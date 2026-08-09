"""AstrBot 插件：主动消息联动 Setu。

当 astrbot_plugin_proactive_chat（主动消息插件）向会话发送主动消息时，
本插件自动向同一会话投递一条 `/setu` 命令事件，让 setu 插件像收到用户
真实命令一样正常发图。

实现原理：
- 主动消息插件每次发送前会触发 AstrBot 的 OnDecoratingResultEvent 钩子
  （core/message_sender.py 的 _trigger_decorating_hooks），传入一个伪造的
  AstrMessageEvent（message_id 为空）。
- 本插件注册该钩子，识别伪造事件后，构造一条带正确会话标识的
  `/setu` 命令事件，投递进 AstrBot 事件队列，走完整管道执行。
"""

from __future__ import annotations

import asyncio
import time
import uuid

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core import AstrBotConfig
from astrbot.core.message.components import Plain
from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_type import MessageType

_DEFAULT_COMMAND = "/setu 3 爱弥斯"


class SetuOnProactivePlugin(Star):
    """主动消息发送时，向同一会话投递配置的指令（默认 setu 发图）。"""

    def __init__(self, context: Context, config: AstrBotConfig | None = None) -> None:
        super().__init__(context, config)
        cfg = config or {}
        # 优先取 commands 列表（自定义多指令）；兼容旧版单条 command 字段
        commands = cfg.get("commands", None)
        if not commands:
            legacy = str(cfg.get("command", _DEFAULT_COMMAND)).strip() or _DEFAULT_COMMAND
            commands = [legacy]
        self._commands = [c.strip() for c in commands if isinstance(c, str) and c.strip()]
        if not self._commands:
            self._commands = [_DEFAULT_COMMAND]
        # 同一会话在窗口内只投递一次，防止主动消息分段/TTS 多段触发重复命令
        self._dedup_window = float(cfg.get("dedup_window_seconds", 60))
        self._last_trigger: dict[str, float] = {}
        self._lock = asyncio.Lock()

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent) -> None:
        """发送消息前钩子：识别主动消息插件的伪造事件并投递 setu 命令。"""
        try:
            msg_obj = getattr(event, "message_obj", None)
            if not msg_obj:
                return
            # 真实平台事件 message_id 非空；主动消息插件构造的伪造事件为空
            if getattr(msg_obj, "message_id", None):
                return
            # 只联动私聊
            if not event.is_private_chat():
                return

            session_key = event.unified_msg_origin
            now = time.time()
            async with self._lock:
                if now - self._last_trigger.get(session_key, 0) < self._dedup_window:
                    return
                self._last_trigger[session_key] = now

            logger.info(
                f"[setu_on_proactive] 主动消息触发，投递指令: {self._commands} -> {session_key}"
            )
            await self._dispatch_commands(event)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[setu_on_proactive] 钩子异常: {e}", exc_info=True)

    async def _dispatch_commands(self, source_event: AstrMessageEvent) -> None:
        """逐条构造指令事件并投递到事件队列，走完整管道。"""
        for command in self._commands:
            await self._dispatch_command(command, source_event)

    async def _dispatch_command(self, command: str, source_event: AstrMessageEvent) -> None:
        """构造单条指令事件并投递到事件队列。"""
        target_id = source_event.get_session_id()
        platform_meta = source_event.platform_meta
        self_id = source_event.get_self_id() or "bot"

        msg_obj = AstrBotMessage()
        msg_obj.type = MessageType.FRIEND_MESSAGE
        msg_obj.session_id = target_id
        msg_obj.message = [Plain(command)]
        msg_obj.message_str = command
        msg_obj.raw_message = command
        msg_obj.message_id = uuid.uuid4().hex
        msg_obj.sender = MessageMember(user_id=target_id)
        msg_obj.self_id = self_id

        new_event = AstrMessageEvent(
            message_str=command,
            message_obj=msg_obj,
            platform_meta=platform_meta,
            session_id=target_id,
        )
        queue = self.context.get_event_queue()
        await queue.put(new_event)
        logger.info(
            f"[setu_on_proactive] 已投递指令事件: {command} -> {new_event.unified_msg_origin}"
        )

# astrbot_plugin_setu_on_proactive（主动消息联动）

AstrBot 插件：当**主动消息插件**向会话发送主动消息时，自动向同一会话投递配置好的指令（默认 `/setu 3 爱弥斯` 发图），让 setu 等指令插件像收到用户真实命令一样正常执行。

## ⚠️ 前置依赖插件（必装）

本插件不负责发送主动消息，它只是"搭车"触发：

- **[astrbot_plugin_proactive_chat](https://github.com/Soulter/astrbot_plugin_proactive_chat)**（主动消息插件）

必须先安装并配置好主动消息插件，让它能正常向目标会话发主动消息。本插件挂在其发送前的钩子上，主动消息插件不发消息，本插件就不会触发。

> 另外，要执行 `/setu` 指令，还需要安装支持该指令的 setu 插件（如 `astrbot_plugin_setu`）；指令可换成任意你想自动执行的命令。

## 功能

- 主动消息插件每次发送前，自动向**同一私聊会话**投递配置的指令列表
- 支持**多条指令**（`commands` 列表），逐条投递、全部执行
- 同一会话 60 秒去重窗口，防止主动消息分段/TTS 多段发送触发重复指令
- 只联动单人私聊，群聊/频道不触发

## 安装

1. 将本插件目录放入 AstrBot 的 `data/plugins/` 下
2. 在 AstrBot WebUI「插件管理」中启用插件
3. 在插件配置中填写要自动执行的指令（可选，默认 `/setu 3 爱弥斯`）

## 配置项

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `commands` | list[str] | `["/setu 3 爱弥斯"]` | 主动消息触发时自动执行的指令列表，可配多条 |
| `command` | str | `/setu 3 爱弥斯` | （旧版兼容）单条指令；已配置 `commands` 时忽略 |
| `dedup_window_seconds` | int | `60` | 同一会话去重窗口（秒），窗口内只投递一次 |

示例：配置 `commands = ["/setu 3 爱弥斯", "/签到"]`，主动消息发出后会自动依次执行这两条指令。

## 工作原理

1. 主动消息插件每次发送前必经 AstrBot 的 `OnDecoratingResultEvent` 钩子（`core/message_sender.py` 的 `_trigger_decorating_hooks`），传入一个伪造事件（`message_id` 为空）
2. 本插件注册该钩子，识别伪造事件后（仅私聊），构造带正确会话标识的指令事件
3. 指令事件投递进 AstrBot 事件队列，走完整管道：命令匹配 → 目标插件执行 → 正常发消息

## 兼容性

- AstrBot v4.x（实测 v4.27.1）
- 旧配置只填了 `command` 单条字段的，无需改动，自动兼容

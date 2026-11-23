# design/ — 设计文档索引

本目录保存改版的设计方案与调研结论，与 ROM 一起进版本管理。

| 文件 | 内容 | 状态 |
|---|---|---|
| [TEAMS.md](TEAMS.md) | 丰缘八馆 + 四天王 + 冠军队伍完整方案：等级、特性、道具、四招、联防设计、配招原则 | ✅ 已实现进 ROM |
| [teams_spec.json](teams_spec.json) | 八馆队伍结构化数据（`gen_party.py` 的输入） | ✅ |
| [teams_e4.json](teams_e4.json) | 四天王 + 冠军队伍结构化数据 | ✅ |
| [gen_party.py](gen_party.py) | 从 JSON 生成 `trainers.party` 片段的脚本 | ✅ |
| [SAVE_COMPAT.md](SAVE_COMPAT.md) | 存档兼容性：改什么会坏档、改什么安全、当前余量实测 | 结论已确认 |
| [ONLINE_LINK.md](ONLINE_LINK.md) | 联机对战调研：模拟器选型（mGBA 已证伪 / VBA-M 可用）、frp 公网中继、掌机三路线 | 隧道已本机验通，掌机环节待定 |

## 三份文档的关系

- **TEAMS.md** 是「游戏里有什么」——已落地
- **SAVE_COMPAT.md** 是「以后还能怎么改」——决定后续改动的边界
- **ONLINE_LINK.md** 是「怎么和别人打」——独立于前两者，与 ROM 内容无关

关键约束记在 SAVE_COMPAT.md：**物种表 / 招式表 / SaveBlock 结构一旦有存档就不能再动**。想让改版长期迭代，这些结构应当在正式开玩前定稿。

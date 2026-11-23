# 联机对战手册（VBA-M + 自建 frp 中继）

> **重要更正**：本文件初版写的是 mGBA 的 `File → Link → Start Link Server`。核实后确认 **mGBA 没有这个功能**——官方 README 把「联网 link cable」列在 *Planned features*（未实现），二进制里也没有任何 `Link Server` 字符串，CHANGES 里只有「multiplayer windows」（同机多开）。网上那些教程是错的。
>
> 真正支持网络 link 的是 **VBA-M**。已实测：VBA-M 2.2.3 能载入我们的 32MB ROM。

---

## 调研结论速查（选型表）

| 模拟器 / 方案 | 网络 link | 结论 | 依据 |
|---|---|---|---|
| mGBA 0.10.5（PC） | ❌ | **不可用**。只有同机多开窗口，没有 netplay | 二进制无 `Link Server` 字符串；官方 README 列为 *Planned* |
| mGBA core（RetroArch / 掌机） | ❌ | **不可用**。继承 mGBA 缺陷，是 core 层面没有，不是配置问题 | 同上 |
| **VBA-M 2.2.3（PC）** | ✅ | **本方案主力**。Cable + Socket 两种链路，TCP 走 `LinkProto`，默认端口 **5738** | 源码确认 `LinkHost` / `LinkPort` / `LinkProto` / `LinkTimeout` 选项存在；实测能载入本 32MB ROM |
| My Boy!（Android） | ✅ | 可用。自带 WiFi 服务端/客户端，走 TCP，可套 frp | 官方功能；本 ROM 未实测 |
| `mgba-wifi-link` core | ⚠️ | 实验性。唯一能让「掌机 Linux ↔ PC RetroArch」互通的路径，需自编 aarch64 core | 项目自述：仅 Multi-Pak、仅局域网 |

**由此确定的技术路线**：PC 端用 VBA-M，VPS 上跑 frps，玩家 A 本机 frpc 把 5738 反向映射到公网，玩家 B 直连 VPS 的 5738。frp 隧道与 ROM 内容无关（裸 TCP 长连接），所以中继层怎么改都不影响游戏本身。

---

## 0. 先记住一条铁律

**两端必须是同一个模拟器。** GBA link 的链路协议由模拟器自己实现，VBA-M、mGBA、My Boy!、RetroArch core 之间互不兼容。选型错了，配置再对也连不上。

---

## 1. VBA-M 的联机能力（已从源码确认）

`src/wx/wxvbam.cpp` 里 `gba_link_type` 的取值：

| 值 | 模式 | 说明 |
|---|---|---|
| 0 | Disconnected | 关闭 |
| **1** | **Cable** | **对战线，联机对战用这个** |
| 2 | RFU | 无线适配器（Wireless Adapter） |
| 3 | GameCube | 连 Dolphin |
| 4 | Game Boy | GB/GBC 串口 |

再叠加一个 `kGBALinkProto`：开启 = IPC（同机进程间），关闭 = **SOCKET（走 TCP 网络）**。
**所以：Cable + 关闭 IPC = 网络对战线。**

网络参数（`src/wx/opts.h`）：

- `link_port` 默认 **5738**
- `LinkHost`：客户端要连的对端地址
- `ServerPort` / server bind IP：服务端监听
- `LinkTimeout`：超时（2.1.5 之前默认值 1，太短最容易误判断线）
- "Link at startup"：启动即开启联机，省得每次点菜单

---

## 2. 开打前的检查项

| 项目 | 要求 |
|---|---|
| ROM | 双方**同一文件**，md5 = `267018b174f8ba9ffbd58fee5cc043bb` |
| 模拟器 | 双方**同版本 VBA-M**（2.2.3） |
| 存档 | 各自独立，不要互传 `.sav` |
| 游戏进度 | 双方都已能进精灵中心 2F |

---

## 3. 先在本机验通（5 分钟）

1. 开两个 VBA-M，各载入同一个 ROM；
2. 两个窗口都进 `Options → Link`：
   - Type = `Cable`
   - 取消勾选 IPC / Local（让它走 socket）
   - Port = `5738`
3. 窗口 A 开启监听（服务端），可勾 "Link at startup"；
4. 窗口 B 的 LinkHost 填 `127.0.0.1`，作为客户端连接；
5. 两边都走到精灵中心 2F，进房间。

本机通了再上公网——否则分不清是链路问题还是模拟器配置问题。

---

## 4. 公网拓扑

```
   玩家 A（主机，无公网 IP）              你的 VPS               玩家 B
 ┌──────────────────────┐            ┌──────────────┐      ┌──────────────┐
 │  VBA-M  监听 :5738    │            │   frps       │      │  VBA-M       │
 │        ▲             │   出站      │  :7000 隧道   │      │  LinkHost    │
 │  frpc ─┴─────────────┼── 7000 ───►│  :5738 游戏  │◄─────┼── VPS:5738   │
 └──────────────────────┘            └──────────────┘      └──────────────┘
```

为什么必须反向隧道：家宽多数没有公网 IP（甚至 CGNAT），VPS 主动连不到你家。frp 让家里那台主动出站连 VPS，VPS 才知道 5738 的流量往哪送。

**例外**：主机侧有公网 IP 时跳过 frp，玩家 B 直接填主机公网 IP。

---

## 5. 部署 VPS

```bash
scp setup_vps.sh root@你的VPS:/root/
ssh root@你的VPS 'bash /root/setup_vps.sh'
```

脚本会：下载 frp → 装到 `/opt/frp` → 生成随机 token → 写 `frps.toml` → 注册 systemd → 放行 ufw → 打印连接信息。

**云厂商安全组**另需放行 `TCP 7000` 和 `TCP 5738`。

---

## 6. 主机端（玩家 A）

1. 编辑 `frpc.toml`：`serverAddr` 填 VPS 公网 IP，`auth.token` 填脚本打印的令牌；
2. 双击 `start_frpc.bat`，看到 `start proxy success`；
3. VBA-M 里开监听（Type=Cable，Port=5738）。

顺序：先开 VBA-M 的监听，再起 frpc，排查更简单。

---

## 7. 客机端（玩家 B）

VBA-M → `Options → Link`：Type=Cable，Port=5738，LinkHost 填 **VPS 公网 IP**（不是玩家 A 的家庭 IP）。
两边同时进精灵中心 2F。

---

## 8. 掌机怎么办（RG353V）

先说结论：**掌机上现成的 mGBA（RetroArch core）连不了**，因为 mGBA 本身没有网络 link——这也是社区里"掌机联机"一直难的原因。

按掌机启动的系统分三条路：

### 路线 A：掌机跑 Android 侧 + My Boy!（最现实）

- My Boy! 自带 WiFi 服务端 / 客户端，填 IP + 端口即可，**两端都是 My Boy!** 就通；
- 走 TCP，能被 frp 转发穿透公网（主机侧 My Boy 开服务端，frpc 映射它的端口）；
- 免费版就支持联机，手柄映射完善；
- **未验证**：我们这个 32MB expansion ROM 在 My Boy! 上能否正常加载与联机，需要实测。

### 路线 B：掌机 Linux 侧 + RetroArch + `mgba-wifi-link` core

- 开源项目 `Aelvryx/mgba-wifi-link`，把 mGBA 魔改成 libretro core，用 RetroArch 的 Netpacket 传 link 数据；
- 官方给 Android ARM64 的 core，**Linux libretro 构建支持源码编译**——要给掌机编一个 aarch64 的 `.so`；
- 两端装同一个 core，**掌机(Linux) ↔ PC(RetroArch) 就打通了**，这是唯一能混搭 PC 的路；
- 限制多：只支持 Multi-Pak（组队对战够用）、**只支持局域网，没有公网中继**（要靠 WireGuard 组虚拟局域网）、宝可梦**未经验证**、实验性。

### 路线 C：掌机 Linux 侧装 VBA-M

- dArkOS 是 Debian 底座，可从源码编 aarch64 版（依赖 wxWidgets3.2 + SDL2）；
- 但 VBA-M 的 wx 界面是给鼠标和 1024×768 设计的，**640×480 + 手柄非常难受**；
- 能编出来，但配置和维护成本最高。不推荐首选。

### 组合可行性速查

| 组合 | 方案 | 可行性 |
|---|---|---|
| PC ↔ PC | VBA-M + frp | ✅ ROM 已实测可载入 |
| 掌机(Android) ↔ 手机 | My Boy! + frp | ⚠️ 需实测 ROM |
| 掌机(Linux) ↔ PC | RetroArch + mgba-wifi-link + WireGuard | ⚠️ 实验性，需自编 core |
| 掌机(Linux) ↔ 掌机(Linux) | 同上 | ⚠️ 同上 |
| 掌机 ↔ 任意端 | mGBA | ❌ 无网络 link |

---

## 9. 延迟预算

VBA-M 的 socket link 每回合有同步点，RTT 越高停顿越明显。

| 单向 RTT | 体验 |
|---|---|
| < 60 ms | 几乎无感 |
| 60–150 ms | 能打，动画间有停顿 |
| 150–250 ms | 容易触发 `LinkTimeout` |
| > 250 ms | 基本打不完一场 |

优化：VPS 选双方都近的节点；双方有线网；关掉加速/快进；`LinkTimeout` 调到 500ms 左右。

---

## 10. 故障排查

| 症状 | 原因 | 解法 |
|---|---|---|
| frpc 报 `connect to server error` | 安全组没放行 7000 | 云控制台 + `ufw allow 7000/tcp` |
| frpc 报 token 不匹配 | 两边 token 不一致 | 重抄脚本输出的令牌 |
| 客机连不上 5738 | 主机没开监听 / 端口不是 5738 | 检查 VBA-M 的 Link 设置 |
| 连上却进不了房间 | 一方还在标题或野外 | 双方都到 2F 房间内 |
| 打到一半断 | `LinkTimeout` 太短 | 调到 500ms |
| 房间显示对方版本不符 | ROM 不一致 | 对 md5 |
| 掌机 RetroArch 里没有联机选项 | 用的是官方 mGBA core | 见第 8 节，官方 core 不支持 |

---

## 11. 关于等级：不拉平

`data/scripts/cable_club.inc` 里只有 单打 / 双打 / 多人，**没有等级选项**；"Lv.50 / 自由等级"只属于对战塔。
→ 联机对战按队伍真实等级结算，双方需自行约定。

---

## 12. 文件清单

| 文件 | 放在哪 | 作用 |
|---|---|---|
| `setup_vps.sh` | VPS | 一键装 frps |
| `frps.toml` / `frps.service` | VPS | 服务端配置与 systemd（模板） |
| `frpc.toml` / `start_frpc.bat` | 主机 PC | 改 IP + token 即可 |
| `frpc.exe` / `frps.exe` | 本目录 | frp v0.72.0 |
| `_test/test_tunnel.py` | 本目录 | 隧道自测（已通过） |

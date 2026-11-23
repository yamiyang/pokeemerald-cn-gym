# 存档兼容性说明

> 回答一个问题：**继续改这个游戏，已有的存档还能打开吗？**
>
> 结论按「改什么」分成两类，不是一律能，也不是一律不能。

---

## 一句话结论

| 你改的东西 | 旧存档 |
|---|---|
| 队伍、等级、招式、道具、特性、AI（`trainers.party`） | ✅ 完全不受影响 |
| 对话文本、NPC 脚本、地图布局、图块 | ✅ 不受影响 |
| 精灵贴图、图鉴说明、招式描述 | ✅ 不受影响 |
| 战斗机制（伤害公式、AI 逻辑、特性效果） | ✅ 不受影响（存档存结果，不存过程） |
| 野生遇敌表、商店、道具价格 | ✅ 不受影响 |
| **物种 / 招式 / 道具 / 训练师的编号表** | ❌ 旧档读不出来 |
| **`SaveBlock1` / `SaveBlock2` 的成员增删** | ❌ 旧档读不出来 |
| **升级 expansion 版本（1.17 → 1.18）** | ❌ 几乎必然坏档 |
| **中文版 ↔ 英文上游换基底** | ❌ 名字乱码、数据错位 |

**你现在这一版属于第一类，以后微调队伍、改剧情、换贴图，存档都不会坏。**

---

## 为什么改队伍绝对安全

`trainers.party` 在编译期被 `trainerproc` 转成 `trainers.h` 里的一张**只读常量表**，嵌在 ROM 里。

存档从来不存对手队伍。存档只存「你打到哪了」——旗标（flags）、变量（vars）、队伍、背包、图鉴。战斗开始时，游戏按 `TRAINER_ROXANNE_1` 这个**编号**去 ROM 里查当前队伍。

所以：

- 改招式、改等级、改特性 → 同一个编号，ROM 里换了个内容，存档无感
- 本版就是活证据：855 个训练师里改了 13 个，ROM 已经编出来了，而训练师常量表（`include/constants/opponents.h`）与上游 `exp1171` **逐字节相同**

验证命令：

```bash
diff -q include/constants/opponents.h /d/exp1171/include/constants/opponents.h   # 无输出 = 一致
diff -q include/constants/species.h   /d/exp1171/include/constants/species.h     # 无输出 = 一致
```

---

## 坏档的确切机制（不是玄学）

GBA 存档 = 14 个 4 KiB 扇区 × 2 个槽位。每扇区结构：

```
[ 3968 字节实际数据 ][ 116 字节 SaveBlock3 ][ 12 字节 footer ]
                                                  └─ signature + checksum
```

数据怎么切，由 `src/save.c` 的 `sSaveSlotLayout` 决定：

```c
SAVEBLOCK_CHUNK(struct, chunkNum)  // = { chunkNum*3968, min(sizeof - chunkNum*3968, 3968) }
```

**关键点：checksum 是按 `sizeof(struct)` 算的。**

读档时（`src/save.c:505`）：

```c
checksum = CalculateChecksum(gReadWriteSector->data, locations[id].size);
if (gReadWriteSector->signature == SECTOR_SIGNATURE && gReadWriteSector->checksum == checksum)
```

`locations[id].size` 来自**当前这颗 ROM** 的结构体大小。旧存档是按**旧的 sizeof** 写进去的。

于是：**sizeof 变一个字节，checksum 就对不上 → 该扇区判为无效 → 换另一个槽位 → 也一样无效 → 游戏提示「存档已损坏」并要求重新开始。**

不是「加太多才坏」，是「改一点点就坏」。

---

## 你这版 ROM 的存档余量（从编译产物实测）

`build/emerald/src/save.o` 里 `sSaveSlotLayout` 的实际数值换算：

| 区块 | 扇区数 | 当前占用 | 上限 | 余量 |
|---|---|---|---|---|
| SaveBlock2 | 1 | 3884 B | 3968 B | **84 B** |
| SaveBlock1 | 4 | 15568 B | 15872 B | **304 B** |
| PokemonStorage | 9 | 34144 B | 35712 B | **1568 B** |
| SaveBlock3 | — | 116 B/扇区 | 116 B | 0（已满，正常） |

**怎么读这张表**：SaveBlock2 只剩 84 字节，往里加一个 `u16` 都勉强。想加存档字段，基本只能从 SaveBlock1 那 304 字节里抠。

好消息：`src/save.c:80-83` 有四条 `STATIC_ASSERT`，**溢出会在编译时直接报错**，不会悄悄写出坏档。报错信息形如 `SaveBlock1FreeSpace`。

---

## 高危操作清单

### 1. 在编号表中间插东西

```c
// include/constants/species.h
SPECIES_PIKACHU,
SPECIES_MY_NEW_MON,   // ← 插在中间：它之后所有物种编号 +1
SPECIES_RAICHU,
```

存档里画的是**编号**。编号一移，旧档里"第 25 号"从皮卡丘变成你的新精灵，整个 PC 盒子全乱。

插入招式（`MOVE_*`）、道具（`ITEM_*`）、训练师（`TRAINER_*`）同理。

### 2. 改 `NUM_SPECIES`（加新精灵）

即使你只在**末尾追加**，`NUM_SPECIES` 一变，`SaveBlock1` 里这两个数组就变长：

```c
u8 dexSeen[NUM_DEX_FLAG_BYTES];    // NUM_DEX_FLAG_BYTES = ROUND_BITS_TO_BYTES(POKEMON_SLOTS_NUMBER)
u8 dexCaught[NUM_DEX_FLAG_BYTES];
```

数组在结构体中间，变长 → 后面所有成员整体后移 → sizeof 变 → 坏档。

**当前余量 304 字节能容纳约 2400 只新精灵**，空间不是问题，问题是「一旦有存档就不能动」。

**所以：要加精灵，趁现在加。这是唯一的时间窗口。**

### 3. 改 flags / vars 数量

```c
u8 flags[NUM_FLAG_BYTES];   // = ROUND_BITS_TO_BYTES(FLAGS_COUNT)
```

改 `FLAGS_COUNT` / `VARS_COUNT` 会让 SaveBlock1 变长。conversion 大量剧情要用 flag，容易踩。

### 4. 改 `PARTY_SIZE` / PC 盒子数量

`struct PokemonStorage` 直接是盒子数组，改盒子数量必然坏档。

### 5. 升级 expansion 版本

1.17 → 1.18 会重排物种 / 招式 enum、改 SaveBlock 布局。**上游从不为留存档做兼容**，反编译项目没有「存档迁移」这个概念。

### 6. 换基底语言

中文仓库的字符是双字节编码（`'啊' = 0x0100`，约 7900 字），英文上游是单字节 Latin。玩家名、精灵昵称在存档里是原始编码值，换基底后名字必然乱码；如果字符表长度也变了，可能连带结构错位。

**中文版存档只能给中文版用。**

---

## 实操建议

1. **现在就开始备份**。哪怕还没怎么玩，先把 `.sav` 存一份。VBA-M / mGBA 是 ROM 同目录同名 `.sav`，RetroArch 是 `saves/` 下的 `.srm`，大小 128 KB（32 扇区 × 4 KB）。

2. **每次改完先开旧档**。不要等玩到一半才发现。改动前后各截一张「继续游戏」界面的图。

3. **把结构改动集中到「还没开始玩」的阶段**。也就是现在。方案刚定、还没进度，正是能自由动结构的窗口。一旦你开始正式玩，物种表、招式表、SaveBlock 就都该冻结了。

4. **真要跨版本迁移，唯一可靠路径是 PKHeX**：
   - 用 PKHeX 打开旧 `.sav`
   - 把队伍和盒子里的宝可梦逐个导出成 `.pk3`
   - 在新版本里开新档，再用 PKHeX 导入
   - **注意**：宝可梦能带走，但进度、徽章、剧情 flag 全部清零。这相当于「只搬宠物，不搬存档」。

5. **改动前先 `git commit`**。这个仓库已经是 git 仓库，`git diff include/constants/` 一眼就能看出有没有碰过编号表。

---

## 复查用的命令

```bash
# 1. 编号表有没有被动过（与上游 1.17.1 对比）
for f in species moves items opponents; do
  diff -q include/constants/$f.h /d/exp1171/include/constants/$f.h && echo "$f: 一致"
done

# 2. 存档三个区块的实际占用
export PATH=/d/msys64/ucrt64/bin:$PATH
arm-none-eabi-objdump -s -j .rodata build/emerald/src/save.o | head -20
# 每 4 字节 = {u16 offset, u16 size}，小端；size=0x0f80(3968) 表示该扇区已满

# 3. 存档结构是否溢出（编译时就会挡）
make -j2   # 报 SaveBlock1FreeSpace 之类的错就是溢出
```

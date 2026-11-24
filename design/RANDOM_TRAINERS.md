# NPC 随机队伍生成算法

## 需求

不是纯随机。要「种类定方向 → 主题池随机 → 打击面兜底」，且严格不超前学招、不提前进化。

脚本：`design/randomize_trainers.py`

```
python3 design/randomize_trainers.py --seed 42 --dry-run
python3 design/randomize_trainers.py --seed 42 --apply
```

`--seed` 改变结果，同一 seed 可复现。

## 五步算法

```
1. 种类 → 主题       Class 决定主属性方向
2. 主题 → 池         按属性筛出该等级可用的基础形态
3. 主怪              池内随机取 1 只
4. 补盲              算出队伍打不动的属性，专门补一只去堵
5. 配招              只从「该等级已能学会」的招里挑，永不超前
```

### 1. 种类 → 主题（65 种 class 全覆盖）

| Class | 主题 | Class | 主题 |
|---|---|---|---|
| Bug Catcher / Bug Maniac | 虫 | Hiker / Ruin Maniac | 岩·地 |
| Bird Keeper | 飞行 | Black Belt / Battle Girl | 格斗 |
| Fisherman / Swimmer / Tuber / Sailor | 水 | Psychic / Medium / Hex Maniac | 超能 / 幽灵 |
| Kindler / Firebreather | 火 | Aroma Lady / Beauty | 草 |
| Guitarist | 电 | Dragon Tamer | 龙 |
| Ninja Boy | 毒·虫 | Team Magma | 火·地 |
| Team Aqua | 水·恶 | Youngster / Lass / School Kid | 普通 |
| Picnicker | 普通·草 | Camper | 普通·火 |
| Lady / Pokefan | 普通·妖精 | Gentleman | 普通·超能 |
| Cooltrainer / Triathlete / Expert / Ranger | **混合（不限属性）** | | |

未列出的 class 一律按「混合」处理，仍然走打击面兜底。

### 2. 池子怎么来

不手工维护 18 个属性池，而是从源码自动筛：

- 从 `src/data/pokemon/species_info/*.h` 读属性与种族值
- 从 `level_up_learnsets/*.h` 读每只的学招表
- **基础形态**判定：没有任何物种通过 `EVOLUTION` 进化成它
- 排除：传说/幻兽/究极异兽、化石精灵、种族值 < 200 或 > 560

### 3. 主怪与等级

- 主怪用队伍最高等级 `hi`
- 其余成员统一 `hi - 1`
- 形态由 `best_form(base, level)` 决定：沿 `EVO_LEVEL` 往上走，**只有 `0 < 进化等级 ≤ level` 才进化**

> ⚠️ 这里踩过一个坑：`EVO_LEVEL 0` 表示「满足特殊条件才进化」（如毒贝比需会龙波），
> 不是「0 级进化」。漏了 `0 <` 会让所有究极异兽 5 级就进化。

### 4. 打击面兜底

```python
cov = coverage(主怪)
while len(team) < size and 还有未覆盖属性:
    从池里随机挑一只「能打到缺口」的
```

`coverage(sp, level)` = 该精灵在此等级能用到的所有攻击招，按属性克制表算出的「能打出 ≥2 倍」的属性集合。

18×18 克制表硬编码在脚本里（只记非 1 的项）。

### 5. 配招

按优先级填 4 格：

1. 本系最高威力攻击招（1 个，不重复堆本系）
2. 能打队伍缺口的补盲招
3. 其他不同属性的攻击招
4. 变化招（前面不足 4 格时补）

只用 `learnset` 里 `等级 ≤ 当前等级` 的招。**TM 招不用**——这样不需要考虑徽章限制。

## AI 强化（开关已打开）

脚本：`design/upgrade_ai.py`　只改 `AI:` 一行，队伍/等级/招式不动，**存档零影响**（AI 标记不存盘，战斗开始时现查）。

原版的问题不是「AI 笨」，是**大部分 NPC 根本没开 AI**：

| 改造前 | 数量 |
|---|---|
| 只有 `Check Bad Move`（不自杀、不送，但不算伤害、不追残血、不换人） | 640 |
| `Basic Trainer`（含全部馆主重赛、Wally、Steven） | 162 |
| 手工调过的完整 AI | 13 |

按最高等级分档，越往后越难缠：

| 等级 | AI |
|---|---|
| < 20 | Check Bad Move / Try To Faint |
| 20+ | + Check Viability（算招式价值、会用变化招） |
| 31+ | + HP Aware（按血量决定先回血还是先打） |
| 44+ | + Smart Switching（读你的队伍，换人针对） |

改造后分布：`CB+TTF` 169 / `+CV` 259 / `+HP` 358 / `+SS` 66。

**开关**（脚本顶部常量）：

```python
ENHANCE_AI = True        # 总开关，False 全部退回原版
OMNISCIENT = False       # 电脑直接看你的招式/道具/特性（开挂级，慎开）
ADD_VIABILITY_FROM = 20
ADD_HP_AWARE_FROM = 31
ADD_SMART_SWITCH_FROM = 44
```

```bash
python design/upgrade_ai.py              # 看统计，不写
python design/upgrade_ai.py --apply      # 生效（备份 .bak_ai）
python design/upgrade_ai.py --apply --off  # 一键还原
```

> 手工设计的 13 队（8 馆 + 四天王 + 冠军）AI 保持原样，那是一队一队调过的。
> `TRAINER_NONE` 与 `*_PLACEHOLDER` 占位空位不塞 AI。

## 保留不动的部分

- **8 馆 + 四天王 + 冠军**（13 个手工设计，队伍里已经混了新世代精灵）
- **所有 `Leader` / `Elite Four` / `Champion`**（含馆主重赛版本 `_2`~`_5`）
- **`TRAINER_STEVEN` / `TRAINER_WALLY_*` / `TRAINER_RED` / `TRAINER_LEAF`**（冠军战、Wally 重赛、彩蛋战，手工设计）
- `_PLACEHOLDER` 占位条目

其余 **797 个**训练师全部重生成。

## 剧情对手（Rival）也随机了

之前 `Rival` 在 `KEEP_CLASS` 里，30 个对手版本（`TRAINER_MAY_*` / `TRAINER_BRENDAN_*`，3 个御三家 × 3 个地点 × 2 个性别）保留原版队伍——就是 **Treecko / Torchic / Mudkip**，新开档走到 103 号路第一战看到的就是这几只，所以「NPC 还是老精灵」的观感主要来自这里。

现在对手参与随机，但保留**克制关系**：后缀是玩家选的御三家，对手挑克制它的属性。

| 后缀 | 玩家选 | 对手主题 | 实例（103 号路） |
|---|---|---|---|
| `_MUDKIP` | 水 | 草 | Smoliv / Bulbasaur |
| `_TREECKO` | 草 | 火 | Slugma / Larvesta |
| `_TORCHIC` | 火 | 水 | Skrelp / Wailmer |

改法：`KEEP_CLASS` 去掉 `Rival`，加 `KEEP_PREFIX` 白名单 + `RIVAL_SUFFIX_THEME` 主题表。

## 传说漏网的修复

原来 `BANNED` 是手写正则，**漏了三圣鸟、三圣兽、三湖神、拉帝欧斯/拉帝亚斯、雷吉三柱、克雷色利亚、三云神**等约 40 只。实测对手队伍里刷出过火焰鸟（MOLTRES）。

现在改成读 `species_info` 的源码标记：

```python
legend = re.search(r"\.(isSubLegendary|isRestrictedLegendary|isMythical|isUltraBeast|isParadox)\s*=\s*TRUE", body)
```

`BASES` 构建时排除，不再依赖手写名单。全量复查：队伍里传说 0 只。

## 校验结果

`design/verify_trainers.py` 复跑：

```
自动生成的精灵: 1482
违规: 0
```

全量复查：队伍内传说/幻兽/悖谬 0 只（含三圣鸟、三圣兽、拉帝欧斯等此前漏网的）。

> 注意：校验时若把原版保留队伍也算进来，会看到 500 多处「招式超等级」。
> 那是原版 NPC 用 TM 招（Wally 的七夕青鸟带燕返、沙奈朵带预知未来），
> 不在升级学招表里，属于误报。只校验物种行是 `SPECIES_` 常量开头的队伍即可。

## 已知取舍

1. **稀有精灵会偶尔出现**：花岩怪（Spiritomb）这类无进化链的稀有物种仍在池里
   （它没被标记为传说，属于正常可捕捉物种）。
2. **弱队仍可能出现**：壶壶（Shuckle）21 级只有 1 个攻击招，生成出来就是 1 招队。
   这是物种本身的学招表决定的，不是算法问题。
3. **固定 seed**：每次 `--apply` 结果相同；换 seed 才会变。想要不同版本就改 seed 重跑。

## 编译踩坑：`make` 只链接不重新生成

改完 `trainers.party` 直接 `make`，可能只做一次链接就「编译成功」，新的 AI/队伍根本没进 ROM。
原因：`Makefile` 用 `ifeq ($(OS),Windows_NT)` 决定 `EXE := .exe`，在 Git Bash 里 `make` 读不到这个变量，
`EXE` 变空 → `tools/trainerproc/trainerproc` 这个前置文件不存在 → `%.h: %.party` 规则被跳过。

```bash
# 出错的样子
make            # 只有 ld / objcopy，没有 trainerproc，ROM 其实没变
# 正确做法：显式指定 EXE
make EXE=.exe generated    # 重新生成 trainers.h（852 条 aiFlags）
make EXE=.exe -j2          # 再编译，会看到 src/data.c 被重编
```

判断有没有真正生效：`stat src/data/trainers.h` 的时间戳应当是刚才，且 `grep -c aiFlags src/data/trainers.h` 等于训练师数。

## 回滚

```bash
cp design/_trainers_before.party src/data/trainers.party
```

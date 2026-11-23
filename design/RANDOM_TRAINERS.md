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

## 保留不动的部分

- **8 馆 + 四天王 + 冠军**（13 个手工设计）
- **所有 `Leader` / `Elite Four` / `Champion` / `Rival`**（含馆主重赛版本、Wally、对手）

其余 **770 个**训练师全部重生成。

## 校验结果

`design/verify_trainers.py` 复跑：

```
自动生成的精灵: 1482
违规: 0
```

> 注意：校验时若把原版保留队伍也算进来，会看到 500 多处「招式超等级」。
> 那是原版 NPC 用 TM 招（Wally 的七夕青鸟带燕返、沙奈朵带预知未来），
> 不在升级学招表里，属于误报。只校验物种行是 `SPECIES_` 常量开头的队伍即可。

## 已知取舍

1. **稀有精灵会偶尔出现**：花岩怪（Spiritomb）这类无进化链的稀有物种仍在池里。
   想彻底排除需要在 `BANNED` 里补名字。
2. **弱队仍可能出现**：壶壶（Shuckle）21 级只有 1 个攻击招，生成出来就是 1 招队。
   这是物种本身的学招表决定的，不是算法问题。
3. **固定 seed**：每次 `--apply` 结果相同；换 seed 才会变。想要不同版本就改 seed 重跑。

## 回滚

```bash
cp design/_trainers_before.party src/data/trainers.party
```

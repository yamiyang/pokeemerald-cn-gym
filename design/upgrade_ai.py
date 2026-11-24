#!/usr/bin/env python3
"""NPC 对战 AI 强化开关。

原版 trainer 的 AI 只有一格半：839 个里有 640 个只挂 `AI_FLAG_CHECK_BAD_MOVE`，
等于「不自杀、不送」，但**不会算伤害、不会追残血、不会换人**。

这个脚本只改 `AI:` 这一行，队伍/等级/招式一律不动，所以：
  - 已生成好的随机队伍不会变（结果可复现）
  - 存档兼容性零影响（AI 标记不存档，战斗开始时现查）

用法
----
    python3 design/upgrade_ai.py            # 只看统计，不写
    python3 design/upgrade_ai.py --apply    # 写入
    python3 design/upgrade_ai.py --apply --off   # 一键还原成基础 AI

分级（按队伍最高等级）
----
    < 20  Check Bad Move / Try To Faint                  会挑招，会收人头
    20+   + Check Viability                              会算「这招到底值不值」、会用变化招
    31+   + HP Aware                                     会看双方血量决定先回血还是先打
    44+   + Smart Switching                              会读你的队伍，换人针对

手工设计的 13 个队伍（8 馆 + 四天王 + 冠军）保持原样，那是一队一队调过的。
"""
import re
import sys
import collections

PARTY = "src/data/trainers.party"

# ============ 开关 ============
ENHANCE_AI = True        # 总开关：False = 全部退回原版基础 AI
OMNISCIENT = False       # 电脑直接看到你的招式/道具/特性（开挂级，慎开）
ADD_VIABILITY_FROM = 20  # 从这级开始算招式价值
ADD_HP_AWARE_FROM = 31   # 从这级开始看血量
ADD_SMART_SWITCH_FROM = 44  # 从这级开始会换人
# =============================

# 手工调过的 13 个，AI 不动
MANUAL = {
    "TRAINER_ROXANNE_1", "TRAINER_BRAWLY_1", "TRAINER_WATTSON_1", "TRAINER_FLANNERY_1",
    "TRAINER_NORMAN_1", "TRAINER_WINONA_1", "TRAINER_TATE_AND_LIZA_1", "TRAINER_JUAN_1",
    "TRAINER_SIDNEY", "TRAINER_PHOEBE", "TRAINER_GLACIA", "TRAINER_DRAKE", "TRAINER_WALLACE",
}


def flags_for(level):
    if not ENHANCE_AI:
        return ["Check Bad Move", "Try To Faint"]
    f = ["Check Bad Move", "Try To Faint"]
    if level >= ADD_VIABILITY_FROM:
        f.append("Check Viability")
    if level >= ADD_HP_AWARE_FROM:
        f.append("HP Aware")
    if level >= ADD_SMART_SWITCH_FROM:
        f.append("Smart Switching")
    if OMNISCIENT:
        f.append("Omniscient")
    return f


def main():
    apply = "--apply" in sys.argv
    # --off 等价于把总开关临时关掉
    if "--off" in sys.argv:
        globals()["ENHANCE_AI"] = False

    raw = open(PARTY, encoding="utf-8").read()
    blocks = re.split(r"(?m)^(=== (TRAINER_[A-Z0-9_]+) ===)$", raw)
    # blocks = [header, marker, name, seg, marker, name, seg, ...]

    out = [blocks[0]]
    stats = collections.Counter()
    samples = []

    i = 1
    while i + 2 < len(blocks):
        marker, name, seg = blocks[i], blocks[i + 1], blocks[i + 2]
        levels = [int(x) for x in re.findall(r"^Level: (\d+)$", seg, re.M)]
        hi = max(levels) if levels else 0

        # 占位空位没有队伍，别给它塞 AI
        if name == "TRAINER_NONE" or name.endswith("_PLACEHOLDER"):
            out.extend([marker, seg])
            stats["placeholder_skipped"] += 1
            i += 3
            continue

        if name in MANUAL:
            out.extend([marker, seg])
            stats["manual_kept"] += 1
            i += 3
            continue

        want = "AI: " + " / ".join(flags_for(hi))
        old_line = re.search(r"(?m)^AI:.*$", seg)

        if old_line:
            if old_line.group(0).strip() == want:
                stats["already"] += 1
                new_seg = seg
            else:
                new_seg = seg[:old_line.start()] + want + seg[old_line.end():]
                stats["changed"] += 1
        else:
            # 没有 AI 行（RED / LEAF），插在头部最后一行之后
            m = re.search(r"(?m)^(Name|Class|Pic|Gender|Music|Double Battle):.*\n", seg)
            if not m:
                out.extend([marker, seg])
                stats["skipped"] += 1
                i += 3
                continue
            idx = m.start()
            while True:
                m2 = re.compile(r"(?m)^(Name|Class|Pic|Gender|Music|Double Battle):.*\n").match(seg, idx)
                if not m2:
                    break
                idx = m2.end()
            new_seg = seg[:idx] + want + "\n" + seg[idx:]
            stats["inserted"] += 1

        if len(samples) < 4 and stats["changed"] + stats["inserted"] <= 8:
            samples.append((name, hi, want))
        out.extend([marker, new_seg])
        i += 3

    new_txt = "".join(out)

    print("\n=== 统计 ===")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print("\n=== 抽样 ===")
    for n, lv, w in samples:
        print(f"  {n} Lv{lv}\n    {w}")

    dist = collections.Counter(re.findall(r"(?m)^AI: (.+)$", new_txt))
    print("\n=== 写入后 AI 分布 ===")
    for k, v in dist.most_common():
        print(f"  {v:4d}  {k}")

    if apply:
        if new_txt != raw:
            open(PARTY + ".bak_ai", "w", encoding="utf-8").write(raw)
            open(PARTY, "w", encoding="utf-8").write(new_txt)
            print("\n已写入 %s（备份 .bak_ai）" % PARTY)
        else:
            print("\n内容无变化，未写入")
    else:
        print("\n(dry-run，未写入；加 --apply 生效)")


if __name__ == "__main__":
    main()

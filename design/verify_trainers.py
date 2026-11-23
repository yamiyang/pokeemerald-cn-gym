#!/usr/bin/env python3
"""批量校验 trainers.party 里每只精灵的进化与学招合法性。"""
import collections
import re
import sys

sys.path.insert(0, r"D:\tools")
import dex  # noqa: E402

PARTY = "src/data/trainers.party"
SKIP_TAIL = ("AI:", "Name:", "Class:", "Pic:", "Gender:", "Music:",
             "Double Battle:", "Items:", "IVs:", "Ability:", "Level:", "===")


def main():
    lines = open(PARTY, encoding="utf-8").read().split("\n")
    trainer = None
    sp = None
    lvl = None
    moves = []
    errs_all = []
    total = 0

    def flush():
        nonlocal sp, lvl, moves, total
        if sp and lvl:
            total += 1
            e, _, name, _ = dex.check_mon(sp, lvl, moves)
            if e:
                errs_all.append((trainer, sp, lvl, moves, e))
        sp, lvl, moves = None, None, []

    for ln in lines:
        s = ln.strip()
        if s.startswith("=== "):
            flush()
            trainer = s.strip("= ").strip()
            continue
        if not s:
            continue
        if s.startswith("- "):
            moves.append(s[2:])
            continue
        if s.startswith("Level:"):
            lvl = int(s.split(":")[1])
            continue
        if s.startswith(SKIP_TAIL):
            continue
        # 物种行（可能带 @ 道具）
        cand = s.split("@")[0].strip()
        if cand:
            flush()
            sp = cand if cand.startswith("SPECIES_") else "SPECIES_" + cand.upper().replace(" ", "_").replace("-", "_")
    flush()

    print(f"校验精灵总数: {total}")
    print(f"有问题的精灵: {len(errs_all)}")
    kinds = collections.Counter()
    for _, _, _, _, e in errs_all:
        for msg in e:
            if "学不到" in msg:
                kinds["招式超等级"] += 1
            elif "不该是未进化形态" in msg:
                kinds["未进化"] += 1
            elif "需要" in msg and "级进化" in msg:
                kinds["提前进化"] += 1
            elif "不存在" in msg:
                kinds["常量不存在"] += 1
            else:
                kinds["其他"] += 1
    for k, v in kinds.most_common():
        print(f"  {k}: {v}")

    print("\n=== 样例（最多 12 条）===")
    for t, sp_, lv, mv, e in errs_all[:12]:
        print(f"  {t} {sp_} Lv{lv}")
        for m in e[:3]:
            print(f"     - {m}")


if __name__ == "__main__":
    main()

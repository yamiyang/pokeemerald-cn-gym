#!/usr/bin/env python3
"""把野外遇敌用到的 Gen4-9 新物种补进丰缘图鉴（FOREACH_SPECIES_IN_HOENN_DEX_ORDER）。

为什么不能直接按全国编号插
--------------------------
丰缘图鉴不是按全国编号排的，而是按「首次遭遇地点」分组：
木守宫(252) 在第 1 号，绿毛虫(10) 却排在几十号之后。
纯按编号插入会让小鸭嘴火龙(240) 跑到木守宫前面、抢走图鉴第 1 号。

所以本脚本按「遇敌邻居」定位：
  新物种 X 出现在地图 M 上 → 找 M 上已有的丰缘物种里编号最接近的那个 → 插在它后面
这样 MAGBY 会跟在 Fiery Path 的 NUMEL/SLUGMA 附近，而不是跑到图鉴开头。

安全性
------
改这张表不会坏档：存档里的 dexSeen[] 按全国编号索引
（NUM_DEX_FLAG_BYTES 取决于 NATIONAL_DEX_COUNT），与丰缘显示顺序无关。

用法
----
    python3 design/add_to_hoenn_dex.py --dry-run
    python3 design/add_to_hoenn_dex.py --apply
"""
import collections
import importlib.util
import json
import re
import sys

POKEDEX_H = "include/constants/pokedex.h"
WILD_JSON = "src/data/wild_encounters.json"
WILD_BEFORE = "design/_wild_before.json"


def load_retint():
    spec = importlib.util.spec_from_file_location("rw", "design/retint_wild.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    apply = "--apply" in sys.argv
    txt = open(POKEDEX_H, encoding="utf-8").read()

    head = "#define FOREACH_SPECIES_IN_HOENN_DEX_ORDER(F) \\"
    m = re.search(re.escape(head) + r"(.*?)\n\n", txt, re.S)
    if not m:
        print("ERROR: 找不到 FOREACH_SPECIES_IN_HOENN_DEX_ORDER 定义")
        return 1
    block = m.group(1)

    nm = re.search(r"enum NationalDexOrder\s*\{(.*?)\};", txt, re.S)
    order = re.findall(r"NATIONAL_DEX_([A-Z0-9_]+)", nm.group(1))
    nidx = {n: i for i, n in enumerate(order)}

    rows = []
    for line in block.split("\n"):
        if not line.strip():
            continue
        mm = re.search(r"F\(([A-Z0-9_]+)\)", line)
        if mm:
            rows.append([mm.group(1), line])
    cur = [r[0] for r in rows]
    cur_set = set(cur)
    print("现有丰缘图鉴条目: %d" % len(cur))

    rw = load_retint()
    pool_sp = set()
    for p in rw.POOLS.values():
        pool_sp |= set(p)
    add = sorted([s for s in pool_sp if s not in cur_set], key=lambda n: nidx.get(n, 99999))
    if not add:
        print("没有需要补充的物种。")
        return 0
    print("池中候选: %d" % len(add))

    def build_index(path):
        d = json.load(open(path, encoding="utf-8"))
        group = d["wild_encounter_groups"][0]
        fields = [f["type"] for f in group["fields"]]
        sp_maps = collections.defaultdict(set)
        map_sps = collections.defaultdict(set)
        for e in group["encounters"]:
            if e["map"] not in rw.ECO_BY_MAP:
                continue
            for t in fields:
                b = e.get(t)
                if not b or not b.get("mons"):
                    continue
                for mon in b["mons"]:
                    sp = mon["species"].replace("SPECIES_", "")
                    sp_maps[sp].add(e["map"])
                    map_sps[e["map"]].add(sp)
        return sp_maps, map_sps

    sp_maps, _ = build_index(WILD_JSON)        # 新物种实际落在哪些地图
    _, map_sps = build_index(WILD_BEFORE)      # 这些地图原本有哪些丰缘物种

    # 只补真正进了遇敌表的物种
    add = [s for s in add if s in sp_maps]
    print("实际待补: %d" % len(add))
    if not add:
        print("没有需要补充的物种。")
        return 0

    def anchor_for(sp):
        """共现地图最多的丰缘物种作锚点；并列时取全国编号最接近的"""
        n = nidx.get(sp, 9999)
        co = collections.Counter()
        for mp in sp_maps.get(sp, ()):
            for cand in map_sps.get(mp, ()):
                if cand in cur_set:
                    co[cand] += 1
        if not co:
            return None
        return max(co.items(), key=lambda kv: (kv[1], -abs(nidx.get(kv[0], 9999) - n)))[0]

    groups = collections.defaultdict(list)
    orphan = []
    for sp in add:
        a = anchor_for(sp)
        if a:
            groups[a].append(sp)
        else:
            orphan.append(sp)

    print("有锚点: %d | 无锚点追加末尾: %d %s"
          % (len(add) - len(orphan), len(orphan), orphan))

    pos_of = {r[0]: i for i, r in enumerate(rows)}
    for anchor in sorted(groups, key=lambda a: -pos_of[a]):
        sps = sorted(groups[anchor], key=lambda n: nidx.get(n, 99999))
        at = pos_of[anchor] + 1
        for k, sp in enumerate(sps):
            rows.insert(at + k, [sp, "    F(%s)" % sp])
            pos_of[sp] = at + k
    for sp in sorted(orphan, key=lambda n: nidx.get(n, 99999)):
        rows.append([sp, "    F(%s)" % sp])

    print("\n=== 抽样：插入位置 ===")
    for sp in add[:8]:
        i = next(j for j, r in enumerate(rows) if r[0] == sp)
        prev = rows[i - 1][0] if i > 0 else "-"
        print("  %-12s 跟 %-12s 后面" % (sp, prev))

    out = []
    for i, (name, raw) in enumerate(rows):
        body = raw.rstrip()
        if body.endswith("\\"):
            body = body[:-1].rstrip()
        out.append(body + (" \\" if i < len(rows) - 1 else ""))
    new_block = "\n".join(out)
    new_txt = txt[: m.start()] + head + "\n" + new_block + "\n\n" + txt[m.end():]

    print("\n丰缘图鉴条目: %d -> %d (+%d)" % (len(cur), len(rows), len(rows) - len(cur)))

    if apply:
        open(POKEDEX_H, "w", encoding="utf-8").write(new_txt)
        print("已写入 %s" % POKEDEX_H)
    else:
        print("(dry-run，未写入)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

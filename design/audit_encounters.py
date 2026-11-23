#!/usr/bin/env python3
"""审计野外遇敌是否符合地形。

规则
----
1. 水域槽（water_mons / fishing）里的物种必须含水系
2. 沙漠不许出现火、水、冰
3. 火山不许出现水、冰，且 land 里必须有火系
4. 冰室不许出现火系
5. 陆地槽里不该出现纯水栖物种（含水系但非水/冰双属性的水鱼）

用法
----
    python3 design/audit_encounters.py
"""
import importlib.util
import json
import os
import re
import sys

SPEC_DIR = "src/data/pokemon/species_info"
WILD = "src/data/wild_encounters.json"


ALIAS = dict(re.findall(r"(SPECIES_\w+)\s*=\s*(SPECIES_\w+)\s*,",
                       open("include/constants/species.h", encoding="utf-8").read()))


def resolve(sp, depth=0):
    if depth > 3:
        return sp
    nxt = ALIAS.get("SPECIES_" + sp)
    return resolve(nxt.replace("SPECIES_", ""), depth + 1) if nxt else sp


def parse_types():
    out = {}
    for fn in sorted(os.listdir(SPEC_DIR)):
        if not fn.endswith(".h"):
            continue
        txt = open(os.path.join(SPEC_DIR, fn), encoding="utf-8", errors="ignore").read()
        parts = re.split(r"\n\s*\[(SPECIES_\w+)\]\s*=\s*\{", txt)
        for i in range(1, len(parts) - 1, 2):
            ty = re.search(r"\.types\s*=\s*MON_TYPES\(([^)]*)\)", parts[i + 1])
            if ty:
                out[parts[i].replace("SPECIES_", "")] = [
                    t.strip().replace("TYPE_", "") for t in ty.group(1).split(",") if t.strip()]
    return out


def main():
    spec = importlib.util.spec_from_file_location("rw", "design/retint_wild.py")
    rw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rw)

    T = parse_types()
    d = json.load(open(WILD, encoding="utf-8"))
    group = d["wild_encounter_groups"][0]
    fields = [f["type"] for f in group["fields"]]

    pool_sp = set()
    for p in rw.POOLS.values():
        pool_sp |= set(p)
    orig = set()
    antes = json.load(open("design/_wild_before.json", encoding="utf-8"))
    for e in antes["wild_encounter_groups"][0]["encounters"]:
        if e["map"] not in rw.ECO_BY_MAP:
            continue
        for t in ["land_mons", "water_mons", "rock_smash_mons", "fishing_mons"]:
            b = e.get(t)
            if b and b.get("mons"):
                for mon in b["mons"]:
                    orig.add(mon["species"].replace("SPECIES_", ""))

    problems = []
    per_eco = {}

    for e in group["encounters"]:
        mp = e["map"]
        if mp not in rw.ECO_BY_MAP:
            continue
        eco = rw.ECO_BY_MAP[mp]
        for t in fields:
            b = e.get(t)
            if not b or not b.get("mons"):
                continue
            for mon in b["mons"]:
                sp = mon["species"].replace("SPECIES_", "")
                ty = T.get(sp) or T.get(resolve(sp), [])
                per_eco.setdefault((eco, t), {}).setdefault(sp, 0)
                per_eco[(eco, t)][sp] += 1

                is_new = sp in pool_sp and sp not in orig
                if not is_new or not ty:
                    continue
                # 规则 1：水域里的新物种必须含水系（水鸟也算，只要带 WATER）
                if t in ("water_mons", "fishing_mons") and "WATER" not in ty:
                    problems.append((mp, t, sp, ty, "水域里放了非水栖"))
                # 规则 2：沙漠禁火
                if eco == "desert" and t == "land_mons" and "FIRE" in ty:
                    problems.append((mp, t, sp, ty, "沙漠放了火系"))
                # 规则 3：火山陆地禁水（冰也禁）
                if eco == "volcano" and t == "land_mons" and ({"WATER", "ICE"} & set(ty)):
                    problems.append((mp, t, sp, ty, "火山陆地放了水/冰"))
                # 规则 4：冰室禁火
                if eco == "ice" and "FIRE" in ty:
                    problems.append((mp, t, sp, ty, "冰室放了火系"))
                # 规则 5：陆地槽不该放纯水栖（无飞行/浮游解释）
                if t == "land_mons" and "WATER" in ty and not ({"FLYING", "ICE"} & set(ty)) \
                        and eco not in ("ocean", "deepsea", "ship", "cave"):
                    problems.append((mp, t, sp, ty, "干旱陆地放了水栖"))

    print("=== 各生态的物种属性分布 ===")
    for (eco, t), cnt in sorted(per_eco.items()):
        if t not in ("land_mons", "water_mons"):
            continue
        tyc = {}
        for sp in cnt:
            for ty in T.get(sp, []):
                tyc[ty] = tyc.get(ty, 0) + 1
        top = sorted(tyc.items(), key=lambda kv: -kv[1])[:6]
        print(f"  {eco:<10} {t:<11} 物种{len(cnt):>3} 属性分布 {top}")

    # 火山是否真的有火系
    print("\n=== 火山 land 的火系占比 ===")
    for (eco, t), cnt in per_eco.items():
        if eco != "volcano" or t != "land_mons":
            continue
        fire = [s for s in cnt if "FIRE" in T.get(s, [])]
        print(f"  火系物种 {len(fire)}/{len(cnt)}: {fire[:8]}")

    print("\n=== 违规 ===")
    if not problems:
        print("  无")
    else:
        agg = {}
        for mp, t, sp, ty, why in problems:
            agg.setdefault((t, sp, tuple(ty), why), 0)
            agg[(t, sp, tuple(ty), why)] += 1
        for (t, sp, ty, why), n in sorted(agg.items(), key=lambda kv: -kv[1])[:30]:
            print(f"  [{why}] {sp} {list(ty)} x{n}")
        print(f"  合计 {len(problems)} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())

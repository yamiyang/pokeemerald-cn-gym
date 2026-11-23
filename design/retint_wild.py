#!/usr/bin/env python3
"""按生态把 Gen4-9 精灵混入丰缘野外遇敌表（wild_encounters.json）。

设计原则
--------
1. 保留原路线的主要物种：每个区块保留 2-3 个原生种，占总遇敌概率 60%
2. 新精灵占约 40%，取自与区域生态匹配的池（草原/森林/洞穴/沙漠/火山/冰/海洋/海底/山顶/墓园/火山灰/狩猎区/废船）
3. 等级沿用原槽位，不改 encounter_rate，不改 fishing
4. 不动 ALTERING_CAVE（特殊机制）与 FRLG 地图（我们编的是 emerald）
5. 同一生态内不同地图用不同偏移取池，避免全图重复

用法
----
    python3 design/retint_wild.py --dry-run      # 只打印报告
    python3 design/retint_wild.py --apply        # 写回 JSON
"""
import json
import re
import sys
import collections
import os

JSON_PATH = "src/data/wild_encounters.json"
SPECIES_H = "include/constants/species.h"

# 12 槽 land 模板：N=原生种，A/B/C=新精灵
# 槽位权重 [20,20,10,10,10,10,5,5,4,4,1,1]
#   N1=idx0+2=30  A=idx1+4=30  N2=idx3+9=14  N3=idx5+11=11  N4=idx7=5  B=idx6+8=9  C=idx10=1
#   原生 = 30+14+11+5 = 60
#   新   = 30+9+1   = 40
TPL_LAND = ["N1", "A", "N1", "N2", "A", "N3", "B", "N4", "B", "N2", "C", "N3"]

# 5 槽 water / rock_smash 模板，权重 [60,30,5,4,1]
#   原生 = N1(60+1) + N2(5) = 66，新 = A(30) + B(4) = 34
TPL_FIVE = ["N1", "A", "N2", "B", "N1"]

# 地图 -> 生态
ECO_BY_MAP = {
    "MAP_ROUTE101": "grassland", "MAP_ROUTE102": "grassland", "MAP_ROUTE103": "grassland",
    "MAP_ROUTE110": "grassland", "MAP_ROUTE115": "grassland", "MAP_ROUTE117": "grassland",
    "MAP_ROUTE118": "grassland",
    "MAP_ROUTE104": "forest", "MAP_ROUTE116": "forest", "MAP_ROUTE119": "forest",
    "MAP_ROUTE120": "forest", "MAP_ROUTE121": "forest", "MAP_ROUTE123": "forest",
    "MAP_PETALBURG_WOODS": "forest", "MAP_ROUTE114": "forest",
    "MAP_GRANITE_CAVE_1F": "cave", "MAP_GRANITE_CAVE_B1F": "cave",
    "MAP_GRANITE_CAVE_B2F": "cave", "MAP_GRANITE_CAVE_STEVENS_ROOM": "cave",
    "MAP_RUSTURF_TUNNEL": "cave", "MAP_ARTISAN_CAVE_1F": "cave", "MAP_ARTISAN_CAVE_B1F": "cave",
    "MAP_METEOR_FALLS_1F_1R": "cave", "MAP_METEOR_FALLS_1F_2R": "cave",
    "MAP_METEOR_FALLS_B1F_1R": "cave", "MAP_METEOR_FALLS_B1F_2R": "cave",
    "MAP_METEOR_FALLS_STEVENS_CAVE": "cave",
    "MAP_CAVE_OF_ORIGIN_1F": "cave", "MAP_CAVE_OF_ORIGIN_ENTRANCE": "cave",
    "MAP_NEW_MAUVILLE_ENTRANCE": "cave", "MAP_NEW_MAUVILLE_INSIDE": "cave",
    "MAP_VICTORY_ROAD_1F": "cave", "MAP_VICTORY_ROAD_B1F": "cave",
    "MAP_VICTORY_ROAD_B2F": "cave", "MAP_VICTORY_ROAD_2F": "cave", "MAP_VICTORY_ROAD_3F": "cave",
    "MAP_SHOAL_CAVE_LOW_TIDE_ENTRANCE_ROOM": "cave",
    "MAP_SHOAL_CAVE_LOW_TIDE_INNER_ROOM": "cave",
    "MAP_SHOAL_CAVE_LOW_TIDE_LOWER_ROOM": "cave",
    "MAP_SHOAL_CAVE_LOW_TIDE_STAIRS_ROOM": "cave",
    "MAP_SHOAL_CAVE_LOW_TIDE_ICE_ROOM": "ice",
    "MAP_ROUTE111": "desert", "MAP_DESERT_UNDERPASS": "desert",
    "MAP_FIERY_PATH": "volcano", "MAP_ROUTE112": "volcano", "MAP_JAGGED_PASS": "volcano",
    "MAP_MAGMA_HIDEOUT_1F": "volcano", "MAP_MAGMA_HIDEOUT_2F_1R": "volcano",
    "MAP_MAGMA_HIDEOUT_2F_2R": "volcano", "MAP_MAGMA_HIDEOUT_2F_3R": "volcano",
    "MAP_MAGMA_HIDEOUT_3F_1R": "volcano", "MAP_MAGMA_HIDEOUT_3F_2R": "volcano",
    "MAP_MAGMA_HIDEOUT_3F_3R": "volcano", "MAP_MAGMA_HIDEOUT_4F": "volcano",
    "MAP_SEAFLOOR_CAVERN_ENTRANCE": "cave", "MAP_SEAFLOOR_CAVERN_ROOM1": "cave",
    "MAP_SEAFLOOR_CAVERN_ROOM2": "cave", "MAP_SEAFLOOR_CAVERN_ROOM3": "cave",
    "MAP_SEAFLOOR_CAVERN_ROOM4": "cave", "MAP_SEAFLOOR_CAVERN_ROOM5": "cave",
    "MAP_SEAFLOOR_CAVERN_ROOM6": "cave", "MAP_SEAFLOOR_CAVERN_ROOM7": "cave",
    "MAP_SEAFLOOR_CAVERN_ROOM8": "cave",
    "MAP_ROUTE113": "ash",
    "MAP_MT_PYRE_1F": "shrine", "MAP_MT_PYRE_2F": "shrine", "MAP_MT_PYRE_3F": "shrine",
    "MAP_MT_PYRE_4F": "shrine", "MAP_MT_PYRE_5F": "shrine", "MAP_MT_PYRE_6F": "shrine",
    "MAP_MT_PYRE_EXTERIOR": "shrine", "MAP_MT_PYRE_SUMMIT": "shrine",
    "MAP_SKY_PILLAR_1F": "highland", "MAP_SKY_PILLAR_3F": "highland",
    "MAP_SKY_PILLAR_5F": "highland",
    "MAP_ABANDONED_SHIP_ROOMS_B1F": "ship",
    "MAP_ABANDONED_SHIP_HIDDEN_FLOOR_CORRIDORS": "ship",
    "MAP_UNDERWATER_ROUTE124": "deepsea", "MAP_UNDERWATER_ROUTE126": "deepsea",
    "MAP_SAFARI_ZONE_CENTER": "safari", "MAP_SAFARI_ZONE_EAST": "safari",
    "MAP_SAFARI_ZONE_NORTH": "safari", "MAP_SAFARI_ZONE_NORTHEAST": "safari",
    "MAP_SAFARI_ZONE_NORTHWEST": "safari", "MAP_SAFARI_ZONE_SOUTH": "safari",
    "MAP_SAFARI_ZONE_SOUTHEAST": "safari", "MAP_SAFARI_ZONE_SOUTHWEST": "safari",
    "MAP_SAFARI_ZONE_WEST": "safari",
}
# 海上/城市水面：三位数路线 + 沿海城镇
for _n in list(range(105, 110)) + list(range(122, 135)):
    if _n == 123:
        continue  # 123 号路是陆地路线（有草原与树林），不是水面
    ECO_BY_MAP["MAP_ROUTE%d" % _n] = "ocean"
ECO_BY_MAP["MAP_ROUTE123"] = "forest"
for _c in ["MAP_DEWFORD_TOWN", "MAP_SLATEPORT_CITY", "MAP_LILYCOVE_CITY",
           "MAP_MOSSDEEP_CITY", "MAP_SOOTOPOLIS_CITY", "MAP_PACIFIDLOG_TOWN",
           "MAP_EVER_GRANDE_CITY", "MAP_PETALBURG_CITY"]:
    ECO_BY_MAP[_c] = "ocean"

# 生态 -> 新精灵池（只用基础形态，保证任何等级出现都合理）
POOLS = {
    "grassland": ["STARLY", "PIDOVE", "LILLIPUP", "FLETCHLING", "BUNNELBY",
                  "SKWOVET", "WOOLOO", "LECHONK", "PAWMI", "FIDOUGH", "BLITZLE"],
    "forest": ["KRICKETOT", "BUDEW", "CHERUBI", "SEWADDLE", "VENIPEDE", "COTTONEE",
               "PETILIL", "SCATTERBUG", "GRUBBIN", "CUTIEFLY", "BLIPBUG",
               "TAROUNTULA", "NYMBLE", "SMOLIV", "PHANTUMP", "APPLIN"],
    "cave": ["BRONZOR", "CHINGLING", "ROGGENROLA", "WOOBAT", "DRILBUR", "CARBINK",
             "BINACLE", "ROCKRUFF", "MUDBRAY", "ROLYCOLY", "NACLI", "SILICOBRA"],
    "desert": ["HIPPOPOTAS", "SKORUPI", "SANDILE", "HELIOPTILE", "SANDYGAST",
               "SILICOBRA", "TOEDSCOOL"],
    "volcano": ["MAGBY", "DARUMAKA", "LITLEO", "SALANDIT", "SIZZLIPEDE", "CHARCADET"],
    "ice": ["SNOVER", "VANILLITE", "CUBCHOO", "BERGMITE", "SNOM"],
    "ocean": ["BUIZEL", "SHELLOS", "FINNEON", "BASCULIN", "FRILLISH", "CLAUNCHER",
              "SKRELP", "WISHIWASHI", "CHEWTLE", "ARROKUDA", "WIGLETT"],
    "deepsea": ["FRILLISH", "SKRELP", "MAREANIE", "WISHIWASHI", "ALOMOMOLA"],
    "highland": ["SIGILYPH", "MINIOR", "BOMBIRDIER", "ARCHEN", "WOOBAT"],
    "ship": ["FRILLISH", "PHANTUMP", "DHELMISE", "SWANNA"],
    "shrine": ["DRIFLOON", "YAMASK", "LITWICK", "PHANTUMP", "PUMPKABOO",
               "MIMIKYU", "SINISTEA", "GREAVARD"],
    "ash": ["LITLEO", "SIZZLIPEDE", "ROLYCOLY", "SALANDIT", "CHARCADET"],
    "safari": ["DEERLING", "BOUFFALANT", "SKIDDO", "MUDBRAY", "BLITZLE"],
}

SKIP = {"MAP_ALTERING_CAVE",
        "MAP_SIX_ISLAND_ALTERING_CAVE",
        "MAP_CAVE_OF_ORIGIN_UNUSED_RUBY_SAPPHIRE_MAP1",
        "MAP_CAVE_OF_ORIGIN_UNUSED_RUBY_SAPPHIRE_MAP2",
        "MAP_CAVE_OF_ORIGIN_UNUSED_RUBY_SAPPHIRE_MAP3"}



SPECIES_H = "include/constants/species.h"
SPEC_DIR = "src/data/pokemon/species_info"


def parse_types():
    """物种 -> 属性列表（自动跟随 SPECIES_X = SPECIES_Y 形态别名）"""
    alias = dict(re.findall(r"(SPECIES_\w+)\s*=\s*(SPECIES_\w+)\s*,",
                            open(SPECIES_H, encoding="utf-8").read()))
    types = {}
    for fn in sorted(os.listdir(SPEC_DIR)):
        if not fn.endswith(".h"):
            continue
        txt = open(os.path.join(SPEC_DIR, fn), encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"\n\s*\[(SPECIES_\w+)\]\s*=\s*\{(.*?)\n    \},", txt, re.S):
            ty = re.search(r"\.types\s*=\s*MON_TYPES\(([^)]*)\)", m.group(2))
            if ty:
                types[m.group(1).replace("SPECIES_", "")] = [
                    x.strip().replace("TYPE_", "") for x in ty.group(1).split(",") if x.strip()]

    def resolve(sp, d=0):
        n = alias.get("SPECIES_" + sp)
        return resolve(n.replace("SPECIES_", ""), d + 1) if (n and d < 3) else sp

    for sp in list(types):
        if sp not in types:
            continue
    return types, resolve


def clean_water(group, fields, types, resolve):
    """水域里不能有既非水系、也非飞行/龙系的物种（岩石浮在水面这种）"""
    fixed = []
    for e in group["encounters"]:
        if e["map"] not in ECO_BY_MAP:
            continue
        eco = ECO_BY_MAP[e["map"]]
        pool = POOLS["deepsea"] if eco == "deepsea" else POOLS["ocean"]
        for t in ("water_mons", "fishing_mons"):
            b = e.get(t)
            if not b or not b.get("mons"):
                continue
            for i, mon in enumerate(b["mons"]):
                sp = mon["species"].replace("SPECIES_", "")
                ty = types.get(sp) or types.get(resolve(sp), [])
                if not ty:
                    continue
                if {"WATER", "FLYING", "DRAGON"} & set(ty):
                    continue
                rep = pool[(i + len(e["map"])) % len(pool)]
                fixed.append((e["map"], t, sp, rep))
                mon["species"] = "SPECIES_" + rep
    return fixed


def load_species_set():
    txt = open(SPECIES_H, encoding="utf-8", errors="ignore").read()
    return set(re.findall(r"\bSPECIES_([A-Z0-9_]+)", txt))


def pick_new(eco, offset, count, pool_override=None):
    pool = pool_override or POOLS[eco]
    return [pool[(offset + i) % len(pool)] for i in range(count)]


def natives(mons, limit):
    """按出现次数降序取原生种（保持稳定顺序）"""
    cnt = collections.Counter(m["species"].replace("SPECIES_", "") for m in mons)
    order = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
    names = [k for k, _ in order]
    out = []
    while len(out) < limit:
        out.append(names[len(out) % len(names)])
    return out


def retint_block(mons, template, eco, offset, new_pool=None):
    if len(mons) != len(template):
        return mons, []
    nat = natives(mons, 4)
    new = pick_new(eco, offset, 3, new_pool)
    mapping = {"N1": nat[0], "N2": nat[1], "N3": nat[2], "N4": nat[3],
               "A": new[0], "B": new[1], "C": new[2]}
    out = []
    changed = []
    for old, slot in zip(mons, template):
        name = mapping[slot]
        species = "SPECIES_" + name
        if species != old["species"]:
            changed.append((old["species"], species))
        item = dict(old)
        item["species"] = species
        out.append(item)
    return out, changed


def main():
    apply = "--apply" in sys.argv
    have = load_species_set()
    for eco, pool in POOLS.items():
        miss = [s for s in pool if s not in have]
        if miss:
            print("ERROR: 物种不存在 %s: %s" % (eco, miss))
            return 1

    d = json.load(open(JSON_PATH, encoding="utf-8"))
    group = d["wild_encounter_groups"][0]
    fields = [f["type"] for f in group["fields"]]

    eco_hits = collections.Counter()
    touched = 0
    skipped_maps = []
    new_species = collections.Counter()
    report = []

    for e in group["encounters"]:
        mp = e["map"]
        if mp in SKIP:
            continue
        eco = ECO_BY_MAP.get(mp)
        if not eco:
            skipped_maps.append(mp)
            continue
        idx = eco_hits[eco]
        eco_hits[eco] += 1
        offset = idx * 3
        did = False
        detail = []
        for t in fields:
            blk = e.get(t)
            if not blk or not blk.get("mons"):
                continue
            if t == "fishing_mons":
                continue
            if t == "land_mons" and eco in ("ocean", "deepsea"):
                continue  # 海图上的陆地是小岛/沙滩，不放鱼
            if t == "land_mons" and len(blk["mons"]) == 12:
                tpl, pool, off = TPL_LAND, None, offset
            elif t == "water_mons" and len(blk["mons"]) == 5:
                tpl = TPL_FIVE
                pool = POOLS["deepsea"] if eco == "deepsea" else POOLS["ocean"]
                off = offset + 1
            elif t == "rock_smash_mons" and len(blk["mons"]) == 5:
                tpl, pool, off = TPL_FIVE, POOLS["cave"], offset + 2
            else:
                continue
            blk["mons"], ch = retint_block(blk["mons"], tpl, eco, off, pool)
            if ch:
                did = True
                for a, b in ch:
                    new_species[b.replace("SPECIES_", "")] += 1
                detail.append("%s: %d 槽" % (t.replace("_mons", ""), len(ch)))
        if did:
            touched += 1
            report.append((mp, eco, ", ".join(detail)))

    print("=== 改造统计 ===")
    print("碰到的地图条目: %d" % touched)
    print("各生态地图数:", dict(eco_hits))
    print("未匹配生态的地图条目: %d" % len(skipped_maps))
    if skipped_maps:
        for m in sorted(set(skipped_maps)):
            print("   !", m)

    print("\n=== 新精灵使用次数 Top 15 ===")
    for s, c in new_species.most_common(15):
        print("  %-14s %d" % (s, c))
    print("用到的不同新物种: %d" % len(new_species))

    print("\n=== 抽样：前 6 条改动 ===")
    for mp, eco, det in report[:6]:
        print("  %-28s [%s] %s" % (mp, eco, det))

    types, resolve = parse_types()
    fixed = clean_water(group, fields, types, resolve)
    if fixed:
        print("\n=== 水域清洗（原版遗留的陆地生物）===")
        for mp, t, a, b in fixed[:10]:
            print("  %-28s %-12s %s -> %s" % (mp, t, a, b))
        print("  合计 %d 处" % len(fixed))

    if apply:
        json.dump(d, open(JSON_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        open(JSON_PATH, "a", encoding="utf-8").write("\n")
        print("\n已写入 %s" % JSON_PATH)
        # 导出新物种清单，供图鉴脚本使用
        all_new = set()
        for e in group["encounters"]:
            for t in fields:
                blk = e.get(t)
                if not blk or not blk.get("mons"):
                    continue
                for m in blk["mons"]:
                    all_new.add(m["species"].replace("SPECIES_", ""))
        json.dump(sorted(all_new), open("design/_wild_species.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("遇敌物种清单 -> design/_wild_species.json (%d 种)" % len(all_new))
    else:
        print("\n(dry-run，未写入。加 --apply 生效)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

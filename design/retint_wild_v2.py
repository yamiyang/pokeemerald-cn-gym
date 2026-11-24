#!/usr/bin/env python3
"""野外遇敌 v2：全量投放。

目标：除传说/幻兽/究极异兽/化石外，**全国图鉴里每一个物种都能在合适的地方遇到**。

算法
----
1. 候选 = 全国图鉴 1007 个物种（同编号取代表形态），排除传说/幻兽/化石
2. 每个物种按属性算出「能活哪些生态」，再按槽位容量均衡分配到 13 个生态
3. 每张图按需替换 6~10 个槽位（至少留 2 个原生种维持地方特色）
4. 稀有度落在权重上：1% 槽放稀有，20% 槽放常见
5. 等级门槛：种族值越高只能出现在越晚的地图；实在放不下就把该槽等级抬到门槛
6. 水面/钓鱼只放水属性；碎岩只放岩/地/钢/格斗/虫
7. 末尾做覆盖率校验，任何目标物种没落位就直接报错退出，不允许静默漏掉

用法
----
    python3 design/retint_wild_v2.py            # 试跑 + 覆盖率报告
    python3 design/retint_wild_v2.py --apply    # 写入
"""

import collections
import importlib.util
import json
import math
import os
import re
import sys

JSON_SRC = "design/_wild_before.json"      # 原始表，不叠加 v1 的改动
JSON_OUT = "src/data/wild_encounters.json"
SPEC_INFO_DIR = "src/data/pokemon/species_info"
SPECIES_H = "include/constants/species.h"
POKEDEX_H = "include/constants/pokedex.h"

# ---------------------------------------------------------------- 生态规则
# 生态 -> (允许属性, 一票否决属性)。否决项对应 audit_encounters.py 的硬规则
ECO_RULES = {
    "grassland": ({"NORMAL", "GRASS", "BUG", "FLYING", "ELECTRIC", "FAIRY",
                   "GROUND", "FIGHTING", "PSYCHIC", "DARK", "POISON"}, set()),
    "forest":    ({"GRASS", "BUG", "POISON", "FAIRY", "GHOST", "DARK", "NORMAL",
                   "FLYING", "PSYCHIC", "FIGHTING", "ICE", "ELECTRIC"}, set()),
    "cave":      ({"ROCK", "GROUND", "POISON", "BUG", "DARK", "GHOST", "STEEL",
                   "PSYCHIC", "FIGHTING", "NORMAL", "DRAGON", "ICE", "FIRE"}, set()),
    "desert":    ({"GROUND", "ROCK", "FIGHTING", "POISON", "BUG", "NORMAL",
                   "STEEL", "DARK", "PSYCHIC", "FLYING", "GHOST"}, {"FIRE"}),
    "volcano":   ({"FIRE", "ROCK", "GROUND", "POISON", "STEEL", "DRAGON",
                   "NORMAL", "DARK"}, {"WATER", "ICE"}),
    "ice":       ({"ICE", "WATER", "STEEL", "NORMAL", "FLYING", "PSYCHIC",
                   "GHOST", "DARK"}, {"FIRE"}),
    "ocean":     ({"WATER", "FLYING", "NORMAL", "ROCK", "GROUND", "FIGHTING", "BUG"}, set()),
    "deepsea":   ({"WATER", "ROCK", "GHOST", "STEEL", "POISON", "DARK"}, set()),
    "highland":  ({"ROCK", "FLYING", "DRAGON", "PSYCHIC", "STEEL", "GROUND",
                   "FIGHTING", "NORMAL", "DARK", "ELECTRIC"}, set()),
    "ship":      ({"GHOST", "WATER", "POISON", "STEEL", "DARK", "NORMAL", "BUG"}, set()),
    "shrine":    ({"GHOST", "DARK", "PSYCHIC", "FAIRY", "POISON", "NORMAL"}, set()),
    "ash":       ({"FIRE", "POISON", "ROCK", "STEEL", "FLYING", "NORMAL", "GROUND"}, set()),
    "safari":    ({"NORMAL", "GRASS", "GROUND", "ROCK", "BUG", "FLYING", "WATER",
                   "FAIRY", "DARK", "FIGHTING", "POISON", "ELECTRIC", "ICE"}, set()),
}
# 生态的「主题属性」：分配时优先保证这类物种占多数
ECO_PRIMARY = {
    "grassland": {"NORMAL", "GRASS"},
    "forest":    {"GRASS", "BUG"},
    "cave":      {"ROCK", "GROUND"},
    "desert":    {"GROUND", "ROCK"},
    "volcano":   {"FIRE"},
    "ice":       {"ICE"},
    "ocean":     {"WATER"},
    "deepsea":   {"WATER"},
    "highland":  {"ROCK", "FLYING", "DRAGON"},
    "ship":      {"GHOST", "WATER"},
    "shrine":    {"GHOST", "PSYCHIC"},
    "ash":       {"FIRE", "POISON"},
    "safari":    {"GRASS", "NORMAL", "BUG"},
}
PRIMARY_QUOTA = 0.6     # 主题属性至少占该生态槽位的 60%

ROCK_TYPES = {"ROCK", "GROUND", "STEEL", "FIGHTING", "BUG"}
AQUATIC_EXTRA = {"WATER", "ICE", "DRAGON"}   # 水面槽容忍的属性

# ---------------------------------------------------------------- 排除名单
LEGEND = set("""
MEWTWO MEW LUGIA HO_OH CELEBI KYOGRE GROUDON RAYQUAZA JIRACHI DEOXYS VICTINI
KELDEO MELOETTA ZERAORA MARSHADOW VOLCANION HOOPA DIANCIE
DIALGA PALKIA GIRATINA ARCEUS PHIONE MANAPHY DARKRAI SHAYMIN
RESHIRAM ZEKROM KYUREM KELDEO MELOETTA GENESECT
XERNEAS YVELTAL ZYGARDE DIANCIE HOOPA VOLCANION
COSMOG COSMOEM SOLGALEO LUNALA NECROZMA MAGEARNA MARSHADOW ZERAORA MELTAN MELMETAL
ZACIAN ZAMAZENTA ETERNATUS KUBFU URSHIFU ZARUDE
REGIELEKI REGIDRAGO GLASTRIER SPECTRIER CALYREX ENAMORUS
KORAIDON MIRAIDON OKIDOGI MUNKIDORI FEZANDIPITI OGERPON TERAPAGOS PECHARUNT
TYPE_NULL SILVALLY REGIGIGAS
ARTICUNO ZAPDOS MOLTRES RAIKOU ENTEI SUICUNE
REGIROCK REGICE REGISTEEL LATIAS LATIOS
AZELF MESPRIT UXIE COBALION TERRAKION VIRIZION
TAPU_KOKO TAPU_LELE TAPU_BULU TAPU_FINI
NIHILEGO BUZZWOLE PHEROMOSA XURKITREE CELESTEELA KARTANA GUZZLORD
POIPOLE NAGANADEL STAKATAKA BLACEPHALON
WALKING_WAKE IRON_LEAVES
""".split())
LEGEND_PREFIX = ("TAPU_", "IRON_")

# 悖谬宝可梦（长得像普通精灵，但按传说处理，不能路边刷）
PARADOX = set("""
GREAT_TUSK SCREAM_TAIL BRUTE_BONNET FLUTTER_MANE SLITHER_WING SANDY_SHOCKS
IRON_TREADS IRON_BUNDLE IRON_HANDS IRON_JUGULIS IRON_MOTH IRON_THORNS
ROARING_MOON IRON_VALIANT WALKING_WAKE IRON_LEAVES
GOUGING_FIRE RAGING_BOLT IRON_BOULDER IRON_CROWN
""".split())

FOSSIL = set("""
OMANYTE OMASTAR KABUTO KABUTOPS AERODACTYL
LILEEP CRADILY ANORITH ARMALDO
SHIELDON BASTIODON CRANIDOS RAMPARDOS
TIRTOUGA CARRACOSTA ARCHEN ARCHEOPS
TYRUNT TYRANTRUM AMAURA AURORUS
""".split())

STARTER = set("""
BULBASAUR IVYSAUR VENUSAUR CHARMANDER CHARMELEON CHARIZARD SQUIRTLE WARTORTLE BLASTOISE
CHIKORITA BAYLEEF MEGANIUM CYNDAQUIL QUILAVA TYPHLOSION TOTODILE CROCONAW FERALIGATR
TREECKO GROVYLE SCEPTILE TORCHIC COMBUSKEN BLAZIKEN MUDKIP MARSHTOMP SWAMPERT
TURTWIG GROTLE TORTERRA CHIMCHAR MONFERNO INFERNAPE PIPLUP PRINPLUP EMPOLEON
SNIVY SERVINE SERPERIOR TEPIG PIGNITE EMBOAR OSHAWOTT DEWOTT SAMUROTT
CHESPIN QUILLADIN CHESNAUGHT FENNEKIN BRAIXEN DELPHOX FROAKIE FROGADIER GRENINJA
ROWLET DARTRIX DECIDUEYE LITTEN TORRACAT INCINEROAR POPPLIO BRIONNE PRIMARINA
GROOKEY THWACKEY RILLABOOM SCORBUNNY RABOOT CINDERACE SOBBLE DRIZZLE INTELEON
SPRIGATITO FLORAGATO MEOWSCARADA FUECOCO CROCALOR SKELEDIRGE QUAXLY QUAXWELL QUAQUAVAL
""".split())

# ---------------------------------------------------------------- 槽位权重
WEIGHTS = {
    ("land_mons", 12): [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1],
    ("water_mons", 5): [60, 30, 5, 4, 1],
    ("rock_smash_mons", 5): [60, 30, 5, 4, 1],
    ("fishing_mons", 10): [40, 40, 10, 5, 1, 1, 1, 1, 1, 1],
}
MIN_KEEP = 1          # 每张图保留几个原生槽（1% 槽，做地方特色）
MAX_REPLACE = {"land_mons": 12, "water_mons": 5,
               "rock_smash_mons": 5, "fishing_mons": 10}


def load_eco_map():
    spec = importlib.util.spec_from_file_location("retint_wild", "design/retint_wild.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ECO_BY_MAP, mod.SKIP


# ---------------------------------------------------------------- 物种解析
def load_roster():
    ptxt = open(POKEDEX_H, encoding="utf-8").read()
    pbody = ptxt[ptxt.index("enum NationalDexOrder"):]
    pbody = pbody[:pbody.index("};")]
    dex_num, n = {}, 0
    for name in re.findall(r"NATIONAL_DEX_(\w+)", pbody):
        if name == "COUNT":
            continue
        dex_num[name] = n
        n += 1

    hdr = open(SPECIES_H, encoding="utf-8").read()
    body = hdr[hdr.index("enum __attribute__"):]
    ids = {}
    for name, val in re.findall(r"SPECIES_(\w+)\s*=\s*([^,\n]+)", body):
        v = val.strip()
        if v.isdigit():
            ids[name] = int(v)

    macro, types_macro, consts = {}, {}, {}
    for fn in os.listdir(SPEC_INFO_DIR):
        if fn.endswith(".h"):
            t = open(os.path.join(SPEC_INFO_DIR, fn), encoding="utf-8", errors="ignore").read()
            for name, val in re.findall(r"#define (\w+_FAMILY_TYPE\d)\s+.*?(TYPE_\w+)\)?\s*$", t, re.M):
                macro[name] = val.replace("TYPE_", "")
            for name, val in re.findall(r"#define ([A-Z_0-9]+)\s+([^\n]+)", t):
                nums = [int(x) for x in re.findall(r"\b(\d{2,3})\b", val)]
                if nums:
                    consts[name] = max(nums)
            for name, args in re.findall(r"#define (\w+_FAMILY_TYPES)\s+\{([^}]*)\}", t):
                if name not in types_macro:      # 首个定义就是当前世代（新）版本
                    types_macro[name] = [x.strip().replace("TYPE_", "")
                                         for x in args.split(",") if x.strip()]

    rec = {}
    for fn in os.listdir(SPEC_INFO_DIR):
        if not fn.endswith(".h"):
            continue
        txt = open(os.path.join(SPEC_INFO_DIR, fn), encoding="utf-8", errors="ignore").read()
        parts = re.split(r"\n\s*\[(SPECIES_\w+)\]\s*=\s*\{", txt)
        for i in range(1, len(parts) - 1, 2):
            key = parts[i].replace("SPECIES_", "")
            body = parts[i + 1]
            ty = re.search(r"\.types\s*=\s*MON_TYPES\(([^)]*)\)", body)
            nd = re.search(r"\.natDexNum\s*=\s*NATIONAL_DEX_(\w+)", body)
            if not nd or nd.group(1) not in dex_num:
                continue
            if ty:
                types = []
                for t in ty.group(1).split(","):
                    t = t.strip().replace("TYPE_", "")
                    if t:
                        types.append(macro.get(t, t))
            else:
                m2 = re.search(r"\.types\s*=\s*(\w+)", body)
                if not m2 or m2.group(1) not in types_macro:
                    continue
                types = types_macro[m2.group(1)]
            stats = 0
            for stat in ("HP", "Attack", "Defense", "Speed", "SpAttack", "SpDefense"):
                mm = re.search(r"\.base%s\s*=\s*([^,\n]+)" % stat, body)
                if not mm:
                    continue
                expr = mm.group(1).strip()
                nums = [int(x) for x in re.findall(r"\d+", expr)]
                if nums:
                    stats += max(nums)      # 三元表达式取现代数值
                else:
                    stats += consts.get(expr, 0)   # 宏常量，如 WIGGLYTUFF_SP_ATK
            evos = re.findall(
                r"EVOLUTION\(\s*\{?\s*(EVO_\w+)\s*,\s*([A-Za-z0-9_]+)\s*,\s*(SPECIES_\w+)", body)
            refs = {r.replace("SPECIES_", "") for r in re.findall(r"SPECIES_(\w+)", body)} - {key}
            flags = set(re.findall(
                r"\.(isSubLegendary|isRestrictedLegendary|isMythical|isUltraBeast|isParadox)\s*=\s*TRUE",
                body))
            rec[key] = {
                "legend": bool(flags),
                "dex": dex_num[nd.group(1)],
                "types": types,
                "stats": stats,
                "evos": [t.replace("SPECIES_", "") for _, _, t in evos],
                "evo_in": [(k2, p, t.replace("SPECIES_", "")) for k2, p, t in evos],
                "refs": refs,
                "id": ids.get(key, 10 ** 6),
            }

    bydex = collections.defaultdict(list)
    for k, v in rec.items():
        bydex[v["dex"]].append((v["id"], k))
    roster = {dex: min(lst)[1] for dex, lst in bydex.items()}

    parents = set()
    for v in rec.values():
        parents |= set(v["evos"]) | v["refs"]

    # 反向索引：谁在几级进化成它（EVO_LEVEL 0 是特殊条件，不是 0 级）
    min_evo = {}
    for v in rec.values():
        for kind, param, tgt in v.get("evo_in", []):
            if kind != "EVO_LEVEL":
                continue
            try:
                lv = int(param)
            except (TypeError, ValueError):
                continue
            if lv <= 0:
                continue
            if tgt not in min_evo or lv < min_evo[tgt]:
                min_evo[tgt] = lv

    return {k: dict(rec[k], evolved=k in parents, min_evo=min_evo.get(k))
            for k in roster.values()}


def match_table(name, table):
    """形态名也能命中：XERNEAS_NEUTRAL -> XERNEAS"""
    if name in table:
        return True
    return any(name.startswith(x + "_") for x in table)


def is_legend(name):
    return (match_table(name, LEGEND) or match_table(name, PARADOX)
            or any(name.startswith(p) for p in LEGEND_PREFIX))


TIER_WEIGHT = {1: 20, 2: 10, 3: 5, 4: 1}   # 稀有度 -> 理想槽位权重
# 稀有度能出现的最高权重槽：稀有种不许挤进 20% 的主槽位
TIER_MAX_WEIGHT = {4: 1, 3: 5, 2: 10, 1: 20}


def level_req(sp):
    st = sp["stats"]
    if st >= 580:
        req = 45
    elif st >= 540:
        req = 40
    elif st >= 500:
        req = 34
    elif st >= 460:
        req = 28
    elif st >= 420:
        req = 20
    elif st >= 380:
        req = 12
    else:
        req = 4
    # 进化形态不能比它的进化等级还早出现：4 级的比比鸟很怪
    lv = sp.get("min_evo")
    if lv:
        req = max(req, lv + 1)
    return req


def tier_of(sp):
    """稀有度：4 最稀有（只给 1% 槽），1 最常见（20% 槽）"""
    if sp.get("starter"):
        return 4            # 御三家只进 1% 槽，路边随手抓就没意思了
    st = sp["stats"]
    if st >= 540:
        return 4
    if st >= 480:
        return 3
    if st >= 400:
        return 2
    return 1


def weight_allowed(sp, w):
    """稀有种不许占据高权重槽，否则 20% 的出怪位全是稀有精灵"""
    return w <= TIER_MAX_WEIGHT[tier_of(sp)]


def fits_eco(types, eco):
    allow, ban = ECO_RULES[eco]
    if ban & set(types):
        return False
    return bool(allow & set(types))


# ---------------------------------------------------------------- 主流程
def main():
    apply = "--apply" in sys.argv
    eco_map, skip_maps = load_eco_map()
    roster = load_roster()
    print("全国图鉴物种: %d" % len(roster))

    targets, excluded = {}, collections.Counter()
    for name, sp in roster.items():
        if sp.get("legend"):
            excluded["传说/幻兽"] += 1
            continue
        if match_table(name, FOSSIL):
            excluded["化石"] += 1
            continue
        if not sp["types"] or sp["stats"] == 0:
            excluded["无数据"] += 1
            continue
        sp["starter"] = name in STARTER
        targets[name] = sp
    starters = sum(1 for n in targets if n in STARTER)
    print("目标物种: %d（含御三家 %d）  排除 %s" % (len(targets), starters, dict(excluded)))

    d = json.load(open(JSON_SRC, encoding="utf-8"))
    group = d["wild_encounter_groups"][0]
    fields = [f["type"] for f in group["fields"]]

    # ---- 槽位
    land, water, rock, fish = [], [], [], []
    for e in group["encounters"]:
        mp = e["map"]
        if mp in skip_maps:
            continue
        eco = eco_map.get(mp)
        if not eco:
            continue
        for t in fields:
            blk = e.get(t)
            if not blk or not blk.get("mons"):
                continue
            n = len(blk["mons"])
            w = WEIGHTS.get((t, n))
            if not w:
                continue
            if t == "land_mons" and eco in ("ocean", "deepsea"):
                continue
            order = sorted(range(n), key=lambda i: (-w[i], i))   # 权重高 -> 低
            for rank, i in enumerate(order):
                mon = blk["mons"][i]
                slot = {"map": mp, "eco": eco, "field": t, "idx": i, "rank": rank,
                        "weight": w[i], "level": mon["max_level"], "block": blk,
                        "min": mon["min_level"], "max": mon["max_level"], "species": None}
                {"land_mons": land, "water_mons": water,
                 "rock_smash_mons": rock, "fishing_mons": fish}[t].append(slot)
    print("槽位：陆地 %d | 水面 %d | 碎岩 %d | 钓鱼 %d"
          % (len(land), len(water), len(rock), len(fish)))

    aquatic = {n for n, s in targets.items() if "WATER" in s["types"]}
    terrestrial = set(targets) - aquatic

    water_eco_cap = collections.Counter(s["eco"] for s in water + fish)
    land_eco_cap = collections.Counter(s["eco"] for s in land)
    load = collections.Counter()

    primary_load = collections.Counter()

    def assign(names, cap, is_aqua):
        out = collections.defaultdict(list)
        rest = []
        ordered = sorted(names, key=lambda x: (-tier_of(targets[x]), -targets[x]["stats"], x))

        # 第一轮：主题属性物种先填主题生态（保留 60% 配额）
        for n in ordered:
            sp = targets[n]
            if is_aqua:
                ecos = [e for e in cap if cap[e] > 0 and e in ("ocean", "deepsea")]
            else:
                ecos = [e for e in cap if fits_eco(sp["types"], e)]
            prim = [e for e in ecos if ECO_PRIMARY[e] & set(sp["types"])]
            prim = [e for e in prim if primary_load[e] < PRIMARY_QUOTA * cap[e]]
            if not prim:
                rest.append(n)
                continue
            e = min(prim, key=lambda x: (primary_load[x] / max(1, cap[x]), -cap[x]))
            primary_load[e] += 1
            load[e] += 1
            out[e].append(n)

        # 第二轮：其余物种填剩余槽位
        for n in rest:
            sp = targets[n]
            if is_aqua:
                ecos = [e for e in cap if cap[e] > 0]
            else:
                ecos = [e for e in cap if fits_eco(sp["types"], e)]
            if not ecos:
                ecos = [e for e in cap if cap[e] > 0][:1]
                if not ecos:
                    continue
            e = min(ecos, key=lambda x: (load[x] / max(1, cap[x]), -cap[x]))
            load[e] += 1
            out[e].append(n)
        return out

    land_by_eco = assign(terrestrial, land_eco_cap, False)
    aqua_by_eco = assign(aquatic, water_eco_cap, True)
    print("分配：陆生 %d / 水生 %d"
          % (sum(len(v) for v in land_by_eco.values()), sum(len(v) for v in aqua_by_eco.values())))

    per_map_used = collections.defaultdict(set)
    unplaced = []

    def place(pool_names, candidates, is_aqua, label):
        names = sorted(pool_names, key=lambda x: (-tier_of(targets[x]), -targets[x]["stats"], x))
        slots = sorted(candidates, key=lambda s: (s["weight"], -s["level"], s["map"], s["idx"]))
        map_cnt = collections.Counter()
        done = 0
        for name in names:
            sp = targets[name]
            req = level_req(sp)
            best = None
            for s in slots:
                if s["species"] is not None:
                    continue
                if s["level"] < req:
                    continue
                if name in per_map_used[s["map"]]:
                    continue
                if not is_aqua and not fits_eco(sp["types"], s["eco"]):
                    continue
                if not weight_allowed(sp, s["weight"]):
                    continue
                key = (abs(s["weight"] - TIER_WEIGHT[tier_of(sp)]), map_cnt[s["map"]],
                       -s["level"], s["map"], s["idx"])
                if best is None or key < best[0]:
                    best = (key, s)
            if best is None:
                unplaced.append(name)
                continue
            s = best[1]
            s["species"] = name
            per_map_used[s["map"]].add(name)
            map_cnt[s["map"]] += 1
            done += 1
        print("  %-16s 物种 %3d → 落位 %3d" % (label, len(names), done))

    for eco, names in land_by_eco.items():
        blocks = len({s["map"] for s in land if s["eco"] == eco})
        k = min(MAX_REPLACE["land_mons"],
                max(6, math.ceil(len(names) / max(1, blocks)) + 1))
        cand = [s for s in land if s["eco"] == eco and s["rank"] < k]
        place(names, cand, False, "陆地/" + eco)

    for eco, names in aqua_by_eco.items():
        cand = [s for s in water + fish if s["eco"] == eco and
                ((s["field"] == "water_mons" and s["rank"] < 4) or
                 (s["field"] == "fishing_mons" and s["rank"] < 5))]
        place(names, cand, True, "水域/" + eco)

    # 碎岩：用岩系物种填充
    rock_pool = sorted((s for s, sp in targets.items() if set(sp["types"]) & ROCK_TYPES),
                       key=lambda x: (tier_of(targets[x]), -targets[x]["stats"], x))
    ri = 0
    for s in sorted(rock, key=lambda x: x["weight"], reverse=True):
        if not rock_pool:
            break
        s["species"] = rock_pool[ri % len(rock_pool)]
        ri += 1

    # ---- 兜底：逐级放宽等级门槛
    relaxed = []
    pending = list(unplaced)
    for floor_delta in (0, 12, 20, 99):
        if not pending:
            break
        nxt = []
        for name in pending:
            sp = targets[name]
            req = level_req(sp)
            if "WATER" in sp["types"]:
                pool = [x for x in water + fish if x["species"] is None
                        and name not in per_map_used[x["map"]]]
            else:
                pool = [x for x in land if x["species"] is None
                        and fits_eco(sp["types"], x["eco"])
                        and name not in per_map_used[x["map"]]]
            floor = max(0, req - floor_delta)
            pool = [x for x in pool if x["level"] >= floor]
            if not pool:
                nxt.append(name)
                continue
            x = max(pool, key=lambda z: (z["level"], -z["weight"]))
            x["species"] = name
            x["min"] = max(x["min"], req)
            x["max"] = max(x["max"], req)
            per_map_used[x["map"]].add(name)
            relaxed.append((name, x["map"], x["level"], req, floor_delta))
        pending = nxt

    if relaxed:
        print("\n放宽等级落位: %d 只" % len(relaxed))
        for n, mp, lv, rq, _delta in relaxed[:8]:
            print("   %-18s → %-26s 原等级 %2d，抬到 %d" % (n, mp, lv, rq))
    if pending:
        print("\n!! 仍无法落位: %d 只 %s" % (len(pending), pending[:20]))

    # ---- 二次铺开：每个物种争取至少 2 个槽位，别只挂在一个 1% 槽上
    def spread():
        have = collections.Counter()
        for x in land + water + rock + fish:
            if x["species"]:
                have[x["species"]] += 1
        maps_of = collections.defaultdict(set)
        for x in land + water + rock + fish:
            if x["species"]:
                maps_of[x["species"]].add(x["map"])

        free = [x for x in land if x["species"] is None]
        map_cnt = collections.Counter()
        for x in land + water + rock + fish:
            if x["species"]:
                map_cnt[x["map"]] += 1
        added = 0
        for name in sorted(have, key=lambda n: have[n]):
            if have[name] >= 2:
                continue
            sp = targets[name]
            req = level_req(sp)
            for x in sorted(free, key=lambda z: (abs(z["weight"] - TIER_WEIGHT[tier_of(sp)]),
                                                 map_cnt[z["map"]],
                                                 z["species"] is not None, -z["level"])):
                if x["species"] is not None:
                    continue
                if x["level"] < req or x["map"] in maps_of[name]:
                    continue
                if name in per_map_used[x["map"]]:
                    continue
                if not weight_allowed(sp, x["weight"]):
                    continue
                if "WATER" in sp["types"]:
                    if not (x["field"] == "land_mons"):
                        continue
                elif not fits_eco(sp["types"], x["eco"]):
                    continue
                x["species"] = name
                per_map_used[x["map"]].add(name)
                maps_of[name].add(x["map"])
                have[name] += 1
                added += 1
                break
            if have[name] < 2 and "WATER" in sp["types"]:
                # 水生种允许进水面/钓鱼
                for x in water + fish:
                    if x["species"] is not None or x["level"] < req:
                        continue
                    if x["map"] in maps_of[name] or name in per_map_used[x["map"]]:
                        continue
                    x["species"] = name
                    per_map_used[x["map"]].add(name)
                    maps_of[name].add(x["map"])
                    have[name] += 1
                    added += 1
                    break
        return added, have

    added, have = spread()
    print("\n二次铺开: +%d 槽（≥2 槽的物种 %d / %d）"
          % (added, sum(1 for v in have.values() if v >= 2), len(have)))

    # ---- 槽驱动补满：剩下的空槽逐个填掉，别让整条路还是老面孔
    # 之前的 place() 是「每个物种找槽」，池子小的生态填不满，低级地图
    # （101 号路最高 3 级 < 等级门槛 4）整张图一个槽都换不掉。这里反过来：
    # 遍历每个空槽，从该生态池里挑人；每张图留一个 1% 槽给原生种做地方特色。
    def fill_rest():
        fixed, lifted = 0, 0
        left = 0
        for is_aqua, slots, by_eco in ((False, land, land_by_eco),
                                       (True, water + fish, aqua_by_eco)):
            for eco, pool_names in by_eco.items():
                pool = [n for n in pool_names if targets[n]["types"]]
                if not pool:
                    continue
                per_map = collections.defaultdict(list)
                for s in slots:
                    if s["species"] is None and s["eco"] == eco:
                        per_map[s["map"]].append(s)
                for mp, free in per_map.items():
                    free.sort(key=lambda s: -s["weight"])
                    keep = free[-1] if len(free) > 1 else None   # 最低权重槽留给原生种
                    for s in free:
                        if s is keep:
                            continue
                        legal = [n for n in pool if is_aqua or fits_eco(targets[n]["types"], eco)]
                        strict = [n for n in legal if weight_allowed(targets[n], s["weight"])]
                        cands = [n for n in (strict or legal) if n not in per_map_used[mp]]
                        ok = [n for n in cands if level_req(targets[n]) <= s["level"]]
                        if not ok:
                            # 早期地图等级太低，允许抬到物种的最低门槛（上限 +8）
                            ok = [n for n in cands if level_req(targets[n]) <= s["level"] + 8]
                            if ok:
                                lifted += 1
                        if not ok:
                            # 该槽没有合适的常见种，放宽稀有度限制
                            loose = [n for n in legal if n not in per_map_used[mp]]
                            ok = [n for n in loose if level_req(targets[n]) <= s["level"] + 8]
                            if ok:
                                lifted += 1
                        if not ok:
                            # 这张图已经没有没出现过的合适物种了，允许重复
                            ok = [n for n in legal if level_req(targets[n]) <= s["level"] + 8]
                            if ok:
                                lifted += 1
                        if not ok:
                            left += 1
                            continue
                        pick = min(ok, key=lambda z: (
                            abs(s["weight"] - TIER_WEIGHT[tier_of(targets[z])]),
                            abs(level_req(targets[z]) - s["level"]),
                            -targets[z]["stats"], z))
                        req = level_req(targets[pick])
                        s["species"] = pick
                        per_map_used[mp].add(pick)
                        if req > s["min"]:
                            s["min"] = req          # 槽的等级下限不能低于物种门槛
                        if req > s["max"]:
                            s["max"] = s["level"] = req
                        fixed += 1
        print("槽驱动补满: +%d 槽（抬等级 %d，仍留空 %d）" % (fixed, lifted, left))
        return left

    fill_rest()

    # ---- 写入
    for s in land + water + rock + fish:
        if s["species"] is None:
            continue
        mon = s["block"]["mons"][s["idx"]]
        mon["species"] = "SPECIES_" + s["species"]
        mon["min_level"] = s["min"]
        mon["max_level"] = s["max"]

    # 水域清洗：水面/钓鱼里非水/飞/龙的物种换掉
    fixed = 0
    placed_aqua = sorted(n for n in aquatic
                         if any(s["species"] == n for s in water + fish))
    aqua_sorted = placed_aqua or sorted(aquatic)
    for e in group["encounters"]:
        for t in ("water_mons", "fishing_mons"):
            b = e.get(t)
            if not b or not b.get("mons"):
                continue
            for j, mon in enumerate(b["mons"]):
                sp = mon["species"].replace("SPECIES_", "")
                ty = targets.get(sp, {}).get("types") or roster.get(sp, {}).get("types")
                if not ty or (set(ty) & AQUATIC_EXTRA):
                    continue
                rep = aqua_sorted[(j + len(e["map"])) % len(aqua_sorted)]
                mon["species"] = "SPECIES_" + rep
                fixed += 1
    if fixed:
        print("水域清洗: %d 处" % fixed)

    # ---- 覆盖
    cnt = collections.Counter()
    for e in group["encounters"]:
        for t in fields:
            b = e.get(t)
            if not b or not b.get("mons"):
                continue
            for mon in b["mons"]:
                cnt[mon["species"].replace("SPECIES_", "")] += 1
    hit = {n for n in cnt if n in targets}
    missing = sorted(set(targets) - hit)
    print("\n=== 覆盖 ===")
    print("目标 %d | 直接遇到 %d | 遗漏 %d | 表内独立物种 %d"
          % (len(targets), len(hit), len(missing), len(cnt)))
    if missing:
        print("  遗漏:", missing[:40])
        for n in missing[:8]:
            lv = [s["level"] for s in land if s["species"] == n]
            print("   ? %-18s %s 门槛 %d 落位等级 %s"
                  % (n, targets[n]["types"], level_req(targets[n]), lv or "无"))

    if apply:
        if missing:
            print("\n仍有遗漏，拒绝写入。")
            return 1
        assert isinstance(d, dict), "d 被覆盖了，别写"
        json.dump(d, open(JSON_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        open(JSON_OUT, "a", encoding="utf-8").write("\n")
        json.dump(sorted(cnt), open("design/_wild_species.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\n已写入 %s（物种清单 design/_wild_species.json）" % JSON_OUT)
    else:
        print("\n(dry-run，未写入；加 --apply 生效)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

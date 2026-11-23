#!/usr/bin/env python3
"""按 NPC 种类生成有章法的随机队伍。

不是纯随机，是「主题约束 + 打击面兜底」：

  1. 种类定主题      Youngster→普通，Kindler→火，Bird Keeper→飞行……
  2. 主题内随机      从该属性池里随机取主怪，每次跑脚本结果不同
  3. 打击面兜底      队伍招式覆盖不了的属性，专门补一只去堵
  4. 招式合法性      只从「该等级已能学会」的招里选，永不超前
  5. 进化合法性      只用到「该等级能进化到」的形态，永不提前

保留不动的：8 馆 + 四天王 + 冠军（手工设计过），以及所有 Leader 重赛版本。

用法
----
    python3 design/randomize_trainers.py --seed 42 --dry-run
    python3 design/randomize_trainers.py --seed 42 --apply
"""
import collections
import json
import os
import random
import re
import sys

ROOT = "."
LEARN_DIR = os.path.join(ROOT, "src/data/pokemon/level_up_learnsets")
SPEC_DIR = os.path.join(ROOT, "src/data/pokemon/species_info")
MOVES_H = os.path.join(ROOT, "src/data/moves_info.h")
PARTY = os.path.join(ROOT, "src/data/trainers.party")

TYPES = ["NORMAL", "FIRE", "WATER", "ELECTRIC", "GRASS", "ICE", "FIGHTING",
         "POISON", "GROUND", "FLYING", "PSYCHIC", "BUG", "ROCK", "GHOST",
         "DRAGON", "DARK", "STEEL", "FAIRY"]

CHART = {
    "NORMAL":   {"ROCK": .5, "GHOST": 0, "STEEL": .5},
    "FIRE":     {"FIRE": .5, "WATER": .5, "GRASS": 2, "ICE": 2, "BUG": 2, "ROCK": .5, "DRAGON": .5, "STEEL": 2},
    "WATER":    {"FIRE": 2, "WATER": .5, "GRASS": .5, "GROUND": 2, "ROCK": 2, "DRAGON": .5},
    "ELECTRIC": {"WATER": 2, "ELECTRIC": .5, "GRASS": .5, "GROUND": 0, "FLYING": 2, "DRAGON": .5},
    "GRASS":    {"FIRE": .5, "WATER": 2, "GRASS": .5, "POISON": .5, "GROUND": 2, "FLYING": .5, "BUG": .5, "ROCK": 2, "DRAGON": .5, "STEEL": .5},
    "ICE":      {"FIRE": .5, "WATER": .5, "GRASS": 2, "ICE": .5, "GROUND": 2, "FLYING": 2, "DRAGON": 2, "STEEL": .5},
    "FIGHTING": {"NORMAL": 2, "ICE": 2, "POISON": .5, "FLYING": .5, "PSYCHIC": .5, "BUG": .5, "ROCK": 2, "GHOST": 0, "DARK": 2, "STEEL": 2, "FAIRY": .5},
    "POISON":   {"GRASS": 2, "POISON": .5, "GROUND": .5, "ROCK": .5, "GHOST": .5, "STEEL": 0, "FAIRY": 2},
    "GROUND":   {"FIRE": 2, "ELECTRIC": 2, "GRASS": .5, "POISON": 2, "FLYING": 0, "BUG": .5, "ROCK": 2, "STEEL": 2},
    "FLYING":   {"ELECTRIC": .5, "GRASS": 2, "FIGHTING": 2, "BUG": 2, "ROCK": .5, "STEEL": .5},
    "PSYCHIC":  {"FIGHTING": 2, "POISON": 2, "PSYCHIC": .5, "DARK": 0, "STEEL": .5},
    "BUG":      {"FIRE": .5, "GRASS": 2, "FIGHTING": .5, "POISON": .5, "FLYING": .5, "PSYCHIC": 2, "GHOST": .5, "DARK": 2, "STEEL": .5, "FAIRY": .5},
    "ROCK":     {"FIRE": 2, "ICE": 2, "FIGHTING": .5, "GROUND": .5, "FLYING": 2, "BUG": 2, "STEEL": .5},
    "GHOST":    {"NORMAL": 0, "PSYCHIC": 2, "GHOST": 2, "DARK": .5},
    "DRAGON":   {"DRAGON": 2, "STEEL": .5, "FAIRY": 0},
    "DARK":     {"FIGHTING": .5, "PSYCHIC": 2, "GHOST": 2, "DARK": .5, "FAIRY": .5},
    "STEEL":    {"FIRE": .5, "WATER": .5, "ELECTRIC": .5, "ICE": 2, "ROCK": 2, "STEEL": .5, "FAIRY": 2},
    "FAIRY":    {"FIRE": .5, "FIGHTING": 2, "POISON": .5, "DRAGON": 2, "DARK": 2, "STEEL": .5},
}

# 种类 -> 主题属性。未列出的按「混合」处理（不限属性，但保证打击面）
THEME = {
    "Bug Catcher": ["BUG"], "Bug Maniac": ["BUG"],
    "Bird Keeper": ["FLYING"],
    "Fisherman": ["WATER"], "Swimmer M": ["WATER"], "Swimmer F": ["WATER"],
    "Tuber M": ["WATER"], "Tuber F": ["WATER"], "Parasol Lady": ["WATER"],
    "Sailor": ["WATER", "FIGHTING"],
    "Hiker": ["ROCK", "GROUND"], "Ruin Maniac": ["GROUND", "ROCK"],
    "Black Belt": ["FIGHTING"], "Battle Girl": ["FIGHTING"],
    "Psychic": ["PSYCHIC"], "Medium": ["GHOST"], "Hex Maniac": ["GHOST"],
    "Kindler": ["FIRE"], "Firebreather": ["FIRE"],
    "Aroma Lady": ["GRASS"], "Beauty": ["GRASS"],
    "Guitarist": ["ELECTRIC"],
    "Dragon Tamer": ["DRAGON"],
    "Ninja Boy": ["POISON", "BUG"],
    "Team Magma": ["FIRE", "GROUND"], "Team Aqua": ["WATER", "DARK"],
    "Lady": ["NORMAL", "FAIRY"], "Gentleman": ["NORMAL", "PSYCHIC"],
    "Pokefan": ["NORMAL", "FAIRY"], "Pkmn Breeder": ["NORMAL"],
    "Youngster": ["NORMAL"], "Lass": ["NORMAL"], "School Kid": ["NORMAL"],
    "Picnicker": ["NORMAL", "GRASS"], "Camper": ["NORMAL", "FIRE"],
    "Twins": ["NORMAL"], "Sr And Jr": ["NORMAL", "PSYCHIC"],
    "Collector": ["BUG", "NORMAL"],
    "Interviewers": ["NORMAL"], "Rich Boy": ["NORMAL", "FAIRY"],
    "Psychic": ["PSYCHIC"],
}

# 保留手工设计的训练师
KEEP = {
    "TRAINER_ROXANNE_1", "TRAINER_BRAWLY_1", "TRAINER_WATTSON_1", "TRAINER_FLANNERY_1",
    "TRAINER_NORMAN_1", "TRAINER_WINONA_1", "TRAINER_TATE_AND_LIZA_1", "TRAINER_JUAN_1",
    "TRAINER_SIDNEY", "TRAINER_PHOEBE", "TRAINER_GLACIA", "TRAINER_DRAKE", "TRAINER_WALLACE",
}
KEEP_CLASS = {"Leader", "Elite Four", "Champion", "Rival"}

# 传说/幻兽/究极异兽不许出现在路人队里
BANNED = re.compile(r"SPECIES_(TYRUNT|TYRANTRUM|AMAURA|AURORUS|ARCHEN|ARCHEOPS|TIRTOUGA|CARRACOSTA|"
                    r"SHIELDON|BASTIODON|CRANIDOS|RAMPARDOS|LILEEP|CRADILY|ANORITH|ARMALDO|AERODACTYL|"
                    r"OMANYTE|OMASTAR|KABUTO|KABUTOPS|MEWTWO|MEW|LUGIA|HO_OH|CELEBI|KYOGRE|GROUDON|RAYQUAZA|JIRACHI|"
                    r"DEOXYS|DIALGA|PALKIA|GIRATINA|ARCEUS|PHIONE|MANAPHY|DARKRAI|SHAYMIN|"
                    r"RESHIRAM|ZEKROM|KYUREM|KELDEO|MELOETTA|GENESECT|XERNEAS|YVELTAL|ZYGARDE|"
                    r"DIANCIE|HOOPA|VOLCANION|TAPU_\w+|COSMOG|COSMOEM|SOLGALEO|LUNALA|NIHILEGO|"
                    r"BUZZWOLE|PHEROMOSA|XURKITREE|CELESTEELA|KARTANA|GUZZLORD|NECROZMA|MAGEARNA|"
                    r"MARSHADOW|ZERAORA|MELTAN|MELMETAL|ZACIAN|ZAMAZENTA|ETERNATUS|KUBFU|URSHIFU|"
                    r"ZARUDE|REGIELEKI|REGIDRAGO|GLASTRIER|SPECTRIER|CALYREX|ENAMORUS|"
                    r"KORAIDON|MIRAIDON|WALKING_WAKE|IRON_LEAVES|OKIDOGI|MUNKIDORI|FEZANDIPITI|"
                    r"OGERPON|TERAPAGOS|PECHARUNT|TYPE_NULL|SILVALLY|REGIGIGAS)")


def parse_learnsets():
    out = {}
    for fn in sorted(os.listdir(LEARN_DIR)):
        if not fn.endswith(".h"):
            continue
        txt = open(os.path.join(LEARN_DIR, fn), encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"static const struct LevelUpMove s(\w+?)LevelUpLearnset\[\] =\s*\{(.*?)\n\};", txt, re.S):
            out[m.group(1).upper()] = sorted(
                (int(l), mv) for l, mv in re.findall(r"LEVEL_UP_MOVE\(\s*(\d+),\s*(MOVE_\w+)\)", m.group(2)))
    return out


def parse_species():
    sp = {}
    for fn in sorted(os.listdir(SPEC_DIR)):
        if not fn.endswith(".h"):
            continue
        txt = open(os.path.join(SPEC_DIR, fn), encoding="utf-8", errors="ignore").read()
        parts = re.split(r"\n\s*\[(SPECIES_\w+)\]\s*=\s*\{", txt)
        for i in range(1, len(parts) - 1, 2):
            key, body = parts[i], parts[i + 1]
            nm = re.search(r"\.speciesName\s*=\s*_\w*\(\s*\"([^\"]+)\"", body)
            ty = re.search(r"\.types\s*=\s*MON_TYPES\(([^)]*)\)", body)
            abl = re.search(r"\.abilities\s*=\s*\{([^}]*)\}", body)
            stats = sum(int(v) for v in re.findall(r"\.base(?:HP|Attack|Defense|Speed|SpAttack|SpDefense)\s*=\s*(\d+)", body))
            evos = re.findall(r"EVOLUTION\(\s*\{?\s*(EVO_\w+)\s*,\s*([A-Za-z0-9_]+)\s*,\s*(SPECIES_\w+)", body)
            if not ty:
                continue
            refs = {"SPECIES_" + x for x in re.findall(r"SPECIES_(\w+)", body)}
            sp[key] = {
                "refs": refs,
                "name": nm.group(1) if nm else "",
                "types": [t.strip().replace("TYPE_", "") for t in ty.group(1).split(",") if t.strip()],
                "abilities": [a.strip() for a in abl.group(1).split(",")] if abl else [],
                "stats": stats,
                "evos": evos,
            }
    return sp


def parse_moves():
    txt = open(MOVES_H, encoding="utf-8", errors="ignore").read()
    out = {}
    parts = re.split(r"\n    \[(MOVE_[A-Z0-9_]+)\]\s*=\s*\n?\s*\{", txt)
    for i in range(1, len(parts) - 1, 2):
        key, body = parts[i], parts[i + 1]
        ty = re.search(r"\.type\s*=\s*(TYPE_\w+)", body)
        pw = re.search(r"\.power\s*=\s*[^,\n]*?(\d+)", body)
        cat = re.search(r"\.damageClass\s*=\s*DAMAGE_CATEGORY_(\w+)", body)
        if not ty:
            continue
        out[key] = {
            "type": ty.group(1).replace("TYPE_", ""),
            "power": int(pw.group(1)) if pw else 0,
            "cat": cat.group(1) if cat else "STATUS",
        }
    return out


def main():
    seed = 42
    for i, a in enumerate(sys.argv):
        if a == "--seed" and i + 1 < len(sys.argv):
            seed = int(sys.argv[i + 1])
    apply = "--apply" in sys.argv
    rng = random.Random(seed)

    print("解析源码 ...")
    LEARN = parse_learnsets()
    SPEC = parse_species()
    MOVES = parse_moves()
    print(f"  招式 {len(MOVES)} | 物种 {len(SPEC)} | 学招表 {len(LEARN)}")

    # 基础形态：没有 EVO_LEVEL 前身
    has_parent = set()
    for k, v in SPEC.items():
        for kind, val, tgt in v["evos"]:
            has_parent.add(tgt)
        if v.get("refs"):
            has_parent |= v["refs"] - {k}
    BASES = [k for k in SPEC if k not in has_parent and k.replace("SPECIES_", "") in LEARN
             and not BANNED.search(k) and 200 <= SPEC[k]["stats"] <= 560]

    # 主题池
    pool_cache = {}

    def pools_for(types):
        key = tuple(types)
        if key in pool_cache:
            return pool_cache[key]
        themed, other = [], []
        for b in BASES:
            st = set(SPEC[b]["types"])
            if st & set(types) and SPEC[b]["stats"] >= 250:
                themed.append(b)
            other.append(b)
        pool_cache[key] = themed
        return themed

    def best_form(base, level):
        """沿等级进化链往上走，返回该等级能到的最高形态"""
        cur = base
        for _ in range(3):
            nxt = [t for kind, val, t in SPEC[cur]["evos"]
                   if kind == "EVO_LEVEL" and val.isdigit() and 0 < int(val) <= level]
            if not nxt:
                break
            cur = nxt[0]
        return cur

    def moves_at(sp, level):
        key = sp.replace("SPECIES_", "")
        return [(lv, mv) for lv, mv in LEARN.get(key, []) if lv <= level]

    def coverage(sp, level):
        cov = set()
        for lv, mv in moves_at(sp, level):
            m = MOVES.get(mv)
            if m and m["power"] > 0:
                for t, mult in CHART.get(m["type"], {}).items():
                    if mult >= 2:
                        cov.add(t)
        return cov

    def pick_moves(sp, level, want_types=()):
        av = moves_at(sp, level)
        atk, status = [], []
        for lv, mv in av:
            m = MOVES.get(mv)
            if not m:
                continue
            (atk if m["power"] > 0 else status).append((m["power"], mv, m["type"]))
        own = set(SPEC.get(sp, {}).get("types", []))
        chosen = []
        # 1 个本系最高威力
        stab = sorted([a for a in atk if a[2] in own], key=lambda x: -x[0])
        if stab:
            chosen.append(stab[0][1])
        # 补盲：能打队伍缺口的招
        for t in want_types:
            for p, mv, ty in sorted(atk, key=lambda x: -x[0]):
                if mv not in chosen and CHART.get(ty, {}).get(t, 0) >= 2:
                    chosen.append(mv)
                    break
        # 填满 4 个，优先不同属性
        seen_t = {MOVES[m]["type"] for m in chosen}
        for p, mv, ty in sorted(atk, key=lambda x: -x[0]):
            if len(chosen) >= 4:
                break
            if mv not in chosen and ty not in seen_t:
                chosen.append(mv)
                seen_t.add(ty)
        for p, mv, ty in sorted(atk, key=lambda x: -x[0]):
            if len(chosen) >= 4:
                break
            if mv not in chosen:
                chosen.append(mv)
        if len(chosen) < 4:
            for _p, mv, _ty in status:
                if len(chosen) >= 4:
                    break
                if mv not in chosen:
                    chosen.append(mv)
        return chosen[:4]

    # 解析 party
    raw = open(PARTY, encoding="utf-8").read()
    blocks = re.split(r"(?m)^(=== TRAINER_[A-Z0-9_]+ ===)$", raw)
    header, body = blocks[0], blocks[1:]

    out = [header]
    stats = collections.Counter()
    samples = []

    for i in range(0, len(body), 2):
        marker, seg = body[i], body[i + 1]
        tname = marker.strip("= ").strip()
        cls = re.search(r"^Class: (.+)$", seg, re.M)
        cls = cls.group(1).strip() if cls else ""
        levels = [int(x) for x in re.findall(r"^Level: (\d+)$", seg, re.M)]
        double = "Double Battle: Yes" in seg

        skip = tname in KEEP or cls in KEEP_CLASS or not levels
        if skip:
            out.append(marker + seg)
            stats["kept"] += 1
            continue

        hi = max(levels)
        size = max(1, min(6, len(levels)))
        types = THEME.get(cls, [])

        if types:
            pool = pools_for(types)
            if not pool:
                out.append(marker + seg)
                stats["no_pool"] += 1
                continue
            ace_base = rng.choice(pool)
        else:
            ace_base = rng.choice(BASES)

        team = []
        mate_lv = max(1, hi - 1)
        ace = best_form(ace_base, hi)
        team.append(ace)
        cov = coverage(ace, hi)
        # 补盲
        tries = 0
        while len(team) < size and tries < 40:
            tries += 1
            gaps = set(TYPES) - cov
            if not gaps:
                break
            cands = [b for b in (pools_for(types) if types else BASES)
                     if b not in [t.replace("SPECIES_", "") for t in team]]
            rng.shuffle(cands)
            picked = None
            for b in cands[:60]:
                f = best_form(b, mate_lv)
                if coverage(f, mate_lv) & gaps:
                    picked = f
                    break
            if not picked:
                break
            team.append(picked)
            cov |= coverage(picked, hi)
        # 补足规模
        while len(team) < size:
            b = rng.choice(pools_for(types) if types else BASES)
            f = best_form(b, mate_lv)
            if f not in team:
                team.append(f)

        # 生成段落
        lines = [marker.rstrip("\n")]
        head_block = []
        for ln in seg.split("\n"):
            if ln.startswith(("Name:", "Class:", "Pic:", "Gender:", "Music:", "Double Battle:", "AI:", "Items:")):
                head_block.append(ln)
        lines.extend(head_block)
        lines.append("")
        team = [t for t in team if t in SPEC]
        team_gaps = set(TYPES) - cov
        for k, sp in enumerate(team):
            lvl = hi if k == 0 else mate_lv
            mv = pick_moves(sp, lvl, list(team_gaps)[:2])
            abl = (SPEC.get(sp, {}).get("abilities") or ["ABILITY_NONE"])[0]
            lines.append(sp + (" @ Sitrus Berry" if hi >= 35 and k == 0 else ""))
            lines.append("Ability: " + abl.replace("ABILITY_", "").title().replace("_", " "))
            lines.append("Level: %d" % lvl)
            iv = 20 if hi < 25 else 24 if hi < 40 else 28
            lines.append("IVs: " + " / ".join("%d %s" % (iv, st) for st in ("HP", "Atk", "Def", "SpA", "SpD", "Spe")))
            for m in mv:
                lines.append("- " + m.replace("MOVE_", "").replace("_", " ").title())
            lines.append("")
        out.append("\n".join(lines).rstrip() + "\n\n")
        stats["changed"] += 1
        if len(samples) < 3:
            samples.append((tname, cls, hi, types, [t.replace("SPECIES_", "") for t in team]))

    print("\n=== 统计 ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("\n=== 抽样 ===")
    for t, c, lv, ty, tm in samples:
        print(f"  {t} [{c}] Lv{lv} 主题{ty or '混合'}")
        print(f"    队伍: {', '.join(tm)}")

    new_txt = "".join(out)
    if apply:
        open(PARTY + ".bak2", "w", encoding="utf-8").write(raw)
        open(PARTY, "w", encoding="utf-8").write(new_txt)
        print("\n已写入 %s（备份 .bak2）" % PARTY)
    else:
        print("\n(dry-run，未写入)")


if __name__ == "__main__":
    main()

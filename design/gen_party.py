# -*- coding: utf-8 -*-
"""把 teams_spec.json / teams_e4.json 写进 trainers.party。
只替换 13 个目标训练师段落，其余 842 个原样保留。
"""
import json, os, re, shutil, sys

BASE = r'D:\cn_base'
PARTY = os.path.join(BASE, 'src', 'data', 'trainers.party')
NAMES = r'D:\tools\names.json'

SP = json.load(open(NAMES, encoding='utf-8'))
SPMAP, MVMAP = SP['sp'], SP['mv']

spec = json.load(open(r'D:\tools\teams_spec.json', encoding='utf-8'))['teams']
e4 = json.load(open(r'D:\tools\teams_e4.json', encoding='utf-8'))['teams']

# 与 json 里 mons 顺序一一对应的特性
ABIL = [
    ["Sturdy", "Purifying Salt", "Tough Claws", "Sturdy"],                       # G1 杜娟
    ["Iron Fist", "Dry Skin", "Pure Power", "Thick Fat"],                        # G2 藤树
    ["Compound Eyes", "Dry Skin", "Motor Drive", "Static"],                      # G3 铁旋
    ["Simple", "Flash Fire", "Drought", "Chlorophyll", "Sheer Force"],           # G4 亚莎
    ["Vital Spirit", "Color Change", "Tangled Feet", "Truant"],                  # G5 千里
    ["Immunity", "Sturdy", "Limber", "Guts", "Natural Cure"],                    # G6 娜琪
    ["Levitate", "Trace", "Magic Guard", "Levitate", "Levitate"],                # G7 小枫小南
    ["Drizzle", "Hydration", "Swift Swim", "Rain Dish", "Swift Swim"],           # G8 亚当
    ["Pressure", "Insomnia", "Water Absorb", "Battle Armor"],                    # E4-1 花月
    ["Insomnia", "Pressure", "Levitate", "Pressure"],                            # E4-2 芙蓉
    ["Snow Cloak", "Snow Warning", "Ice Body", "Thick Fat"],                     # E4-3 波妮
    ["Levitate", "Natural Cure", "Rough Skin", "Intimidate"],                    # E4-4 源治
    ["Drizzle", "Swift Swim", "Swift Swim", "Marvel Scale", "Intimidate"],       # CH 米可利
]

# 道具（None 表示不持有）
ITEMS = [
    [None, None, None, "Oran Berry"],
    [None, None, None, None],
    [None, None, None, None],
    [None, None, "Heat Rock", None, "Charcoal"],
    [None, None, None, None],
    [None, None, None, None, None],
    [None, None, None, None, None],
    ["Damp Rock", None, None, None, None],
    [None, None, None, None],
    [None, None, None, None],
    [None, None, None, None],
    [None, None, None, None],
    [None, None, None, None, None],
]

TARGETS = [
    ("TRAINER_ROXANNE_1", "Check Bad Move / Try To Faint", 20),
    ("TRAINER_BRAWLY_1", "Check Bad Move / Try To Faint", 20),
    ("TRAINER_WATTSON_1", "Check Bad Move / Try To Faint / Check Viability", 24),
    ("TRAINER_FLANNERY_1", "Check Bad Move / Try To Faint / Check Viability", 24),
    ("TRAINER_NORMAN_1", "Check Bad Move / Try To Faint / Check Viability", 24),
    ("TRAINER_WINONA_1", "Check Bad Move / Try To Faint / Check Viability", 28),
    ("TRAINER_TATE_AND_LIZA_1", "Check Bad Move / Try To Faint / Check Viability / HP Aware", 28),
    ("TRAINER_JUAN_1", "Check Bad Move / Try To Faint / Check Viability / HP Aware", 28),
    ("TRAINER_SIDNEY", "Check Bad Move / Try To Faint / Check Viability / HP Aware / Smart Switching", 31),
    ("TRAINER_PHOEBE", "Check Bad Move / Try To Faint / Check Viability / HP Aware / Smart Switching", 31),
    ("TRAINER_GLACIA", "Check Bad Move / Try To Faint / Check Viability / HP Aware / Smart Switching", 31),
    ("TRAINER_DRAKE", "Check Bad Move / Try To Faint / Check Viability / HP Aware / Smart Switching", 31),
    ("TRAINER_WALLACE", "Check Bad Move / Try To Faint / Check Viability / HP Aware / Smart Switching", 31),
]

TEAMS = spec + e4


def mon_lines(mon, ability, item, ivs):
    key = 'SPECIES_' + mon['species']
    if key not in SPMAP:
        raise KeyError('unknown species: ' + mon['species'])
    name = SPMAP[key]
    head = name if not item else '%s @ %s' % (name, item)
    out = [head, 'Level: %d' % mon['level']]
    if ability:
        out.append('Ability: ' + ability)
    out.append('IVs: %d HP / %d Atk / %d Def / %d SpA / %d SpD / %d Spe'
               % (ivs, ivs, ivs, ivs, ivs, ivs))
    for mv in mon['moves']:
        mk = 'MOVE_' + mv
        if mk not in MVMAP:
            raise KeyError('unknown move: ' + mv)
        out.append('- ' + MVMAP[mk])
    return out


def build_body(team, idx, ivs):
    blocks = []
    for j, mon in enumerate(team['mons']):
        blocks.append(mon_lines(mon, ABIL[idx][j], ITEMS[idx][j], ivs))
    lines = []
    for b in blocks:
        lines.extend(b)
        lines.append('')
    return lines


def main():
    raw = open(PARTY, encoding='utf-8', newline='').read()
    newline = '\r\n' if '\r\n' in raw else '\n'
    lines = raw.replace('\r\n', '\n').split('\n')

    report = []

    # 从后往前替换，避免行号漂移；每轮重新定位，防止索引失效
    for ti in range(len(TARGETS) - 1, -1, -1):
        tname, ai, ivs = TARGETS[ti]
        marker = '=== %s ===' % tname
        found = [i for i, l in enumerate(lines) if l.strip() == marker]
        if len(found) != 1:
            raise RuntimeError('%s found %d times' % (tname, len(found)))
        start = found[0]
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('=== ')), len(lines))

        seg = lines[start:end]
        # header = title 行之后到第一个空行
        blank = next((k for k in range(1, len(seg)) if seg[k].strip() == ''), len(seg))
        header = seg[1:blank]

        new_header = []
        has_ai = False
        for h in header:
            if h.startswith('AI: '):
                new_header.append('AI: ' + ai)
                has_ai = True
            else:
                new_header.append(h)
        if not has_ai:
            new_header.append('AI: ' + ai)

        old_mons = [l for l in seg[blank:] if l.strip() and not l.startswith('Level:')
                    and not l.startswith('IVs:') and not l.startswith('-') and not l.startswith('Ability:')]
        body = build_body(TEAMS[ti], ti, ivs)

        new_seg = [seg[0]] + new_header + [''] + body
        report.append((tname, len(old_mons), len(TEAMS[ti]['mons'])))
        lines[start:end] = new_seg

    out = newline.join(lines)
    if not os.path.exists(PARTY + '.orig'):
        shutil.copy2(PARTY, PARTY + '.orig')
    open(PARTY, 'w', encoding='utf-8', newline='').write(out)

    for t, a, b in report:
        print('%-26s %d mons -> %d mons' % (t, a, b))
    print('total lines:', len(lines))


if __name__ == '__main__':
    main()

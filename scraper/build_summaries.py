"""
Builds accurate aggregated summary documents for the vector DB.

Key improvement over v1:
- Category extracted from URL path (reliable, not keyword guessing)
- Every weapon labeled [Base Game], [DLC], or [Convergence New]
- Stats and location parsed from page text per weapon
- Summaries generated per category AND per stat focus
- Master "all new weapons" list

Run: python scraper/build_summaries.py
Output: data/raw/summaries.json
"""

import json
import re
from pathlib import Path
from collections import defaultdict

CONVERGENCE_FILE = Path("data/raw/convergence.json")
FANAPI_FILE      = Path("data/raw/fanapi.json")
OUT_FILE         = Path("data/raw/summaries.json")

# ── Helpers ────────────────────────────────────────────────────────────────

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

def category_from_url(url: str) -> str | None:
    """Extract weapon sub-category from URL path, e.g. 'greatswords'."""
    parts = url.rstrip("/").split("/")
    for marker in ("weapons", "shields", "spell-casting-tools"):
        if marker in parts:
            idx = parts.index(marker)
            # Need at least one more segment after the marker (the sub-category)
            # and at least one after that (the item name) to be an item page
            if idx + 2 < len(parts):
                return parts[idx + 1].replace("-", " ").title()
            elif idx + 1 < len(parts):
                # Only one segment after marker = category index page, skip
                return None
    for marker in ("spells", "sorceries", "incantations", "spell-runes"):
        if marker in parts:
            idx = parts.index(marker)
            if idx + 1 < len(parts):
                return "Spell Runes" if "rune" in url else parts[idx].replace("-", " ").title()
    return None

def is_item_page(page: dict) -> bool:
    """Return True only for individual item pages, not category index pages."""
    if len(page["text"]) < 250:
        return False
    # Category index pages tend to have very short path depth
    parts = page["url"].rstrip("/").split("/")
    # Must be at least 5 deep: scheme + '' + domain + section + category + item
    return len(parts) >= 6

def parse_location(text: str) -> str:
    m = re.search(r"How to Obtain\s+(.+?)(?:Notes|Copyright|For detailed|$)",
                  text, re.IGNORECASE | re.DOTALL)
    if m:
        loc = m.group(1).strip()
        loc = re.sub(r"\s+", " ", loc)
        return loc[:180]
    return ""

def parse_stats(text: str) -> dict[str, int]:
    """Parse STR/DEX/INT/FAI/ARC requirements from page text."""
    m = re.search(
        r"Attribute Requirements\s+([\d]+)\s+([\d]+)\s+([\d]+)\s+([\d\-]+)\s+([\d\-]+)",
        text
    )
    if not m:
        return {}
    names = ["STR", "DEX", "INT", "FAI", "ARC"]
    result = {}
    for name, val in zip(names, m.groups()):
        if val.isdigit() and int(val) > 0:
            result[name] = int(val)
    return result

def dominant_stats(stats: dict[str, int]) -> list[str]:
    """Return the 1-2 stats with meaningful requirements (>=10)."""
    meaningful = {k: v for k, v in stats.items() if v >= 10}
    if not meaningful:
        return []
    sorted_stats = sorted(meaningful, key=lambda k: meaningful[k], reverse=True)
    return sorted_stats[:2]


# ── Boss extraction from changelog ────────────────────────────────────────

def build_boss_summaries(changelog_text: str) -> list[dict]:
    """
    Parse the changelog for new/replaced/removed bosses and build summary docs.
    The convergence site has no /bosses/ section so changelog is the only source.
    """

    # Explicitly known new bosses extracted from changelog analysis
    NEW_BOSSES = [
        ("Bloodflame Dragon Sanguivaros", "Mohgwyn Palace"),
        ("The Rotten Monk",              "South Caelid Erdtree Portal (replaces Kindred of Rot)"),
        ("Charred Banished Knight",      "East Mt. Gelmir Erdtree Portal (replaces Colossal Finger Creeper)"),
        ("Spiritshaper Caimar",          "Has its own arena — rewards Caimar's Remembrance"),
        ("Einar, Ice Guardian",          "Has its own arena — rewards Einar's Remembrance"),
        ("Goras, Scourge of Dreams",     "Has its own arena and theme"),
        ("Scion of the Sealed God",      "Lake of Rot"),
        ("Godskin Matriarch",            "Top of Divine Tower of Liurnia — rewards Godskin Flayer weapon (sold by Enia)"),
        ("Dakk, Starcaller Lord",        "Redmane Castle (replaces Crucible Knight & Misbegotten Duo)"),
        ("Sigur, Night's Captain",       "Erdtree Sanctuary (replaces Godfrey spirit)"),
        ("Singing Winged Dame",          "Earthbore Cave (replaces Runebear)"),
        ("Skarde, Crucible's Betrayer",  "Replaces Gideon, the All-Knowing"),
        ("Seera, Blade of the Ancients", "Replaces Godskin Duo"),
        ("Banished Knight Oleg",         "Golden Lineage Evergaol (replaces Godefroy)"),
        ("Bloodhound Knight Gethin",     "Replaces Soldier of Godrick"),
        ("Battlemage Duncan",            "Lakeside Crystal Cave (replaces Bloodhound Knight)"),
        ("Konrad, Pureblood Knight",     "Mohgwyn Palace"),
        ("Erdtree Sentries",             "Multiple locations — guard Erdtree transport portals"),
        ("Abductor Virgin",              "Leyndell courtyard near Fortified Manor (new mini-boss)"),
    ]

    REPLACED_BOSSES = [
        ("Crucible Knight & Misbegotten Warrior (Redmane)", "Dakk, Starcaller Lord"),
        ("Godfrey spirit (Erdtree Sanctuary)",              "Sigur, Night's Captain"),
        ("Runebear (Earthbore Cave)",                       "Singing Winged Dame"),
        ("Gideon Ofnir, the All-Knowing",                   "Skarde, Crucible's Betrayer"),
        ("Godefroy (Golden Lineage Evergaol)",               "Banished Knight Oleg"),
        ("Godskin Duo",                                      "Seera, Blade of the Ancients"),
        ("Soldier of Godrick",                               "Bloodhound Knight Gethin"),
        ("Bloodhound Knight (Lakeside Crystal Cave)",        "Battlemage Duncan"),
        ("Kindred of Rot (South Caelid Erdtree Portal)",     "The Rotten Monk"),
        ("Colossal Finger Creeper (East Mt. Gelmir Portal)", "Charred Banished Knight"),
    ]

    REMOVED_BOSSES = [
        "Fia's Champions",
        "Beastman of Farum Azula (Groveside Cave)",
    ]

    NEW_NPCS = [
        ("Nox Oracle Sadia",       "Selia, Town of Sorcery"),
        ("Volcanist Dist",         "Volcano Manor"),
        ("Snuppet, Servant of Rot","Lake of Rot"),
        ("Stormcaller Curtis",     "Stormveil Castle"),
        ("Necromancer Domo",       "Stormveil Castle"),
        ("Glint Sorcerer Bree",    "Raya Lucaria Academy"),
        ("Fundamentalist Gino",    "Castle Morne"),
        ("Darkmoon Knight Oroboro","Chelona's Rise"),
    ]

    summaries = []

    # Master new bosses list
    lines = [f"CONVERGENCE MOD — All New Bosses Added ({len(NEW_BOSSES)} confirmed)\n"]
    lines.append("These bosses do not exist in the base game and were added by Convergence:\n")
    for name, loc in NEW_BOSSES:
        lines.append(f"  • {name} — {loc}")

    lines.append(f"\nBosses REPLACED by Convergence ({len(REPLACED_BOSSES)}):")
    lines.append("(base game boss removed and replaced with a new one at the same location)")
    for old, new in REPLACED_BOSSES:
        lines.append(f"  • {old}  ->  {new}")

    lines.append(f"\nBosses REMOVED by Convergence ({len(REMOVED_BOSSES)}):")
    for b in REMOVED_BOSSES:
        lines.append(f"  • {b}")

    summaries.append({
        "text":   "\n".join(lines),
        "source": "convergence_summary",
        "title":  "All new bosses added in Convergence",
    })

    # New NPCs list
    npc_lines = [f"CONVERGENCE MOD — New NPCs Added ({len(NEW_NPCS)})\n"]
    npc_lines.append("These class-trainer NPCs are new to Convergence and are not in the base game:")
    for name, loc in NEW_NPCS:
        npc_lines.append(f"  • {name} — {loc}")

    summaries.append({
        "text":   "\n".join(npc_lines),
        "source": "convergence_summary",
        "title":  "All new NPCs added in Convergence",
    })

    return summaries


# ── Main build ─────────────────────────────────────────────────────────────

def build(conv_data: list[dict], fan_data: dict) -> list[dict]:
    # Build base-game name set from fan API
    base_names: set[str] = set()
    for cat in ("weapons", "shields", "armors", "sorceries", "incantations",
                "ashes", "talismans", "spirits", "items", "ammos"):
        for rec in fan_data.get(cat, []):
            base_names.add(norm(rec["name"]))

    # Parse every Convergence item page
    items: list[dict] = []
    for page in conv_data:
        if not is_item_page(page):
            continue
        cat = category_from_url(page["url"])
        if not cat:
            continue

        title = re.sub(r"[–—]\s*Convergence Mod", "", page["title"]).strip()
        if not title or title.lower() in ("weapons", "shields", "spells"):
            continue

        location = parse_location(page["text"])
        stats    = parse_stats(page["text"])
        dom      = dominant_stats(stats)

        # Label
        n = norm(title)
        if n in base_names:
            label = "Base Game"
        else:
            label = "Convergence New"   # includes DLC weapons mod incorporates

        items.append({
            "title":    title,
            "category": cat,
            "label":    label,
            "location": location,
            "stats":    stats,
            "dom_stats": dom,
            "url":      page["url"],
        })

    print(f"  Parsed {len(items)} item pages")
    base_count = sum(1 for i in items if i["label"] == "Base Game")
    new_count  = sum(1 for i in items if i["label"] == "Convergence New")
    print(f"  Base Game: {base_count}  |  Convergence New/DLC: {new_count}")

    summaries: list[dict] = []

    # ── 1. Per-category summaries ──────────────────────────────────────────
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_cat[item["category"]].append(item)

    for cat, cat_items in sorted(by_cat.items()):
        base_items = [i for i in cat_items if i["label"] == "Base Game"]
        new_items  = [i for i in cat_items if i["label"] == "Convergence New"]

        lines = [f"CONVERGENCE MOD — All {cat} ({len(cat_items)} total)\n"]

        if new_items:
            lines.append(f"[Convergence New / DLC] ({len(new_items)}):")
            for i in sorted(new_items, key=lambda x: x["title"]):
                stat_str = "/".join(i["dom_stats"]) if i["dom_stats"] else ""
                loc_str  = f" — {i['location'][:80]}" if i["location"] else ""
                stat_tag = f" [{stat_str}]" if stat_str else ""
                lines.append(f"  • {i['title']}{stat_tag}{loc_str}")

        if base_items:
            lines.append(f"\n[Base Game] ({len(base_items)}):")
            for i in sorted(base_items, key=lambda x: x["title"]):
                stat_str = "/".join(i["dom_stats"]) if i["dom_stats"] else ""
                stat_tag = f" [{stat_str}]" if stat_str else ""
                lines.append(f"  • {i['title']}{stat_tag}")

        summaries.append({
            "text":   "\n".join(lines),
            "source": "convergence_summary",
            "title":  f"All {cat} in Convergence",
        })

    # ── 2. All new weapons master list ────────────────────────────────────
    new_all = [i for i in items if i["label"] == "Convergence New"]
    by_cat_new: dict[str, list[str]] = defaultdict(list)
    for i in new_all:
        stat_str = "/".join(i["dom_stats"]) if i["dom_stats"] else "?"
        loc = i["location"][:60] if i["location"] else "location unknown"
        by_cat_new[i["category"]].append(f"{i['title']} [{stat_str}] — {loc}")

    lines = [f"CONVERGENCE MOD — All New Weapons & Items Added ({len(new_all)} total)\n"]
    for cat in sorted(by_cat_new):
        lines.append(f"\n{cat}:")
        for entry in sorted(by_cat_new[cat]):
            lines.append(f"  • {entry}")

    summaries.append({
        "text":   "\n".join(lines),
        "source": "convergence_summary",
        "title":  "All new weapons added in Convergence",
    })

    # ── 3. Stat-focus summaries ────────────────────────────────────────────
    STAT_GROUPS = {
        "INT":     ["INT"],
        "FTH":     ["FAI"],
        "INT/FTH": ["INT", "FAI"],
        "STR":     ["STR"],
        "DEX":     ["DEX"],
        "STR/DEX": ["STR", "DEX"],
        "ARC":     ["ARC"],
        "FTH/ARC": ["FAI", "ARC"],
        "INT/ARC": ["INT", "ARC"],
    }

    for group_name, required_stats in STAT_GROUPS.items():
        matching = [
            i for i in items
            if all(s in i["stats"] and i["stats"][s] >= 10 for s in required_stats)
        ]
        if len(matching) < 3:
            continue

        new_m  = [i for i in matching if i["label"] == "Convergence New"]
        base_m = [i for i in matching if i["label"] == "Base Game"]

        lines = [f"CONVERGENCE MOD — {group_name} Weapons ({len(matching)} total)\n"]

        if new_m:
            lines.append(f"[Convergence New / DLC] ({len(new_m)}):")
            for i in sorted(new_m, key=lambda x: x["title"]):
                loc = i["location"][:70] if i["location"] else ""
                loc_str = f" — {loc}" if loc else ""
                lines.append(f"  • {i['title']} [{i['category']}]{loc_str}")

        if base_m:
            lines.append(f"\n[Base Game] ({len(base_m)}):")
            for i in sorted(base_m, key=lambda x: x["title"]):
                lines.append(f"  • {i['title']} [{i['category']}]")

        summaries.append({
            "text":   "\n".join(lines),
            "source": "convergence_summary",
            "title":  f"Convergence {group_name} weapons",
        })

    # ── 4. Spell rune summaries ────────────────────────────────────────────
    rune_pages = [p for p in conv_data if "/spell-runes/" in p["url"] and is_item_page(p)]
    by_class: dict[str, list[str]] = defaultdict(list)
    for page in rune_pages:
        title = re.sub(r"[–—]\s*Convergence Mod", "", page["title"]).strip()
        # Class is usually in first line: "Class / Spell Type  Frost Witch – Sorceries"
        class_match = re.search(r"Class / Spell Type\s+(.+?)\s+[–—]", page["text"])
        cls = class_match.group(1).strip() if class_match else "Unknown"
        loc_match = re.search(r"Location\s+(.+?)(?:Faint Rune|Copyright|$)", page["text"], re.DOTALL)
        loc = loc_match.group(1).strip()[:100] if loc_match else ""
        by_class[cls].append(f"{title} — {loc}" if loc else title)

    for cls, runes in sorted(by_class.items()):
        text = (f"CONVERGENCE MOD — Spell Runes for {cls} ({len(runes)}):\n"
                + "\n".join(f"  • {r}" for r in runes))
        summaries.append({"text": text, "source": "convergence_summary",
                          "title": f"Convergence spell runes for {cls}"})

    # Master spell rune list
    all_runes = [(re.sub(r"[–—]\s*Convergence Mod","",p["title"]).strip(), p["url"])
                 for p in rune_pages]
    text = (f"CONVERGENCE MOD — All Spell Runes ({len(all_runes)} total)\n"
            + "Spell Runes are unique to Convergence. Each contains 3-4 spells and is found in a specific location.\n"
            + "\n".join(f"  • {t}" for t, _ in sorted(all_runes)))
    summaries.append({"text": text, "source": "convergence_summary",
                      "title": "All Convergence spell runes"})

    # ── 5. Talisman summaries from fan API ─────────────────────────────────
    talismans = fan_data.get("talismans", [])
    if talismans:
        text = (f"BASE GAME — All Talismans ({len(talismans)}):\n"
                + "\n".join(f"  • {t['name']}: {t.get('description','')[:80]}"
                            for t in talismans))
        summaries.append({"text": text, "source": "fanapi_summary",
                          "title": "Base game all talismans"})

    # ── 6. Spirit summons from fan API ─────────────────────────────────────
    spirits = fan_data.get("spirits", [])
    if spirits:
        text = (f"BASE GAME — All Spirit Ashes ({len(spirits)}):\n"
                + "\n".join(f"  • {s['name']}: {s.get('description','')[:80]}"
                            for s in spirits))
        summaries.append({"text": text, "source": "fanapi_summary",
                          "title": "Base game all spirit ashes"})

    # ── 7. Boss summaries from changelog ──────────────────────────────────
    changelog_page = next((p for p in conv_data if "changelogs" in p["url"]), None)
    if changelog_page:
        boss_summaries = build_boss_summaries(changelog_page["text"])
        summaries.extend(boss_summaries)

    # ── 5. Fan API base-game summaries ────────────────────────────────────
    # Weapons by category
    fan_by_cat: dict[str, list[str]] = defaultdict(list)
    for w in fan_data.get("weapons", []):
        scales = ", ".join(s["name"] for s in w.get("scalesWith", []) if s.get("name"))
        entry  = f"{w['name']} (scales: {scales})" if scales else w["name"]
        fan_by_cat[w.get("category", "Unknown")].append(entry)

    for cat, weapons in sorted(fan_by_cat.items()):
        text = (f"BASE GAME — All {cat} ({len(weapons)}):\n"
                + "\n".join(f"  • {w}" for w in sorted(weapons)))
        summaries.append({"text": text, "source": "fanapi_summary",
                          "title": f"Base game {cat}"})

    # All bosses
    bosses = fan_data.get("bosses", [])
    text = (f"BASE GAME — All bosses ({len(bosses)}):\n"
            + "\n".join(f"  • {b['name']} — {b.get('location','?')} ({b.get('region','?')})"
                        for b in bosses))
    summaries.append({"text": text, "source": "fanapi_summary", "title": "Base game all bosses"})

    # All NPCs
    npcs = fan_data.get("npcs", [])
    text = (f"BASE GAME — All NPCs ({len(npcs)}):\n"
            + "\n".join(f"  • {n['name']} — {n.get('location','?')} ({n.get('role','?')})"
                        for n in npcs))
    summaries.append({"text": text, "source": "fanapi_summary", "title": "Base game all NPCs"})

    for spell_type in ("sorceries", "incantations"):
        spells = fan_data.get(spell_type, [])
        text = (f"BASE GAME — All {spell_type} ({len(spells)}):\n"
                + "\n".join(f"  • {s['name']}: {s.get('description','')[:80]}"
                            for s in spells))
        summaries.append({"text": text, "source": "fanapi_summary",
                          "title": f"Base game {spell_type}"})

    return summaries


def main():
    if not CONVERGENCE_FILE.exists() or not FANAPI_FILE.exists():
        print("ERROR: Run scrapers first.")
        return

    print("Loading data ...")
    conv_data = json.loads(CONVERGENCE_FILE.read_text(encoding="utf-8"))
    fan_data  = json.loads(FANAPI_FILE.read_text(encoding="utf-8"))

    print("Building summaries ...")
    summaries = build(conv_data, fan_data)

    OUT_FILE.write_text(json.dumps(summaries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. {len(summaries)} summary documents -> {OUT_FILE}")


if __name__ == "__main__":
    main()

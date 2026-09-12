#!/usr/bin/env python3
"""Pull Trans Caledonia results from my.raceresult.com and write data/results.json.

Run again after each race day:  python3 scripts/fetch_results.py
"""
import json, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVENT_ID = 413373
PAGE = "live"
OVERALL_LIST = "1 Trans Results|Live Overall"
DAY_LIST = "1 Trans Results|Day Results dynamic across page to select day1 2 3 4 523"
# Day 3 stage 6 (global stage 16) was cancelled, times shown but not counted.
CANCELLED = {(3, 6)}
OUT = Path(__file__).resolve().parent.parent / "data" / "results.json"


def get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_time(s):
    """'1:41:36,45' / '2:08,46' / '+40,97' / '-' -> seconds (float) or None."""
    if not s or s.strip() in ("-", ""):
        return None
    s = s.strip().lstrip("+").replace(",", ".")
    parts = s.split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        return None
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return round(total, 3)


def flatten(data):
    """RaceResult groups rows in nested dicts keyed '#1_Male' etc. Yield (path, row)."""
    if isinstance(data, list):
        for row in data:
            yield [], row
    else:
        for key, val in data.items():
            label = key.split("_", 1)[1] if "_" in key else key
            for path, row in flatten(val):
                yield [label] + path, row


def main():
    cfg = get(f"https://my.raceresult.com/{EVENT_ID}/{PAGE}/config", {"lang": "en"})
    key = cfg["key"]
    server = "https://" + cfg.get("server", "my.raceresult.com")
    base = f"{server}/{EVENT_ID}/{PAGE}/list"
    common = {"key": key, "page": PAGE, "r": "all", "l": 0}

    riders = {}

    # Overall standings
    ov = get(base, {**common, "listname": OVERALL_LIST, "contest": 0})
    cols = ov["DataFields"]
    idx = {c: i for i, c in enumerate(cols)}
    for path, row in flatten(ov["data"]):
        bib = int(row[idx["BIB"]])
        name = re.sub(r"^\d+\s*\.", "", row[idx["Displaying"]]).strip()
        flag = re.search(r"flags/([A-Z]+)\.svg", row[idx["NATION.FLAG"]] or "")
        riders[bib] = {
            "bib": bib,
            "name": name,
            "gender": "f" if path and path[0].lower().startswith("f") else "m",
            "category": row[idx["Category"]],
            "nation": flag.group(1) if flag else "",
            "overall": {
                "rank": int(re.sub(r"\D", "", row[idx["TotalRank.th"]]) or 0) or None,
                "time": parse_time(row[idx["[TIME6]"]]),
                "gap": 0.0 if row[idx["GapTimeTop(6;9)"]].strip() == "-" else parse_time(row[idx["GapTimeTop(6;9)"]]),
                "daysRidden": int(row[6] or 0),
                "stagesRidden": int(row[7] or 0),
                "penalty": row[8],
            },
            "days": {},
        }

    # Per day stage results; selector ids 1-5 are days 1-5, id 9 is day 6
    selectors = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (9, 6)]
    days_meta = []
    for sel, day in selectors:
        d = get(base, {**common, "listname": DAY_LIST, "contest": 1, "selectorResult": sel})
        # data columns: BIB, ID, AUTORANK, Displaying, then Stage/Pos pairs ..., Stages, Penalty, Time, Gap
        rows = list(flatten(d["data"]))
        if not rows:
            continue
        n_stages = 0
        for path, row in rows:
            bib = int(row[0])
            r = riders.get(bib)
            if not r:
                continue
            # explicit mapping: data row = [BIB, ID, AUTORANK, Displaying, S1, P1, S2, P2, ... S7, P7, Stages, Penalty, Time, Gap]
            stages = []
            for si in range(1, 8):
                t = parse_time(row[4 + (si - 1) * 2])
                p = row[5 + (si - 1) * 2]
                rank = int(p.strip("()")) if p.strip("()").isdigit() else None
                if t is not None:
                    n_stages = max(n_stages, si)
                stages.append({"time": t, "rank": rank, "cancelled": (day, si) in CANCELLED} if t is not None else None)
            gap_raw = row[-1].strip()
            r["days"][str(day)] = {
                "rank": int(row[2]) if str(row[2]).isdigit() else None,
                "category": path[1] if len(path) > 1 else r["category"],
                "stagesRidden": int(row[-4]) if str(row[-4]).isdigit() else None,
                "penalty": row[-3],
                "total": parse_time(row[-2]),
                "gap": 0.0 if gap_raw == "-" else parse_time(gap_raw),
                "stages": stages,
            }
        days_meta.append({"day": day, "stages": n_stages,
                          "cancelled": [s for (dd, s) in CANCELLED if dd == day]})

    # trim per rider stage arrays to that day's stage count
    counts = {m["day"]: m["stages"] for m in days_meta}
    for r in riders.values():
        for day, dd in r["days"].items():
            dd["stages"] = dd["stages"][: counts[int(day)]]

    out = {
        "event": cfg.get("eventname"),
        "eventId": EVENT_ID,
        "source": f"https://my.raceresult.com/{EVENT_ID}/live",
        "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eventOver": cfg.get("EventOver", False),
        "note": re.sub(r"<[^>]+>", "", cfg.get("TabConfig", {}).get("InfoText", "") or "").strip(),
        "days": days_meta,
        "riders": sorted(riders.values(), key=lambda r: (r["overall"]["rank"] or 9999, r["bib"])),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"wrote {OUT}: {len(out['riders'])} riders, {len(days_meta)} days, "
          f"{sum(m['stages'] for m in days_meta)} stages")


if __name__ == "__main__":
    sys.exit(main())

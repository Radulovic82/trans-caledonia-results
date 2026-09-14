#!/usr/bin/env python3
"""Turn the photo index plus number/rider analysis into data/photos.json.

    python3 scripts/analyze_photos.py worklist [--limit N] [--json out.json]
        list photos that still need analysis (fileId, local thumbnail path)
    python3 scripts/analyze_photos.py import results.json
        merge analysis results into the local cache (validated, never re-analyses)
    python3 scripts/analyze_photos.py build
        match riders across photos, apply overrides, write data/photos.json
"""
import json, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import photo_common as pc  # noqa: E402

SCENES = {"race-action", "podium", "group", "portrait", "scenery"}
CONF = {"high", "medium", "low"}
FIELDS = ("helmet", "kit", "bike", "other")
THRESHOLD, MARGIN = 0.6, 0.15
WEIGHTS = {"helmet": 0.35, "kit": 0.4, "bike": 0.25}
STOP = {"and", "with", "a", "the", "jersey", "helmet", "bike", "frame", "kit", "shirt", "top", "colour", "color"}


# ---- worklist / import

def pending(index, cache):
    return [fid for fid in index.get("photos", {}) if fid not in cache]


def validate_entry(file_id, entry):
    if not isinstance(entry, dict):
        return None, f"{file_id}: not an object"
    scene = str(entry.get("scene", "")).strip().lower()
    if scene not in SCENES:
        return None, f"{file_id}: bad scene {entry.get('scene')!r}"
    numbers = []
    for n in entry.get("numbers") or []:
        try:
            bib = int(n["bib"]); conf = str(n.get("confidence", "medium")).lower()
        except (KeyError, TypeError, ValueError):
            return None, f"{file_id}: bad number entry {n!r}"
        if conf not in CONF:
            return None, f"{file_id}: bad confidence {conf!r}"
        numbers.append({"bib": bib, "confidence": conf})
    riders = []
    for r in entry.get("riders") or []:
        if not isinstance(r, dict):
            return None, f"{file_id}: bad rider entry {r!r}"
        bib = r.get("bib")
        try:
            bib = int(bib) if bib not in (None, "", "null") else None
        except (TypeError, ValueError):
            return None, f"{file_id}: bad rider bib {r.get('bib')!r}"
        riders.append({"bib": bib, **{f: str(r.get(f) or "").strip().lower() for f in FIELDS}})
    return {"analysedAt": entry.get("analysedAt") or pc.now_iso(), "scene": scene, "numbers": numbers, "riders": riders}, None


def import_results(cache, index, results):
    n, errors = 0, []
    for fid, entry in results.items():
        if fid not in index.get("photos", {}):
            errors.append(f"{fid}: not in photo index"); continue
        clean, err = validate_entry(fid, entry)
        if err:
            errors.append(err); continue
        cache[fid] = clean; n += 1
    return n, errors


# ---- identity propagation

def tokens(text):
    return {t for t in "".join(c if c.isalnum() else " " for c in (text or "").lower()).split() if t not in STOP}


def build_profiles(cache):
    prof = {}
    for e in cache.values():
        high = {n["bib"] for n in e["numbers"] if n["confidence"] == "high"}
        for r in e["riders"]:
            if r["bib"] in high:
                p = prof.setdefault(r["bib"], {f: set() for f in FIELDS})
                for f in FIELDS:
                    p[f] |= tokens(r[f])
    return prof


def score(rider, profile):
    total, weight = 0.0, 0.0
    for f, w in WEIGHTS.items():
        a, b = tokens(rider[f]), profile[f]
        if not a or not b:
            continue
        total += w * len(a & b) / len(a | b); weight += w
    return total / weight if weight else 0.0


def _ts(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() if iso else None


def propagate(index, cache, known):
    photos = index["photos"]
    prof = build_profiles(cache)
    seen = []  # (bib, folder, ts, seq) for every number read anywhere
    for fid, e in cache.items():
        meta = photos.get(fid)
        if not meta:
            continue
        for n in e["numbers"]:
            seen.append((n["bib"], meta["folder"], _ts(meta["capturedAt"]), meta["seq"]))
    out = {}
    for fid, e in cache.items():
        meta = photos.get(fid)
        if not meta:
            continue
        ids = [{"bib": n["bib"], "method": "number", "confidence": n["confidence"]} for n in e["numbers"]]
        taken = {n["bib"] for n in e["numbers"]}
        ts, seq = _ts(meta["capturedAt"]), meta["seq"]
        for r in e["riders"]:
            if r["bib"] is not None:
                continue
            scores = {}
            for bib, p in prof.items():
                if bib in taken or bib not in known:
                    continue
                s = score(r, p)
                near = [x for x in seen if x[0] == bib and x[1] == meta["folder"]]
                if ts and any(x[2] and abs(x[2] - ts) <= 90 for x in near):
                    s += 0.3
                elif ts and any(x[2] and abs(x[2] - ts) <= 600 for x in near):
                    s += 0.15
                if seq is not None and any(x[3] is not None and abs(x[3] - seq) <= 3 for x in near):
                    s += 0.2
                scores[bib] = min(s, 1.0)
            ranked = sorted(scores.items(), key=lambda kv: -kv[1])
            if ranked and ranked[0][1] >= THRESHOLD and (len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= MARGIN):
                bib, s = ranked[0]
                ids.append({"bib": bib, "method": "inferred", "confidence": round(s, 2)})
                taken.add(bib)
        out[fid] = ids
    return out


# ---- manifest

def apply_overrides(photo, ov):
    if not ov:
        return photo
    if ov.get("hide"):
        return None
    p = dict(photo)
    ids = [i for i in p["identifications"] if i["bib"] not in set(ov.get("remove_bibs", []))]
    for b in ov.get("add_bibs", []):
        if int(b) not in {i["bib"] for i in ids}:
            ids.append({"bib": int(b), "method": "manual", "confidence": "high"})
    p["identifications"] = ids
    p["bibs"] = sorted({i["bib"] for i in ids})
    if ov.get("photographer"):
        p["photographer"] = ov["photographer"]
    return p


def _day_key(day):
    return (0, int(day)) if str(day).isdigit() else (1, str(day))


def build_manifest(index, cache, overrides, results):
    known = set(pc.known_bibs(results))
    ids_by = propagate(index, cache, known)
    summary = {"analysed": 0, "byNumber": 0, "inferred": 0, "unidentified": 0, "unmatched": 0, "hidden": 0}
    photos = []
    for fid, meta in index["photos"].items():
        e = cache.get(fid)
        if not e:
            continue
        summary["analysed"] += 1
        ids = [i for i in ids_by.get(fid, []) if i["bib"] in known]
        unmatched = sorted({n["bib"] for n in e["numbers"] if n["bib"] not in known})
        summary["byNumber"] += sum(i["method"] == "number" for i in ids)
        summary["inferred"] += sum(i["method"] == "inferred" for i in ids)
        summary["unmatched"] += len(unmatched)
        identified = {i["bib"] for i in ids} | set(unmatched)
        unid = max(0, len(e["riders"]) - len(identified)) if e["riders"] else 0
        summary["unidentified"] += unid
        photo = {"fileId": fid, "name": meta["name"], "day": meta["day"],
                 "photographer": meta.get("photographer") or pc.photographer_for(meta["folder"], meta["name"]),
                 "capturedAt": meta.get("capturedAt"), "bibs": sorted({i["bib"] for i in ids}), "identifications": ids,
                 "unmatched": unmatched, "scene": e["scene"], "unidentifiedRiders": unid}
        photo = apply_overrides(photo, overrides.get(fid))
        if photo is None:
            summary["hidden"] += 1; continue
        photos.append(photo)
    photos.sort(key=lambda p: (_day_key(p["day"]), index["photos"][p["fileId"]]["seq"] or 0, p["name"]))
    return {"generated": pc.now_iso(), "credits": pc.CREDITS, "photos": photos}, summary


# ---- commands

def cmd_worklist(argv):
    index = pc.load_json(pc.INDEX, {"photos": {}})
    cache = pc.load_json(pc.CACHE, {})
    todo = pending(index, cache)
    if "--limit" in argv:
        todo = todo[: int(argv[argv.index("--limit") + 1])]
    rows = [{"fileId": fid, "path": str(pc.TMP / f"{fid}.jpg"), "folder": index["photos"][fid]["folder"],
             "name": index["photos"][fid]["name"]} for fid in todo]
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"{r['fileId']}\t{r['folder']}/{r['name']}\t{r['path']}")
    print(f"{len(rows)} photos to analyse, {len(cache)} already done", file=sys.stderr)
    return 0


def cmd_import(argv):
    index = pc.load_json(pc.INDEX, {"photos": {}})
    cache = pc.load_json(pc.CACHE, {})
    results = json.loads(Path(argv[0]).read_text())
    n, errors = import_results(cache, index, results)
    pc.save_json(pc.CACHE, cache)
    for e in errors:
        print("skip", e, file=sys.stderr)
    print(f"imported {n}, skipped {len(errors)}, cache now {len(cache)} photos")
    return 1 if errors else 0


def cmd_build(argv):
    index = pc.load_json(pc.INDEX, {"photos": {}})
    cache = pc.load_json(pc.CACHE, {})
    overrides = {k: v for k, v in pc.load_json(pc.OVERRIDES, {}).items() if not k.startswith("_")}
    results = pc.load_json(pc.RESULTS, {"riders": []})
    manifest, s = build_manifest(index, cache, overrides, results)
    pc.save_json(pc.MANIFEST, manifest)
    todo = len(pending(index, cache))
    print(f"wrote {pc.MANIFEST}: {len(manifest['photos'])} photos ({s['hidden']} hidden), {todo} still unanalysed")
    print(f"{s['analysed']} photos analysed, {s['byNumber']} identified by number, {s['inferred']} inferred, "
          f"{s['unidentified']} unidentified riders, {s['unmatched']} numbers not in start list")
    return 0


def main(argv):
    cmds = {"worklist": cmd_worklist, "import": cmd_import, "build": cmd_build}
    if not argv or argv[0] not in cmds:
        print(__doc__); return 2
    return cmds[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

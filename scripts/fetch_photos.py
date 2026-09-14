#!/usr/bin/env python3
"""Sync the public Trans Caledonia photo folder into data/photo_index.json and
download analysis-size thumbnails for photos not seen before.

    python3 scripts/fetch_photos.py            # sync everything new
    python3 scripts/fetch_photos.py --dry-run  # just list what is new
"""
import io, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import photo_common as pc  # noqa: E402

IMAGE_EXT = (".jpg", ".jpeg", ".png")
ENTRY = re.compile(r'<div class="flip-entry" id="entry-([^"]+)".*?<a href="([^"]+)".*?<div class="flip-entry-title">(.*?)</div>', re.S)
UA = {"User-Agent": "Mozilla/5.0"}


def http(url, headers=None, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception:  # noqa: BLE001
            if i == retries - 1:
                raise
            time.sleep(2 ** i)


def fetch_text(folder_id):
    return http(f"https://drive.google.com/embeddedfolderview?id={folder_id}#list").decode("utf-8", "replace")


def parse_folder_view(html):
    out = []
    for fid, href, title in ENTRY.findall(html):
        name = unescape(re.sub(r"<[^>]+>", "", title)).strip()
        if "/drive/folders/" in href:
            out.append({"id": fid, "name": name, "kind": "folder"})
        elif "/file/d/" in href:
            out.append({"id": fid, "name": name, "kind": "file"})
    return out


def list_tree(root_id, fetch=fetch_text):
    files, queue = [], [(root_id, None)]
    while queue:
        fid, fname = queue.pop(0)
        for e in parse_folder_view(fetch(fid)):
            if e["kind"] == "folder":
                queue.append((e["id"], e["name"]))
            elif fname and e["name"].lower().endswith(IMAGE_EXT):
                files.append({"id": e["id"], "name": e["name"], "folderId": fid, "folder": fname})
    return files


def exif_time(jpeg_head):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(jpeg_head))
        ex = im.getexif()
        raw = ex.get_ifd(0x8769).get(36867) or ex.get(306)
    except Exception:  # noqa: BLE001
        return None
    if not raw:
        return None
    m = re.match(r"(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})", str(raw))
    return f"{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:{m[6]}Z" if m else None


def plan_downloads(files, index, cache):
    seen = {k for k, v in index.get("photos", {}).items() if v.get("fetched")} | set(cache)
    return [f for f in files if f["id"] not in seen]


def main(argv):
    dry = "--dry-run" in argv
    index = pc.load_json(pc.INDEX, {"photos": {}})
    cache = pc.load_json(pc.CACHE, {})
    print("listing Drive folder...")
    files = list_tree(pc.ROOT_FOLDER_ID)
    by_folder = {}
    for f in files:
        by_folder[f["folder"]] = by_folder.get(f["folder"], 0) + 1
    print(f"{len(files)} images in {len(by_folder)} folders: " + ", ".join(f"{k} {v}" for k, v in sorted(by_folder.items())))
    live = {f["id"] for f in files}
    for fid in list(index["photos"]):
        if fid not in live:
            del index["photos"][fid]
    new = plan_downloads(files, index, cache)
    new_ids = {f["id"] for f in new}
    print(f"{len(new)} new photos" + (" (dry run, nothing downloaded)" if dry else ""))
    if dry:
        for f in new:
            print(f"  {f['folder']}/{f['name']} {f['id']}")
        return 0
    pc.TMP.mkdir(parents=True, exist_ok=True)
    for f in files:
        day, _ = pc.folder_meta(f["folder"])
        entry = index["photos"].get(f["id"]) or {"capturedAt": None}
        entry.update({"name": f["name"], "folderId": f["folderId"], "folder": f["folder"], "day": day,
                      "photographer": pc.photographer_for(f["folder"], f["name"]), "seq": pc.seq_number(f["name"])})
        index["photos"][f["id"]] = entry

    def grab(f):
        fid = f["id"]
        dest = pc.TMP / f"{fid}.jpg"
        if not dest.exists():
            dest.write_bytes(http(pc.thumb_url(fid, 1600)))
        head = http(f"https://drive.google.com/uc?export=download&id={fid}", {"Range": "bytes=0-262143"})
        return fid, exif_time(head)

    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(grab, f) for f in new]):
            fid, captured = fut.result()
            index["photos"][fid]["capturedAt"] = captured
            index["photos"][fid]["fetched"] = True
            done += 1
            e = index["photos"][fid]
            print(f"[{done}/{len(new)}] {e['folder']}/{e['name']} {captured or 'no exif'}", flush=True)
            if done % 25 == 0:
                index["fetchedAt"] = pc.now_iso(); pc.save_json(pc.INDEX, index)
    index["fetchedAt"] = pc.now_iso()
    pc.save_json(pc.INDEX, index)
    print(f"wrote {pc.INDEX}: {len(index['photos'])} photos, {len(new)} new")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

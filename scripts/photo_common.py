"""Shared helpers for the photo scripts."""
import json, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MANIFEST = DATA / "photos.json"
CACHE = DATA / "photo_analysis_cache.json"
INDEX = DATA / "photo_index.json"
OVERRIDES = DATA / "photo_overrides.json"
RESULTS = DATA / "results.json"
TMP = DATA / "photo_tmp"
ROOT_FOLDER_ID = "1GZXFGwYuxcEYCCsiDQwOLARxEhzoSEGE"
CREDITS = ("Photos by the Trans Caledonia Enduro media team: Sadie Aldridge, Pete Scullion, Nico Turner, Nick Clark. "
           "Please credit the creator when sharing.")


def load_json(path, default):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def known_bibs(results):
    return {int(r["bib"]): r["name"] for r in results.get("riders", [])}


def thumb_url(file_id, width):
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{width}"


def view_url(file_id):
    return f"https://drive.google.com/file/d/{file_id}/view"


def seq_number(name):
    """DSC_0055.jpg -> 55; 'Trans Caledonia - Day 1 - Pete Scullion-50.jpg' -> 50."""
    stem = Path(name).stem
    paren = re.search(r"\((\d+)\)\s*$", stem)
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    m = re.search(r"_(\d{3,})", stem)
    if m:
        return int(m.group(1))
    if paren:
        return int(paren.group(1))
    m = re.search(r"-(\d+)$", stem)
    return int(m.group(1)) if m else None


def photographer_for(folder_name, file_name):
    """Credit from the folder name ('... - Credit X') or the file name ('... - Day 1 - Pete Scullion-50.jpg')."""
    _, credit = folder_meta(folder_name)
    if credit:
        return credit
    m = re.search(r"-\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+?)(?:[- ]\d+)*(?:\s*\(\d+\))?$", Path(file_name).stem)
    if m and not m.group(1).startswith("Day"):
        return m.group(1).replace("Peter ", "Pete ")
    return None


def folder_meta(folder_name):
    """'Day 3' -> ('3', None); 'Podiums - Credit Sadie Aldridge' -> ('Podiums', 'Sadie Aldridge')."""
    m = re.fullmatch(r"Day (\d+)", folder_name.strip())
    if m:
        return m.group(1), None
    photographer = None
    m = re.search(r"Credit\s+(.+)$", folder_name)
    if m:
        photographer = m.group(1).strip()
    day = re.split(r"\s+-\s+", folder_name)[0].strip()
    if "slideshow" in day.lower():
        day = "Slideshow"
    return day, photographer


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

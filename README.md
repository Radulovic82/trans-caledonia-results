# Trans Caledonia 2026 results

Line charts comparing every rider across all timed stages of the MTB Enduro Trans Caledonia 2026. Pick riders to highlight them against the rest of the field, filter by category, and share the URL (the selection is kept in the hash).

Live page: https://radulovic82.github.io/trans-caledonia-results/

Data comes from the official live timing at https://my.raceresult.com/413373/live. This page is unofficial.

## Updating after a race day

```
python3 scripts/fetch_results.py
git add data/results.json
git commit -m "day 6"
git push
```

Or run the **Refresh results** workflow from the Actions tab, which does the same and commits if anything changed.

## Local preview

```
python3 -m http.server 8000
```

then open http://localhost:8000/

## Photos

The Photos page lists race photos from the organisers' shared Google Drive folder and sorts them by rider. Photos stay in Drive; only `data/photos.json` (which photo shows which rider) lives in this repo.

Updating when new photos are added to Drive:

```
python3 scripts/fetch_photos.py                 # find new photos, download small copies to data/photo_tmp/
python3 scripts/analyze_photos.py worklist      # list photos still waiting for number reading
# read numbers and rider descriptions for those photos and save them as results.json (format below)
python3 scripts/analyze_photos.py import results.json
python3 scripts/analyze_photos.py build         # match riders, apply overrides, write data/photos.json
git add data/photos.json && git commit -m "photos" && git push
```

Already-analysed photos are skipped automatically (`data/photo_analysis_cache.json`, not committed). Needs Pillow (`pip install pillow`) for reading capture times.

Results format for `import`, one entry per Drive file id:

```
{"FILE_ID": {"scene": "race-action", "numbers": [{"bib": 42, "confidence": "high"}],
             "riders": [{"bib": 42, "helmet": "white", "kit": "black jersey, orange sleeves", "bike": "blue", "other": "hip pack"}]}}
```

`scene` is one of race-action, podium, group, portrait, scenery. `confidence` is high, medium or low. A rider whose number is not readable gets `"bib": null`; the build step tries to match them to a rider seen nearby with the same kit and marks those with ≈ on the page.

Manual corrections go in `data/photo_overrides.json`, keyed by file id, and always win:

```
{"FILE_ID": {"add_bibs": [42], "remove_bibs": [47], "hide": false, "photographer": "Sadie Aldridge"}}
```

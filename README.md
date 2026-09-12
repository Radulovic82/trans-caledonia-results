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

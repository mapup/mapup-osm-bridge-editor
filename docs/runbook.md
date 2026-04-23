# Runbook

## Common Failures & Recovery

| Failure                                    | Cause                                                    | Fix                                                                 |
| ------------------------------------------ | -------------------------------------------------------- | ------------------------------------------------------------------- |
| `FileNotFoundError` on input data          | Input `.pbf`/`.csv`/`.gpkg` not in `input-data/<state>/` | Download missing file (links in README), place in correct path      |
| `MemoryError` / OOM during join            | Large state `.pbf` processed in memory                   | Reduce scope by filtering to a county first                         |
| Osmium tool not found                      | Not installed                                            | `brew install osmium-tool`                                          |
| GDAL import error                          | GDAL not installed or Python binding missing             | `brew install gdal`, reinstall `geopandas`                          |
| Dask partial output in `result_directory/` | Pipeline interrupted mid-run                             | Delete `output-data/<state>/csv-files/result_directory/` and re-run |
| JOSM scripting plugin error                | Plugin version mismatch                                  | Update JOSM and scripting plugin to latest                          |

## Rollback

No database mutations. To reset: delete the output directory and re-run.

```bash
rm -rf hydrography-approach/output-data/<state>/
cd hydrography-approach && python run-hydrography-pipeline.py
```

## Logs / Monitoring

- Output is stdout only (`print()` statements in pipeline scripts)
- No external monitoring or alerting

## Cron / Scheduled Jobs

None.

## Data Backfill

To reprocess with updated source data:

1. Download fresh input files (Geofabrik, FHWA NBI, USGS NHD)
2. Replace files in `input-data/<state>/`
3. Delete `output-data/<state>/`
4. Re-run the pipeline

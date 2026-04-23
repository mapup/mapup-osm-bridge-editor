# Architecture

## Major Services
None. All processing is local batch scripts. No web services, APIs, or daemons.

## Datastore Choices
- **Input**: `.pbf` (OSM extract), `.csv` (NBI bridge data), `.gpkg` (NHD streams)
- **Intermediate/output**: `.gpkg` and `.csv` files written to `output-data/<state>/`
- All paths configured in `hydrography-approach/config.yml`

## Queues / Jobs
None. Pipeline stages run sequentially in a single Python process.

## Third-Party Dependencies
Python: see [`requirements.txt`](../requirements.txt).
External tools: QGIS-LTR, Osmium, GDAL, JOSM with Scripting Plugin.

## Auth Model
None. All data sources (Geofabrik, FHWA, USGS) are public. OSM upload requires a personal OSM account and is done manually via JOSM.

## Tenancy
Not applicable.

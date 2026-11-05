# Real Tower Data for the Family B Case Studies

Date integrated: 2026-07-09. Both case studies now run on **real cell-site
positions**; the synthetic fallback layouts are retired.

## Sources

1. **OpenCellID** (`Thesis/OpenCell_ID/`, MCC 310–314 US extracts,
   CC BY-SA, opencellid.org). Crowd-sourced cell positions; we use LTE
   cells only, with the position quality caveats documented in `data_format`.
2. **FCC Antenna Structure Registration** (`Thesis/r_tower/`, ASR database
   flat files). `CO.dat` provides surveyed DMS coordinates of registered
   structures (typically >60 m or near airports). Used as a ground-truth
   cross-check, not as the primary source — most urban cell sites are
   unregistered rooftop installations.

## Method (`tools/opencellid_towers.py`)

1. Filter LTE cells inside each study bbox across all five MCC files
   (`osm/dc_cells.csv`, `osm/va_cells.csv`).
2. Greedy-cluster cells into physical sites (multiple sectors/carriers per
   tower): 200 m radius urban, 300 m rural.
3. Keep the 8 densest sites per area; convert lat/lon to SUMO scenario
   coordinates via the network projection (pyproj).
4. Emit eNodeB positions + **full-mesh X2** config (real layouts are not
   linear chains; `CorridorNet.x2Mesh = true` wires all site pairs).

## Results per area

| | DC urban (Foggy Bottom/GWU) | Rural VA (US-29 / Gainesville) |
|---|---|---|
| bbox | −77.055..−77.030, 38.892..38.905 | −77.72..−77.60, 38.78..38.84 |
| OpenCellID LTE cells | 477 | 204 |
| Sites used | 8 | 8 |
| FCC ASR structures in bbox | 5 | 3 |
| Worst route-point→nearest-site | 607 m | **4,852 m** |
| Route fraction >4.5 km from any site | 0% | **7.6%** |

## Case-study outcomes with real towers (seed 0)

| KPI | DC urban | Rural VA |
|---|---|---|
| Delivery | 97.1% (1800/1854) | **64.9%** (2078/3204) |
| Mean E2E delay | 135 ms | 897 ms |
| Max E2E delay | 1.23 s | 54.6 s (outage buffering + flush) |
| Sites visited by ego | 7 of 8 | 9 serving-cell IDs, rich handover/ping-pong |

The rural VA route's western leg crosses a genuine coverage gap present in
the measured tower data — the resulting outage, buffering, and delayed-flush
behavior is the paper's "digital health divide" mechanism, now demonstrated
from real infrastructure rather than configured knobs.

QC (`tools/qc_check.py`): PASSED on 12 runs / 2 configs with real towers.

## Reproduce

```
cd PaperRebuild/osm
python3 ../tools/opencellid_towers.py --cells dc_cells.csv --net dc_urban.net.xml \
    --out ../simulations/dc_case/towers_dc.ini --site-radius 200 --max-sites 8 --x2-mesh
python3 ../tools/opencellid_towers.py --cells va_cells.csv --net va_rural.net.xml \
    --out ../simulations/va_case/towers_va.ini --site-radius 300 --max-sites 8 --x2-mesh
```
(Initial serving cell in each case ini = nearest site to the trace start:
DC `servingNodeId=4`, VA `servingNodeId=8`.)

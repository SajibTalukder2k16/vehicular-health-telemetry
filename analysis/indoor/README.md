# Indoor campaign extracts

The five indoor campaigns produce about **1 GB** of `.sca`/`.vec` output,
which is not committed. These extracts are what the indoor tables are computed
from, so every one of them regenerates from this repository alone.

## Files

| file | corpus | runs | contents |
|---|---|---|---|
| `room_wired_latencies.csv.gz` | `results_room_ladder` | 300 | ladder, camera on a cable, 802.11 backhaul, two bands |
| `room_wifi_latencies.csv.gz` | `results_room_wifi` | 300 | ladder, camera on the WLAN, quiet and 80 % busy |
| `room_ble_latencies.csv.gz` | `results_room_ble` (Part A) | 150 | ladder, camera on BLE |
| `indoor_lte_latencies.csv.gz` | `results_indoor_lte` | 150 | ladder, stationary unloaded edge on an LTE backhaul |
| `indoor_lte_cam4k_latencies.csv.gz` | `results_indoor_lte_cam4k` | 150 | the same arm at a 4 KiB camera, matching `CondHealthy`'s payload |
| `sensor_link_scalars.csv.gz` | all three room corpora | 1,050 | camera-link load, wearable vitals delivery |
| `room5g_120_latencies.csv.gz` | `results_room5g_120` | 600 | **120 seeds**: WLAN 5 GHz |
| `indoor_lte_120_latencies.csv.gz` | `results_indoor_lte_120` | 600 | **120 seeds**: stationary LTE |
| `indoor_lte_4k_120_latencies.csv.gz` | `results_indoor_lte_4k_120` | 600 | **120 seeds**: the same at a 4 KiB camera |
| `healthy_120_latencies.csv.gz` | `results_healthy_120` | 600 | **120 seeds**: `CondHealthy` |
| `outage_120_latencies.csv.gz` | `results_outage_120` | 600 | **120 seeds**: `CondOutage` |

The five `*_120_*` extracts are what the paper's decomposition table is
computed from. At 30 seeds two of its three steps were not detectable and the
third was unstable by a third; see `docs/INDOOR_BACKHAUL_RESULT.md` §9.

The five `*_latencies.csv.gz` files hold the per-escalation vectors
(`condition,arm,seed,kind,recv_time,delay,creation`) written by
`tools/extract_vec.py`. `sensor_link_scalars.csv.gz` holds the seven scalars
the camera-link and radio-share tables need, written by
`tools/extract_indoor_scalars.py`; those are scalars rather than vectors and
so are absent from the others.

## Regenerating the tables

```sh
# completion and dispatch, per condition and rung
python3 -I tools/analyze_room_ladder.py analysis/indoor/room_wired_latencies.csv.gz
python3 -I tools/analyze_room_ladder.py analysis/indoor/room_wifi_latencies.csv.gz
python3 -I tools/analyze_room_ladder.py analysis/indoor/room_ble_latencies.csv.gz
python3 -I tools/analyze_room_ladder.py analysis/indoor/indoor_lte_latencies.csv.gz

# the backhaul decomposition and its significance tests
python3 -I tools/compare_backhaul.py \
    analysis/indoor/room_wired_latencies.csv.gz RoomMatched5GHz \
    analysis/indoor/indoor_lte_latencies.csv.gz CondIndoorLte --arm e4

# camera-link load (C1's WLAN and BLE rows, measured) and the radio-share cliff
python3 -I tools/indoor_sensor_links.py analysis/indoor/sensor_link_scalars.csv.gz
```

`analyze_room_ladder.py` and `indoor_sensor_links.py` each take either a
directory of raw output or one of these extracts, and produce identical
output from both.

## Verification

Each latency extract is checked against its corpus cell by cell — not by row
count, which can match while values differ, but on the published statistics
themselves:

```sh
python3 -I tools/verify_indoor_extract.py \
    simulations/room/results_room_ladder analysis/indoor/room_wired_latencies.csv.gz
```

All five passed at the time of extraction: **35 cells × 5 statistics**
(complete, lost, median alert, median gap, median dispatch) agreeing to
$10^{-9}$.

This check is not a formality. An extract is a lossy rewrite of a corpus that
is then deleted; if it silently drops a cell, the tables still compute and
still look plausible. This project has already published one silently wrong
table, and the only tell was that a number looked too clean.

## Regenerating the corpora instead

Cheaper than storing them — all five campaigns run in about 80 seconds total
on 12 parallel jobs:

```sh
sh tools/room_ladder.sh          # 300 runs, ~90 s
sh tools/room_wifi_ladder.sh     # 300 runs, ~17 s
sh tools/indoor_lte_ladder.sh    # 150 runs, ~43 s
sh tools/room_ble_ladder.sh      # 450 runs, ~18 s  (Parts A, B and C)
CAM4K=1 sh tools/indoor_lte_ladder.sh   # 150 runs; the 4 KiB camera control
sh tools/indoor_power120.sh      # 2,400 runs, ~13 min; the 120-seed arms
```

**Run `tools/verify_power120.py` on any 120-seed corpus before using it.**
Seeds 0–29 are the same seed-sets the 30-seed corpora used, so they must
reproduce the published cells exactly. That check caught a real error: the
driver initially left `CondHealthy` at the configuration's 4 KiB camera
instead of the 53,167 B every campaign actually runs, giving 25/12
complete/lost against a published 31/6.

The `CAM4K=1` control exists because the cellular corpus runs its camera at
4 KiB (`CondHealthy`) or 60 KiB, not at the 53,167 B the indoor campaigns use.
It checks whether that mismatch reaches the verification path. It does not:
the alert and the E4 gap are identical and completion moves by one burst in
35.

Note that `room_ble_ladder.sh` Parts B and C write labels (`rate-*`,
`share-*`) that the latency extracts deliberately exclude: those sweeps vary
the camera rate and the wearable's radio share, not the evidence rung, so
their escalation latencies are not comparable with the ladder's and are not
part of any latency table.

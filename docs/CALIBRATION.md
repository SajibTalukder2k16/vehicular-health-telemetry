# Model Calibration & Validation (manuscript section source)

Three layers of validation, from component to system level.

## 1. BLE link (component level) — see docs/BLE_VALIDATION.md

Reproduces Gomez et al. (2012) 236.7 kbps BLE 4.0 ceiling within 1.5%, the
BLE 4.2/5 measured throughput ranges (Tosi et al. 2017), the CI/2 latency law
within 8%, and exact PER-proportional degradation. Campaign runs use
pduErrorRate = 0.01 (measured short-range PER).

## 2. LTE stack behavior (Simu5G, system level)

- **Latency floor.** Urban DC drive, vitals stream: p10 = 26 ms, p50 = 41 ms
  end-to-end (BLE hop ~15 ms mean + edge 1.25 ms + LTE UL). The implied LTE
  uplink one-way latency of ~10–25 ms sits inside published LTE UL ranges
  (drive-test medians ~20–40 ms RTT-half; FCC MBA mobile latency reports;
  Raca et al. LTE dataset).
- **Channel-quality falloff (fig5):** mean uplink CQI declines monotonically
  from ~15 at <100 m to ~6 at 0.8 km (urban UMa) and ~1–2 at 4–5 km (rural
  RMa) — consistent with 3GPP path-loss expectations; no plateau or
  discontinuity artifacts.
- **Handover dynamics:** 10.3 handovers per 519 s urban drive across 8 real
  sites with occasional ping-pong (2–3), median delivered-packet delay in the
  2 s post-handover window elevated to 117 ms (vs 41 ms drive median) —
  matching the tens-of-ms-to-sub-second interruption range reported for X2
  handover. Rural: more ping-pong (10–14) as expected under shadowing with
  sparse sites.
- **Loss realism check (contrast with the old model):** urban delivery is
  96–98% and rural (in-coverage) 91–97%; the ~45% "loss" of the discarded
  abstract model does not reappear. Loss now concentrates where physics says
  it should: cell edges, handovers, and the VA route's real coverage gap.

## 3. Upstream model provenance

- INET 4.7.0 802.11 and Simu5G 1.4.4 LTE stacks are community-validated;
  three Simu5G defects found during this work are documented and patched
  locally (docs/SIMU5G_PATCHES.md) — most notably a 180 dB unit error in the
  RMa/SMa LOS path-loss (Hz vs GHz) that would have silently invalidated any
  rural LOS scenario. This is disclosed in the manuscript's methodology.
- Tower positions: OpenCellID LTE cells clustered to sites, cross-checked
  against FCC ASR registered structures (docs/TOWER_DATA.md). Mobility: SUMO
  on OSM road networks.

## Known limitations to state in the paper

- CQI-vs-distance is validated against model expectations, not against a
  matched drive-test dataset for the same routes; RSRP traces were not
  recorded (CQI is the actionable proxy in Simu5G).
- Delivery-horizon truncation at −100/−104 dBm sensitivity keeps the runs
  inside the path-loss models' validity ranges; signals below that floor are
  treated as outage.
- Single instrumented vehicle per run. Background load was **absent from every
  run before 2026-11-02**: Simu5G background UEs were instantiated but never
  transmitted, because `startTimeUl` defaults to `-1s` and was never set. See
  `docs/CORRECTIONS_2026-10.md` C13. Fixed since, and the corridor headline has
  been re-run under ~2.5 Mbps/cell of competing uplink
  (`results_loaded/`, 490 validated runs); the margin is unchanged within the
  interval, so the result is not an artifact of an idle cell. Everything
  outside `results_loaded/` — the pilot, the case studies, Family A — is still
  unloaded, and must be described that way.

# Old Simulation Model — Deficiency Memo

**Project:** Communication Performance of IoT and Edge-Based Health Monitoring System (GWU MS thesis, 2025)
**Purpose of this memo:** documents, with evidence, why the original simulation cannot support a journal submission and what the rebuild must fix. Feeds the motivation/limitations narrative of the new paper and serves as the QC checklist for the new model.
**Evidence base:** `Thesis/.metadata/Old_Data/` — `Report/Manuscript.docx`, ~7,985 `.sca` files in `Thesis_Updated_simulations/sca_files/`, `InRoomAnalysis/` + `InVehicleAnalysis/` pipelines, `.tex` chapters, comparison reports. Audit date: 2026-07-08.

---

## 1. Model-architecture deficiencies (root causes)

### 1.1 Channel behavior was configured, not simulated
The model is a bespoke OMNeT++ project (`vehicle_com.simulations.*` modules) with **no INET modules at all**, although the manuscript states "INET 4.4". From the `.sca` config headers (e.g. `R001-1-#0.sca`):

```
**.cellularInterface.latency  "uniform(50ms, 120ms)"   ← latency drawn from RNG knob
**.cellularInterface.packetLoss  0.05                  ← base loss probability knob
**.bluetooth.delay  "uniform(10ms, 50ms)"              ← BLE delay knob
**.bluetooth.errorRate  0.01
**.wired.dataRate 1Gbps, delay 0.5ms
```

End-to-end delay is therefore (approximately) a sum of uniform random draws plus queueing; loss is a coin flip plus coverage. There is no PHY, MAC, contention, fading, or interference. Urban configs were *given* lower latency/loss knobs and higher data rates than rural configs (e.g. `U007`: `uniform(35ms,85ms)`, loss 0.02, 30 Mbps vs `R001`: `uniform(50ms,120ms)`, loss 0.05, 5 Mbps) — so the paper's central urban-vs-rural finding is largely an echo of its own inputs.

### 1.2 The headline 45% vehicular packet loss is an out-of-coverage artifact
`LinearMobility` at constant speed for 3,600 s drives the vehicle up to ~88 km from a **single** tower (`coverageRadius 25000m`, `distanceToTower:mean ≈ 43,705 m` in R001). There is no handover and no second tower. Most recorded loss (`packetLossRate ≈ 0.467` vs configured base 0.05) is the vehicle simply leaving coverage. Real LTE at 0.25–1 mile from a serving cell loses ≪1% of packets; the manuscript's 36–52% loss and the "digital health divide" magnitude built on it are not physically credible.

### 1.3 Degenerate recorded metrics (placeholder values)
Constant across **all** ~8,000 runs:

| Scalar | Value | Implication |
|---|---|---|
| `edgeServer.bufferOccupancy:mean` | 0.5000 (std ≈ 0) | placeholder, not a measured queue |
| `edgeServer.packetsDropped` | 0 | edge buffer never exercised |
| `edgeServer.packetDeliveryRatio` | exactly 1.0 | contradicts the thesis's own "buffer overflow" narrative |

Any statistics computed over these columns are meaningless.

### 1.4 In-room model never implemented the WiFi band
Rows for 2.4 GHz and 5 GHz in `InRoomAnalysis/analysis_data.csv` are **bit-for-bit identical** (Room1 ≡ Room7, Rooms 4–6 ≡ 10–12, 13–18 ≡ 19–24). The band parameter had no code behind it. One auto-generated report (`FINAL_COMPREHENSIVE_ANALYSIS_REPORT.md`) nevertheless claims an ~85% band improvement with F-statistics and Cohen's d — those numbers do not exist in the data. (The thesis abstract/discussion correctly say p ≈ 1.0.)

### 1.5 Runaway-queue scenarios reported as findings
BLE (~≤2–3 Mbps knob) cannot carry 60 KB camera frames at 5–10 fps (~2.4–4.8 Mbps offered). The queue never drains; raw in-room E2E delays reach **113,000–115,500 s inside a ≤500 s simulation**, then appear in reports as "115.47 s" (a ÷1000 unit error). The correct statement is "BLE video is infeasible by design" (one line of link-budget arithmetic), not a 12-scenario latency comparison.

## 2. Experiment-design deficiencies

- **Speed ⟂ environment confound:** urban = 25/45 mph, rural = 55/65 mph — no overlap, so speed effects and environment effects are inseparable. The abstract reports r = 0.970 (speed→loss) as a headline; the results chapter reports r = 0.015 after partial correlation. Both cannot be in the same paper.
- **Multi-factor confound:** urban vs rural simultaneously changes speed, tower distance, data rate, configured latency, and configured loss.
- **Edge-device confound:** smartphone (all-BLE sensors) vs embedded PC (wired camera/OBD) confounds the device with the sensor connectivity.
- **Near-deterministic model + 100 seeds = p-value theater:** Cohen's d up to 71.25 and p < 1e-300 reflect near-zero within-config variance, not scientific strength.

## 3. Reporting integrity issues in the current manuscript

1. Speed→loss correlation: abstract r = 0.970 vs results chapter r = 0.015 (n.s.).
2. Best-vs-worst "fold" claims: 2,442× (abstract) vs 1,206× (conclusion) vs 3.7× (elsewhere); Table 5's own numbers give 1,123×.
3. Scenario/seed accounting: 96 vs 90 vs 80 configs across documents; 10 vs 100 seeds; "over 9,000 runs" vs 96×100 = 9,600; actual corpus = 80 configs × ~100 = 7,985 files; in-room seed count never stated.
4. Abstract percentages (21.4/16.6/21.7%) ≠ Table 9 (20.5/17.8/22.7%).
5. Abstract says WiFi band "no statistically significant impact" while Table 6 reports p = 0.0034 — and the raw data say the band was never modeled at all (§1.4).
6. "Five primary objectives" vs four listed RQs; two different packet-loss datasets (results.tex: urban 50.7% / rural 59.8%; analysis docs: 40.9% / 49.0%).
7. No validation against any real measurement; "empirical evidence" language overclaims for an idealized simulation.

## 4. What was sound (kept in the rebuild)

- The Python analysis layer honestly parses real `.sca` output — no fabricated metrics (verified by grep for RNG/synthetic generation; only plot jitter found).
- Real experiment-campaign discipline: 80 configs × ~100 seeds, consistent naming, reproducible parsing.
- The three-tier architecture, motivation, scenario taxonomy, and ~60-reference literature review are reusable.

## 5. QC rules for the new model (derived from the above)

A run set FAILS quality control if any of:
- any recorded metric is constant across seeds within a config (catches §1.3);
- any delay exceeds simulation time (catches §1.5);
- loss/latency at short range contradicts published LTE/WiFi/BLE measurements by more than the calibration tolerance (catches §1.1–1.2);
- two factor levels produce bit-identical outputs (catches §1.4);
- reported aggregate numbers cannot be regenerated from the raw result files by the pipeline (catches §3).

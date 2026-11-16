# M4: pricing the edge — the gap is invariant, and a measurement bug is fixed

**960 runs, 2026-11-11.** `results_edge/`, verified extract in `analysis/edge/`.
Eight arms × four conditions × 30 seeds. Predictions recorded in
`tools/edge_sensitivity.sh` **before** the run; contrasts in
`tools/edge_contrasts.py`.

This campaign existed to answer one question — *what does a correctly-sourced
edge processing time do to time-to-dispatch?* — because the live
`uniform(0.5ms, 2ms)` is unsourced and 11–190× too fast
(`PARAMETER_PROVENANCE.md` §A.2), and under C2′ the edge sits **inside** the
dispatch budget. Until it was priced, no absolute time-to-dispatch was
reportable.

It returned three things: the answer (§3), a **bug in the analysis tool that
had already produced published numbers** (§1), and a correction to the compute
wall's own arithmetic (§2).

Companions: `VERIFICATION_FRONTIER.md` (C3), `PHASE2_RESULT.md` (the deferral
rules), `PARAMETER_PROVENANCE.md` §A.2 (M4) and §A.7 (the compute wall).

---

## 1. First: the two delay signals are on different clocks

`HealthServerApp::socketDataArrived` computes one delay for every packet,
`simTime() - payload->getSensorCreationTime()`. But the two classes carry
different creation stamps:

* an **alert** carries the rig's sensor creation time, so `e2eDelayAlarm`
  **includes** the edge's processing and queueing delay;
* an **evidence chunk** is a `SensorData` constructed at the edge inside
  `EdgeApp::escalate()`, so its stamp is the *detection* instant and
  `e2eDelayEvidence` **excludes** everything upstream of the edge. The code says
  so explicitly: *"Created now, at the edge… End-to-end delay for this class is
  therefore measured from the detection instant."*

`dispatch_times.py` computed `max(alert_delay, max chunk_delay)`, which charges
the edge cost to the alert and credits it to the evidence. The difference is the
per-frame edge latency, measured here:

| edge setting | min | median | max |
|---|---|---|---|
| `uniform(0.5ms, 2ms)` | 0.000502 | 0.001194 | 0.002440 |
| 22.73 ms @ 30 fps | 0.022730 | 0.030898 | 0.066293 |
| 22.73 ms @ 60 fps | 0.032327 | 0.048418 | 0.087952 |
| 94.27 ms @ 60 fps | 0.174657 | 0.233411 | 0.450942 |

At the unsourced edge that error is ≤1.3 ms and invisible. At 94.27 ms it is
**230 ms**, and it drove the dispatch gap to *exactly* `0.0000` in seven cells —
reading as *"a slower edge makes verification free."* It does not. Dispatch is
referred to the **sensor instant**, the moment the physiological event was
observed, which is what an emergency latency is measured from:

```
dispatch_delay = max(alert_delay, offset + max over the burst's chunk delays)
```

Fixed, with the offset now reported by `--report-pairing`. Pairing also became a
**signed** window: evidence is created at or after its alert, never before, and
the measured minimum inter-escalation spacing is **1.1692 s** — below the
tolerance a saturated edge needs, so a symmetric `|Δ|` window could pair an
alert to its *neighbour's* burst. A signed window cannot. The two code paths
(corpus and committed extract) were duplicated and are now one function.

### What this changes in already-published numbers

The offset on the earlier corpora is 1.28 ms, so every gap moves by ~+1.7 ms and
**no conclusion changes**. One *ratio* does move materially, because its
denominator is the same size as the correction:

| condition | E2→E3 factor, as published | corrected |
|---|---|---|
| CondHealthy | 53× | **32×** |
| CondCongested | 14× | **13×** |
| CondTransient | 21× | **19×** |
| CondOutage | 42× | **40×** |

So C3's headline is **"13–40×", not "14–53×"**. Every budget-miss percentage in
both documents is unchanged. `VERIFICATION_FRONTIER.md` and `PHASE2_RESULT.md`
carry the corrected tables and a pointer here.

---

## 2. The compute wall is real, and slightly worse than recorded

`PARAMETER_PROVENANCE.md` §A.7 derived the wall from the *camera* frame rate.
But `EdgeAggregator` is a **single-server FIFO applying `processingTime` to
every packet**, and the vitals stream shares that server. Measured offered load
is **61.5 pkt/s at 60 fps, not 60** — so the sustainable *camera* rate is lower
than the sustainable packet rate:

| arm | offered pkt/s | forwarded pkt/s | 1/service | dropped |
|---|---|---|---|---|
| 30 fps, free edge | 31.5 | 31.5 | — | **0** |
| 30 fps, 22.73 ms | 31.5 | 31.5 | 44.0 | 76 (0.18 %) |
| 60 fps, 22.73 ms | 61.5 | **44.0** | 44.0 | 28.5 % |
| 60 fps, 94.27 ms | 61.5 | **10.61** | 10.61 | **82.8 %** |

Forwarded throughput pins to `1/processingTime` exactly, confirming the server
model. Two corrections:

1. Sustainable **camera** rate is ≈ **42.5 fps** (PC-class) and ≈ **9.1 fps**
   (embedded), not 44.0 and 10.6.
2. PC-class at 30 fps *fits*, but at **ρ = 0.72** — 28 % headroom, 0.18 % of
   packets already dropped, and a median per-frame latency of **30.9 ms against
   22.73 ms of service**, i.e. a third of it is queueing.

And the wall has a **sensing** consequence, not only a latency one: at 60 fps on
embedded hardware the edge forwards 14,521 of 84,227 packets, so the pipeline
sees an effective **10.6 fps** — below the 20 fps HR floor. Asking for
PRV-grade sensing on that platform does not yield degraded PRV; it yields a
stream too sparse for HR.

The §A.7 caveat stands unchanged and is load-bearing: Kim & Koo measure a
**blink-based drowsiness pipeline, not rPPG PRV extraction**. The wall's
*existence* is supported; its *position* is not settled, and settling it needs a
measured per-frame cost for an rPPG-PRV pipeline.

---

## 3. Result: the dispatch gap is invariant to edge cost

**The prediction's central claim is confirmed.** Per-seed median gap, paired on
the seed, exact two-sided sign test, each arm against a baseline **at the same
frame rate** (see §5 — mismatching this is a trap that reads backwards). Of
**24 cells, exactly one** reaches p < 0.05:

| contrast | CondHealthy | CondCongested | CondTransient | CondOutage |
|---|---|---|---|---|
| 30 fps, E2′: free → PC | 0.98 (p 1.00) | 1.08 (p 0.58) | 1.31 (p 0.86) | 0.30 (p 0.12) |
| 30 fps, E4: free → PC | 0.64 (p 0.26) | 1.03 (p 0.58) | 1.09 (p 0.86) | 0.97 (p 0.44) |
| 60 fps, E2′: free → PC | 0.44 (p 0.26) | 0.76 (p 1.00) | 0.82 (p 0.58) | 8.13 (p 0.12) |
| 60 fps, E2′: free → EMB | 1.04 (p 0.82) | 1.36 (p 0.86) | 0.82 (p 0.58) | 0.88 (p 1.00) |
| 60 fps, E4: free → PC | **1.53 (p 0.041)** | 1.12 (p 0.58) | 1.00 (p 0.58) | 1.02 (p 1.00) |
| 60 fps, E4: free → EMB | 1.21 (p 0.12) | 1.15 (p 0.58) | 0.68 (p 0.58) | 1.27 (p 1.00) |

One hit at p = 0.041 across 24 tests is exactly the false-positive rate α = 0.05
predicts (expected 1.2), and the effect it flags is a 1.53× on CondHealthy's 20
seeds. **Twenty-two of the 24 ratios fall in 0.44–1.53** with no systematic
direction; the two outliers (0.30× and 8.13×) are both CondOutage, both
non-significant, and both on the same thin, high-variance cell.

**This is the result that matters most in the campaign**, because it is what
licenses everything already written: a 50–190× change in edge processing cost
moves the *absolute* dispatch times substantially (§4) and leaves every
*contrast* intact. The mechanism is the one predicted — the alert and its
evidence are both produced at the edge and shift together.

### The design rule survives at 20 of 20

E2′ (14.4 kB) → E4 (138 kB), within a single edge setting, per-seed median gap:

| edge setting | CondHealthy | CondCongested | CondTransient | CondOutage |
|---|---|---|---|---|
| free, 60 fps *(published pair)* | 5.7× | 7.6× | 7.9× | 15.8× |
| free, 30 fps | 15.8× | 8.3× | 6.6× | 5.5× |
| PC-class, 30 fps | 10.3× | 7.9× | 5.5× | 18.1× |
| PC-class, 60 fps | 19.7× | 11.1× | 9.7× | 2.0× |
| embedded, 60 fps | 6.6× | 6.4× | 6.5× | 22.7× |

**All 20 cells significant (p ≤ 0.012), all in the same direction, 2.0–22.7×.**
*Verify from the waveform, not the image* is robust to the entire sourced range
of edge cost.

---

## 4. Result: the additive magnitude was wrong — the edge is a shared queue

The prediction's *other* half — "about +21 ms at PC-class and +93 ms at
embedded" — is **refuted**. Shift in per-seed median **alert** delay:

| contrast | nominal | CondHealthy | CondCongested | CondTransient | CondOutage |
|---|---|---|---|---|---|
| 30 fps → PC | +22.73 ms | +29.7 ms | +35.8 ms | +33.4 ms | **−135 ms** |
| 60 fps → PC | +22.73 ms | +51.8 ms | +50.9 ms | +49.6 ms | −143 ms (ns) |
| 60 fps → EMB | +94.27 ms | +224 ms | +257 ms | +267 ms | **+735 ms** |

Waveform rung; the image rung agrees everywhere except CondOutage, where it
gives −472 ms (ns), +5.6 ms (ns) and −199 ms. All non-outage cells p ≤ 0.0003. The shift is **1.3–1.6× nominal at 30 fps and
2.1–3.0× nominal at 60 fps**, because the edge is a single FIFO server shared
with the vitals stream: the per-frame latency is service *plus* queueing, and
above saturation it is set by the buffer rather than by the service time.

**In a coverage outage the edge cost stops behaving like a cost.** The alert
shift goes *negative* in four of the six outage contrasts, and the two that
reach significance (p = 0.0059) are both negative — the alert arrives 135 ms and
199 ms **sooner** with the slower edge. The one significant positive is the
embedded waveform arm (+735 ms, p = 0.0192), so this is not a clean reversal;
the honest statement is that in an outage the sign is no longer predictable from
the edge cost. That is the second-order mechanism the prediction's escape clause
named: displacing the escalation instant by hundreds of milliseconds makes it
meet a different radio state, and in an outage the radio (0.47–1.18 s of alert
delay at the free edge) dominates the edge entirely.

### The absolute numbers, now reportable

The headline configuration is **30 fps, PC-class edge, waveform verification at
LF/HF-grade W** — the only measured regime in which inference fits the frame
interval (§2). Median dispatch / % over the 4 s eCall budget:

| condition | E2′ 14.4 kB | E4 138 kB |
|---|---|---|
| CondHealthy | 0.070 s / 0.0 % | 0.276 s / 0.0 % |
| CondCongested | 0.146 s / 2.8 % | 0.608 s / 8.3 % |
| CondTransient | 0.241 s / 9.6 % | 1.036 s / 18.2 % |
| CondOutage | 1.139 s / 34.2 % | 2.381 s / 43.8 % |

---

## 5. What is not solid here

1. **Matching the frame rate is not optional.** The camera stream is uplink
   background load as well as edge load, so a 30 fps arm and a 60 fps arm differ
   in the radio even with an identical edge. Compared *unmatched*, `e2bEMB`
   (60 fps) appears to beat `e2bB30` (30 fps) on budget misses — 1.4 % vs 3.5 %
   in CondCongested, 27.4 % vs 36.1 % in CondOutage — which would read as a
   slower edge improving dispatch. Those two arms sit adjacent in the dispatch
   table; the comparison is meaningless and `edge_contrasts.py` exists to make
   the matched one the easy one to run.
2. **Two levels, from one paper, for a different pipeline.** M4's provenance
   (§2, §A.2) is unchanged by this run.
3. **The 30 fps half is HRV-grade, not PRV-grade.** It is the regime the
   architecture can actually run, which is the point, but it does not satisfy
   C1's variability case at the 60 fps Cerina revises to.
4. **`processingTime` is a constant, not a distribution** at the two sourced
   levels — the paper reports means and its per-stage tables did not survive
   text extraction. The free-edge arm supplies the only spread.
5. **CondOutage conclusions are the weakest**: 27 paired seeds, the largest
   ratios, the only sign inversions, and the widest spread.
6. **CondHealthy remains thin** — 37 escalations, 20 paired seeds, 320 s window.
7. The 0.18 % packet drop at PC-class/30 fps means that arm is not perfectly
   lossless, though it is three orders of magnitude below the saturated arms.

---

## 6. Provenance

```sh
python3 -I tools/dispatch_times.py analysis/edge/escalation_latencies.csv.gz \
        --report-pairing --tol 1.0        # reproduces §3-§4's dispatch table
python3 -I tools/edge_contrasts.py        # reproduces §3-§4's contrasts
```

The first is **identical** to the same command run against the 1.5 GB corpus.
The scalar extract is verified value-by-value:

```
OK: 5356040 values match exactly; 77760 histograms sum to their recorded count
```

Pairing: **100 % of escalations paired** in 29 of 32 cells, and 36/36, 137/138,
142/143 in the other three — the unpaired alerts are escalations whose burst
falls outside the window (signed offsets of −41 s and −326 s, i.e. no burst of
their own), correctly rejected rather than silently collapsed.

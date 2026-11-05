# Results Summary (feeds the manuscript's Results section)

**Regenerated 2026-10-05** after the metric and site-selection corrections
described in `docs/CORRECTIONS_2026-10.md`. Numbers here supersede every
earlier version of this file and the v0.4 manuscript. Do not cite the
pre-correction figures.

Corpus: 7,500 runs / 250 design cells (Family A factorial 7,200 + Family B
case studies 300), plus 300 sensitivity and 90 room-baseline runs.
Sources: `runs_detailed.csv`, `cells_aggregated.csv`, `main_effects.csv`,
`sens/`, `room/`, `vectors/` (3-seed subsets). Figures in `figures/`.

## Metric definitions (read this before quoting anything)

Three metrics that were previously conflated are now reported separately.

| Metric | Definition | Use |
|---|---|---|
| `delivery_e2e` | received / **generated** | feasibility; the honest headline |
| `delivery_uplink` | received / handed-to-radio | what the radio did with its input |
| `timely_<stream>` | (received − late) / **generated** | clinical timeliness |
| `late_<stream>` | arrived after the deadline | *only* counts packets that arrived |
| `undelivered_<stream>` | generated − received | never arrived at all |

`delivery_uplink` excludes anything the sensor link dropped before the uplink,
so on a BLE rig it exceeds `delivery_e2e` by about 13 pp. Quoting `late_*`
alone (as "misses per drive") hides the undelivered packets entirely.

## Main effects, Family A (difference with 95% CI, percentage points)

| Effect | Δ delivery_e2e (pp) | Δ timely vitals (pp) |
|---|---|---|
| Rural ISD 10 km vs 5 km | **−5.99 ± 0.92** | **−10.64 ± 0.56** |
| Urban ISD 2 km vs 0.5 km | −0.46 ± 0.90 | −0.08 ± 0.18 |
| Payload 60 KiB vs 4 KiB (rural) | **−17.59 ± 0.70** | **−7.89 ± 0.62** |
| Payload 60 KiB vs 4 KiB (urban) | **−14.99 ± 0.58** | −0.41 ± 0.13 |
| Speed 105 vs 30 km/h (rural) | −1.29 ± 1.34 | −0.35 ± 0.96 |
| Speed 105 vs 30 km/h (urban) | −2.00 ± 1.03 | −1.88 ± 0.21 |
| Load 20 vs 0 background UEs | **+0.00 ± 0.71** | **+0.00 ± 0.37** |
| Smartphone (BLE) vs embedded (wired) edge | **−12.38 ± 0.51** | **+1.66 ± 0.30** |

Re-derived 2026-10-21 from 7,200 paired runs; the superseded unpaired values
differed by at most 0.4 pp, so every conclusion below survives.

### Reading of the effects

1. **Infrastructure density dominates timeliness.** Doubling rural site
   spacing from 5 to 10 km costs 10.3 pp of timely vitals, an order of
   magnitude more than any speed effect. Within the urban range (0.5–2 km)
   density is a non-factor: the network is delay-limited, not coverage-limited.
   This is a *designed* parameter sweep over synthetic spacing, so unlike the
   case studies it is unaffected by the OpenCellID site-selection problem.
2. **Speed is second-order** (≤2.1 pp across a 3.5× speed range), which
   refutes the confounded r=0.97 "speed dominates" reading of the original
   thesis and confirms its partial-correlation result.
3. **Load-insensitivity is a finding, with a scope caveat:** at 0/8/20
   background UEs per cell the effect is **exactly zero on both metrics**
   (+0.00 ± 0.71 pp delivery, +0.00 ± 0.37 pp timely vitals). This was the
   claim most at risk from the unpaired comparison, since it asserts absence
   of an effect at a magnitude below the drift that was present when it was
   first measured. Pairing made it cleaner, not weaker. Health telemetry
   (~0.1–1 Mbps) is small against LTE cell capacity; feasibility is governed
   by coverage, not contention. Two limits on that claim. The load axis is
   *how many competing UEs*, not how much traffic each offers — Simu5G's
   background generator ignores its `periodUl` parameter entirely (C12 in
   `docs/CORRECTIONS_2026-10.md`), so per-UE offered rate was never varied.
   And in a harsher cell than any in this factorial, 0 → 20 background UEs
   nearly doubles vitals deadline misses, so load does bite once a cell is
   already near its limit.
4. **Payload hurts delivery everywhere, timeliness only in sparse cells.**
   On the corrected denominator, 60 KiB frames cost ~15–18 pp of delivery in
   *both* environments — the earlier figures (−1.6 urban / −4.2 rural)
   understated this four- to tenfold because frames the BLE link dropped were
   excluded from the denominator. The environment-specific part is timeliness:
   −0.6 pp urban against −7.6 pp rural. So the payload × density interaction
   is specifically a *freshness* interaction, not a delivery one.
5. **The BLE edge trades camera data for vitals timeliness.** It delivers
   1.78 pp more timely vitals while delivering 12.67 pp less of everything
   generated: the BLE link saturates near 0.77 Mbps and sheds camera frames at
   the rig, which protects the cellular uplink. Pooled over 3,600 runs per
   arm, camera frames reaching the cloud fall from 90.9% (wired) to 69.3%
   (BLE). This is a defensible design trade, but it is a trade, not a free
   win — the earlier "+0.88 pp delivery advantage" was an artifact of the
   uplink-only denominator and reverses on correction.
   **Caveat on attribution:** in this factorial the camera link, OBD link and
   processing time flip together, so this row does not isolate a cause. The
   de-confounded factorial below shows the camera link is responsible and the
   other two factors are null; cite that one for the mechanism.
   The effect is also stress-dependent — at 4 KiB the two edge types are
   indistinguishable (97.6% vs 97.8% timely vitals), and the trade appears
   only when the camera link saturates.

## De-confounded edge-type factorial (added 2026-10-05)

In Family A the camera link, the OBD link and the edge processing time flip
together (`! camlink` parallel iteration), so the "smartphone vs embedded
edge" effect above conflates three changes and cannot be attributed to camera
admission. `simulations/corridorA` config `RuralEdgeDeconf` crosses the three
factors independently in the stressed cell where the trade-off actually
appears (rural, 10 km ISD, 60 KiB camera, speed 55 km/h, 8 background UEs):
2 × 2 × 2 × 30 seeds = 240 runs, QC passed. Data in `analysis/deconf/`.

Marginal main effects, each averaged over the other two factors:

Corrected 2026-11-04. Regenerate with `tools/analyze_deconf.py`; intervals are
per-seed block contrasts, since `seed-set = ${repetition}` makes every cell
share its seed draws.

| Factor | Δ timely vitals (pp) | Δ timely camera (pp) | Δ delivery_e2e (pp) |
|---|---|---|---|
| Camera link BLE vs wired | **+16.75 ± 1.84** | **−27.65 ± 2.16** | −18.58 ± 1.73 |
| OBD link BLE vs wired | +0.47 ± 1.26 | +0.48 ± 1.43 | +0.20 ± 1.11 |
| Processing slow vs fast | −0.58 ± 1.78 | −1.38 ± 1.62 | −1.03 ± 1.13 |

> The figures previously in this table (+16.28/−28.23, OBD +1.46/+1.64,
> processing +0.72/+0.74) did **not** reproduce from `analysis/deconf/` — all
> nine were off and the three processing-time effects had the wrong sign. The
> data was fine; the table was not. See `docs/CORRECTIONS_2026-10.md` C14.

**The camera link is the entire mechanism.** The OBD link and the edge
processing time are both null within CI, so the confound in Family A was
harmless to the conclusion even though it invalidated the attribution — and
they are null on a roughly twice-tighter test than the original, which pooled
runs rather than blocking on seed and so carried the 28 pp camera-link split
inside the residual variance of the other two factors.

With the other two factors held fixed the camera effect is larger than the
confounded estimate suggested: in this cell BLE throttling buys **+16.8 pp of
timely vitals at a cost of −27.7 pp of timely camera frames**, an exchange
rate of **0.61** pp of vitals per pp of camera given up.

The processing-time effects are small, null, and consistently *negative* across
all three metrics, which is the physically sensible direction (slower edge
processing is slightly worse); timely camera is closest to significant at
−1.38 ± 1.62. Nothing rests on it, but it should not be described as zero.

That exchange rate is the quantity a deliberate edge policy has to beat. BLE
saturation is an *accidental* controller: it sheds frames on link capacity
alone, with no knowledge of vitals urgency, alarm deadlines or radio state.
Any informed policy should be able to protect vitals as well while giving up
less camera data, and the ratio above is the baseline it must improve on.

**But the magnitude is set by the sensor-link buffer, not by BLE bandwidth.**
See the buffer sweep below before quoting +16.75 pp as the effect size.

## Sensor-link buffer sweep (added 2026-10-06)

`BleLink.queueCapacity` defaults to 65536 B while the stressed camera frame is
61440 B, so one frame occupies 94% of the queue and the drop-tail test
rejects every second frame while the first drains. The default therefore makes
the link a one-frame-in-flight system, and the admission behaviour could be an
artifact of that ratio rather than of bandwidth. `RuralBufferSweep` varies the
buffer with everything else fixed: BLE camera link, 60 KiB frames, rural 10 km
cell, 30 seeds, 150 runs. Data in `analysis/bufsweep/`.

| Buffer | frames held | sent to cloud | received | camera late | timely camera | timely vitals |
|---|---|---|---|---|---|---|
| 64 KiB (default) | 1.1 | 102,797 | 91,964 | 1,940 | 38.5% | **87.6%** |
| 128 KiB | 2.1 | 126,506 | 110,735 | 5,765 | 57.8% | 79.7% |
| 256 KiB | 4.3 | 126,506 | 110,735 | 6,394 | 57.0% | 79.7% |
| 512 KiB | 8.5 | 126,506 | 110,735 | 8,012 | 55.0% | 79.7% |
| 1024 KiB | 17.1 | 126,506 | 110,735 | 53,022 | **0.2%** | 79.7% |
| *matched wired reference* | — | — | — | — | *67.9%* | *72.1%* |

Three things follow.

1. **Beyond two frames of buffer the packet counts are bit-identical**
   (QC's R3 flags this, correctly). Bandwidth, not buffer, fixes how much
   gets through once the queue can hold more than one frame. The buffer only
   decides whether excess frames are dropped promptly or queued; the small
   residual drop differences are frames stranded in the queue at the cutoff.
2. **Dropping is what protects vitals, not buffering.** The vitals benefit is
   confined to the 64 KiB cell (87.6%); every larger buffer sits flat at
   79.7%. Holding frames instead of dropping them does not protect the
   cellular path.
3. **Large buffers destroy camera timeliness without buying anything.** At
   1024 KiB delivery is unchanged but 53,022 of the delivered frames arrive
   past their deadline, so timely camera collapses to 0.2%. Textbook
   bufferbloat.

**Consequence for the edge-type effect.** Against the matched wired reference
the exchange rate depends strongly on a parameter nobody tuned:

| Buffer | Δ timely vitals | Δ timely camera | vitals gained per camera pp given up |
|---|---|---|---|
| 64 KiB (default) | +14.9 pp | −29.9 pp | **0.50** |
| 128 KiB | +2.5 pp | −15.2 pp | 0.17 |
| 256 KiB | +2.5 pp | −15.9 pp | 0.16 |
| 512 KiB | +2.5 pp | −17.5 pp | 0.15 |
| 1024 KiB | +2.5 pp | −68.5 pp | 0.04 |

**CORRECTED 2026-10-21 — a claim previously made here is withdrawn.** The
earlier unpaired figures (0.53 / 0.75 / 0.11) supported the statement that
"the default is not the best operating point" and that "a tuned static
configuration already captures a large part of what an adaptive controller
would be claiming". Properly paired, the 64 KiB default is the **best**
operating point of those tested, by roughly a factor of three, and that
statement is withdrawn. The unpaired comparison had flattered the
large-buffer cells by inflating their vitals (79.7% against the true 75.2%).
The argument had been used to position a tuned static buffer as a serious
competitor to the controller; it does not support that.

The +16.75 pp figure in the de-confounded factorial above is still specific
to the 64 KiB default and should be quoted with that condition attached.

## Mechanism decomposition (added 2026-10-06)

The buffer sweep showed dropping protects vitals and buffering does not, but
BLE drops *and* bandwidth-limits simultaneously, so it cannot separate volume
reduction from temporal spreading. `MechNone` / `MechSweep` use the **wired**
camera link — no bandwidth cap, no link drops — and reintroduce each mechanism
through a token-bucket admission gate in `EdgeApp`, placed before
`socket.sendTo()` because once a packet reaches UDP it is committed to the
RLC/PDCP queues. Vitals, OBD and alarms are never gated. The camera source
workload is identical in every arm (2,737 frames/run), so admission reduction
cannot flatter a delivery denominator. 300 runs, 30 seeds per cell.

| Policy | Rate | camera received | timely camera | timely vitals | delivery_e2e |
|---|---|---|---|---|---|
| none (reference) | — | 78.0% | 67.9 ± 2.9% | 72.1 ± 2.1% | 83.6% |
| drop | 400k | 25.7% | 25.4 ± 1.4% | 93.6 ± 1.2% | 55.6% |
| drop | 600k | 42.4% | 40.2 ± 1.6% | 88.7 ± 2.1% | 65.0% |
| drop | 800k* | 42.4% | 40.2 ± 1.6% | 88.7 ± 2.1% | 65.0% |
| pace | 400k | 33.0% | 30.6 ± 1.0% | 91.1 ± 1.4% | 59.6% |
| pace | 600k | 51.5% | 46.2 ± 1.7% | 84.7 ± 2.5% | 69.8% |
| pace | 800k | 65.5% | 56.1 ± 2.4% | 75.7 ± 2.2% | 76.8% |
| dropPace | 400k | 33.0% | 31.6 ± 1.0% | 91.1 ± 1.4% | 59.6% |
| dropPace | 600k | 51.5% | 47.0 ± 1.7% | 84.7 ± 2.5% | 69.8% |
| dropPace | 800k | 65.5% | 56.4 ± 2.4% | 75.7 ± 2.2% | 76.8% |

\* `drop` saturates above 600 kbps: `cameraBurst` is 65536 B and a frame is
61440 B, so the bucket holds only 1.07 frames and drop-on-arrival cannot
admit more regardless of rate. The 800k drop row is **not** a valid
higher-rate point; a larger burst is needed for a fair comparison there.

### 1. Volume reduction beats temporal spreading

Comparing at equal vitals protection (interpolating along each policy's
curve, excluding the burst-limited drop point):

| Vitals target | camera retained, drop | camera retained, pace | drop advantage |
|---|---|---|---|
| 88.7% | 40.2% | 36.4% | **+3.8 pp** |
| 90.0% | 36.3% | 33.3% | **+3.0 pp** |
| 91.1% | 33.0% | 30.6% | **+2.4 pp** |

Dropping is the more efficient mechanism. Delaying a camera frame still
injects its bytes into the cellular path, just later, where they still
compete with vitals; only discarding removes the work. This confirms the
first half of the hypothesis that reducing camera work entering the cellular
path reduces critical-traffic queueing. The second half — that pacing adds
benefit during capacity changes — is **not** supported here, but this scenario
has only handover-driven variation and is not a controlled capacity-drop
test, so it is untested rather than refuted.

### 2. Staleness discard is free timeliness

`dropPace` admits exactly the same number of frames as `pace` (33,412 /
50,110 / 66,806 at the three rates) and the sent and received counts are
bit-identical — QC's R3 flags this correctly. What changes is *which* frames
go: discarding a frame older than 2 s frees queue room for a newer one. Of
48,578 gate drops in `dropPace@400k`, 37,631 are staleness discards and the
rest capacity drops (staleness discards are a subset of gate drops, so the
accounting closes at ~82,110 generated).

Result: **+0.3 to +1.0 pp timely camera at identical throughput**. Small, but
free and in the direction the freshness literature predicts.

### 3. An explicit gate already beats the accidental one

Against the BLE 64 KiB cell from the buffer sweep (same scenario):

| | timely vitals | timely camera |
|---|---|---|
| BLE drop-tail (accidental) | 87.6% | 38.5% |
| gate, drop @600k (deliberate) | **88.7%** | **40.2%** |

The deliberate token bucket dominates the accidental drop-tail on *both*
axes. The margin is modest, but it establishes that the gate is a real
control surface and not merely a reimplementation of what BLE was doing.

### What this means for a controller

The ordering is now established: discard beats delay, and discarding the
*oldest* beats discarding arbitrarily. A controller that adds radio-state
awareness has to beat `drop` + staleness discard at a tuned rate, which is a
considerably stronger baseline than the FIFO reference. That is the
comparison the pilot must make.

## Family B case studies (real maps, per-operator real towers)

Each config is one operator's site set, keeping every site that is among the
2 nearest anywhere on the route; each `towers_*.ini` carries an AUDIT block
showing the route's distance-to-nearest-site profile is identical to that of
the operator's full site set. 30 seeds each.

| Config | sites | delivery_e2e | timely vitals | timely alarm | timely camera | p95 | p99 |
|---|---|---|---|---|---|---|---|
| DC AT&T | 16 | 99.2 ± 0.3% | 99.6% | 100% | 98.9% | 0.38 s | 1.00 s |
| DC T-Mobile | 12 | 99.5 ± 0.3% | 99.7% | 100% | 99.2% | 0.06 s | 0.99 s |
| DC Verizon | 9 | 99.4 ± 0.3% | 99.7% | 100% | 99.1% | 0.24 s | 1.00 s |
| VA AT&T | 23 | 91.7 ± 0.8% | 92.3% | 84.0% | 89.9% | 1.00 s | 6.90 s |
| VA T-Mobile | 21 | 89.7 ± 0.6% | 90.9% | 88.5% | 88.3% | 2.20 s | 7.00 s |
| VA Verizon | 24 | 92.7 ± 1.4% | 92.7% | 95.2% | 90.8% | 1.44 s | 12.60 s |
| *VA superseded* | *8* | *65.0 ± 0.6%* | *65.5%* | *71.7%* | *62.6%* | *4.20 s* | *16.00 s* |

The superseded row pools three operators and keeps the 8 densest clusters of
88. It is retained as a site-selection sensitivity arm and reproduces the
previously published numbers exactly; it is **not** a result.

**The urban/rural gap is real but far smaller than published:** about 7 pp of
delivery and 7–9 pp of timely vitals, not 33 pp. There is no coverage gap and
no multi-minute outage on these routes for any single operator.

### Alarm reliability — controlled study (added 2026-10-07)

The primary configs keep the design alarm rate, which cannot resolve
reliability (see below). `VaDriveAttAlarm` / `DcDriveAttAlarm` raise the rate
tenfold purely for statistical exposure — a sampling device, not a claim about
how often patients raise alarms — and stop alarm generation one 5 s deadline
before the cutoff so no alarm is censored. 30 seeds each, data in
`analysis/extra/`.

| Config | generated | received | late | undelivered | timely/generated | 95% CI | width |
|---|---|---|---|---|---|---|---|
| DC AT&T | 534 | 533 | 0 | 1 | **99.8%** | [98.9, 100.0] | 1.0 pp |
| VA AT&T | 810 | 765 | 19 | 45 | **92.1%** | [90.0, 93.8] | 3.7 pp |
| *VA at design rate* | *50* | *43* | *1* | *7* | *84.0%* | *[71.5, 91.7]* | *20.2 pp* |

The interval narrows from 20.2 pp to 3.7 pp, which makes the rural alarm
shortfall a measurable result rather than noise: **about 8% of alarms miss
their 5 s deadline on the rural corridor** — 45 never arrive and 19 arrive
late out of 810 — against 0.2% urban. The design-rate point estimate (84.0%)
sits just at the edge of the new interval, so the two are consistent; 92.1% is
the better estimate.

This is now a supportable statement where the earlier "0.033 misses per drive"
was not. It is still a normal-operation figure: conditional reliability during
outages and handovers needs its own stress study.

### Alarm reliability at the design rate (why the study above was needed)

Alarms are generated as `exponential(300 s)`, so a 922 s drive yields ~3 per
run and the whole 30-run corpus yields 50–98 alarms per config. Pooled, with
Wilson 95% CIs:

| Config | timely / generated | 95% CI | CI width |
|---|---|---|---|
| VA AT&T | 42/50 = 84.0% | [71.5, 91.7] | 20.2 pp |
| VA T-Mobile | 85/96 = 88.5% | [80.6, 93.5] | 12.8 pp |
| VA Verizon | 59/62 = 95.2% | [86.7, 98.3] | 11.6 pp |
| VA superseded | 68/98 = 69.4% | [59.7, 77.6] | 18.0 pp |
| all DC configs | 100% | — | — |

Two things follow. Rural alarm delivery is **not** the near-perfect service
the earlier "0.033 misses per drive" figure implied: that number counted only
late arrivals among alarms that arrived, and ignored the 7–11 per config that
never did. And the alarm stream is far too sparse for this corpus to resolve
reliability better than ±10–20 pp, so **no confident alarm claim can be made
from these runs**. A dedicated higher-rate alarm study is needed before any
safety-critical statement.

## Age of Information

Computed over the **full configured observation window**, not up to the last
received update (`figures_src/_shared.py:aoi_series`). Budget 10 s, 3
vector-recorded seeds per config.

| Config | peak (mean of 3) | peak (worst) | mean AoI | % of drive above budget |
|---|---|---|---|---|
| DC AT&T | 6.5 s | 7.0 s | 1.0 s | 0.0% |
| DC T-Mobile | 6.2 s | 7.0 s | 1.0 s | 0.0% |
| DC Verizon | 6.2 s | 7.0 s | 1.0 s | 0.0% |
| DC superseded | 6.3 s | 7.0 s | 1.0 s | 0.0% |
| VA AT&T | 31.6 s | 48.5 s | 2.1 s | 3.9% |
| VA T-Mobile | 29.8 s | 35.6 s | 2.3 s | 4.2% |
| VA Verizon | 21.3 s | 26.3 s | 1.9 s | 3.4% |
| *VA superseded* | *142.6 s* | *148.6 s* | *17.0 s* | *30.6%* |

Re-derived 2026-10-22 from vector subsets regenerated under the paired RNG
mapping. The qualitative picture is unchanged: the urban corridor never goes
stale, the per-operator rural corridors spend 3–4% of the drive above the
10 s budget with peaks of 21–32 s, and the superseded 8-of-88-site selection
is an order of magnitude worse on every measure.

The rural freshness penalty is real — peak AoI roughly 3× urban, and 2–3% of
the drive above budget against 0% urban — but it is tens of seconds, not the
two minutes previously reported. Three seeds is too few for a distribution;
these are illustrative.

## Site-reduction sensitivity (added 2026-10-07)

The headline per-operator configs keep every site among the 2 nearest anywhere
on the route, justified by showing the distance-to-nearest-site profile is
identical to the operator's full set. That verified coverage *geometry* only.
These arms raise the serving rank so radio and application outcomes can be
compared. AT&T rural corridor; 15 seeds for the sensitivity arms.

| Config | sites | n | delivery_e2e | timely vitals | mean E2E |
|---|---|---|---|---|---|
| K2 (headline) | 23 | 30 | 91.7 ± 0.5% | 92.3% | 392 ms |
| K3 | 25 | 15 | 92.4 ± 0.6% | 92.4% | 408 ms |
| K4 | 27 | 15 | 91.9 ± 1.0% | 93.0% | 350 ms |

Delivery varies by 0.7 pp across serving rank 2→4 with overlapping intervals,
timely vitals by 0.7 pp, and mean delay by under 60 ms with no monotone trend.
**The reduction is now verified for outcomes, not only for geometry** — the
outstanding caveat in `docs/CORRECTIONS_2026-10.md` is closed. Adding the
remaining 14 candidate sites would mean a full 41-site X2 mesh, which is
computationally prohibitive here (roughly 24 minutes per 60 s of simulated
time); the flatness from 23 to 27 sites is the available evidence.

## Room baseline

| Config | delivery_e2e | timely vitals | mean E2E | n |
|---|---|---|---|---|
| 2.4 GHz | 100.00% | 100.00% | 7.2 ms | 30 |
| 5 GHz | 100.00% | 100.00% | 7.0 ms | 30 |
| 5 GHz, camera over BLE | 99.98% | 99.97% | 58.2 ms | 30 |

Under single-user load the WiFi band is immaterial.

### Matched room configuration (added 2026-10-07)

The configs above are the indoor deployment as originally designed, and they
are **not** comparable with the vehicular runs: 0.1 s camera interval against
0.5 s, `uniform(1ms, 5ms)` edge processing against `uniform(0.5ms, 2ms)`, no
OBD stream, and no BLE PDU error process. `RoomMatched*` holds the sensor rig
identical to `dc_case` so the only difference between settings is the backhaul.
30 seeds each, data in `analysis/room_matched/`.

| Config | delivery_e2e | timely vitals | mean E2E |
|---|---|---|---|
| Room 2.4 GHz, as designed | 100.00% | 100.00% | 7.2 ms |
| Room 5 GHz, as designed | 100.00% | 100.00% | 7.0 ms |
| **Room 2.4 GHz, matched** | **100.00%** | **100.00%** | **8.7 ms** |
| **Room 5 GHz, matched** | **99.99%** | **99.99%** | **8.6 ms** |
| Vehicle, urban LTE (DC AT&T) | 99.20% | 99.60% | 62.0 ms |

Matching the workload moves indoor mean delay from 7.0 to 8.7 ms and leaves
delivery at essentially 100%. **The critique was valid in principle but the
effect is immaterial**: the indoor setting is roughly seven times faster than
the urban vehicular one and effectively lossless under either configuration,
so the room-to-road contrast survives matching. Quote the matched numbers
(≈8.6 ms) when comparing settings, and the as-designed numbers only when
describing the indoor deployment on its own terms.

## Sensitivity analysis

300 runs (`sens/`), 5 channel variants, representative urban (1 km ISD) and
rural (10 km ISD) cells. Conclusions were unchanged by the corrections, since
the sensitivity arms are Family A cells and the comparison is within-metric.
Re-exported with the corrected metrics; see `sens/cells_aggregated.csv`.

## Figures

- `fig1_feasibility_heatmap` — timely-vitals % over ISD × speed × payload
- `fig2_delay_ecdf` — per-operator DC vs VA delay distributions vs budgets
- `fig3_delivery_vs_isd` — density effect with CIs, on `delivery_e2e`
- `fig4_aoi_timeseries` — full-horizon AoI, with the superseded site selection
  overlaid on the rural panel for contrast
- `fig5_cqi_vs_distance` — channel-quality falloff, per-operator towers

## Known limitations carried forward

- Histogram-based `delay_p50` is bin-limited for fast configs (reads 0 ms);
  use the vector subsets for precise low quantiles.
- AoI rests on 3 seeds per config.
- Alarm reliability is unresolvable at the current alarm rate (above).
- OpenCellID positions are *estimated* cell locations from crowd-sourced
  measurements, and a missing record is not evidence of absent service.
  Coverage derived from them is **inferred**, not measured.

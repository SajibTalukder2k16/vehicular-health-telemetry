# Corrections of 2026-10 — what changed, why, and what it invalidates

An external review of draft v0.4 raised five issues. All five were checked
against the corpus and all five were confirmed; two were worse than the review
stated. This memo records what was wrong, what it affected, and what was done.
Every number in `analysis/EFFECTS_SUMMARY.md` and in the figures postdates
these corrections. **The v0.4 manuscript predates them and should not be
circulated.**

---

## C1. Tower site selection manufactured the rural coverage gap

**Severity: invalidates the central empirical claim of Family B.**

`tools/opencellid_towers.py` sorted clusters by cell count and kept the
`--max-sites` densest. For the rural Virginia corridor that meant 204 LTE
cells → 88 clusters → **8 kept**, discarding 80. The discarded clusters are
the 1–2-cell ones, which is exactly what a rural site looks like in
OpenCellID. The script also never filtered by operator, so those 8 sites
pooled three carriers (T-Mobile 79 cells, AT&T 77, Verizon 48) into one
network no subscriber can actually use.

Route distance to the nearest site, rural VA:

| site set | max | p95 | % of drive beyond 4.5 km |
|---|---|---|---|
| 8 densest, operators pooled (published) | 4.86 km | 4.63 km | **7.8%** |
| all 88 clusters | 2.43 km | 2.07 km | **0.0%** |
| AT&T, all 41 | 3.52 km | 2.47 km | 0.0% |
| T-Mobile, all 42 | 2.41 km | 2.04 km | 0.0% |
| Verizon, all 40 | 2.47 km | 2.12 km | 0.0% |

**The "measured 7.6% coverage gap" is not in the data.** It is a consequence
of `--max-sites 8`. No single operator has a gap on this route.

The bias is also asymmetric in the direction that flattered the paper's
thesis: truncation costs the dense DC extract almost nothing (max distance
0.61 km against 0.22 km with all sites) but costs the rural route 2.4 km of
margin. It amplified precisely the urban/rural contrast the paper claimed to
discover.

**Fix.** The script now requires `--mnc` (or an explicit `--allow-pooled`),
selects by route proximity rather than density, offers `--serving-rank K` to
keep every site that is among the K nearest anywhere on the route, and writes
an AUDIT block into every generated file giving the route's
distance-to-nearest-site profile before and after selection, with a warning if
selection raised the gap fraction. Family B was re-run as six per-operator
configs (K=2, which preserves each operator's coverage profile exactly) plus
two `Legacy8` arms that reproduce the superseded selection for comparison.

**Effect on results.** Rural delivery rises from 65.0% to 89.7–92.7%; the
urban/rural delivery gap falls from 33 pp to about 7 pp. The gap is still
real and still larger than the urban case, but it is a cell-edge SINR effect
at 2–3.5 km, not an outage.

## C2. AoI was truncated at the last received update

**Severity: understated the headline freshness number, and mis-ranked seeds.**

`fig4_aoi_timeseries.py` built the AoI staircase only up to the last arrival,
so a final outage that never ends before the simulation cutoff was invisible.
On the rural corridor the last vitals update arrived at t=691 s and t=739 s of
a 922 s drive in two of three seeds.

| seed | peak as published | peak over full window |
|---|---|---|
| 0 | 121.0 s | 121.0 s |
| 1 | 25.1 s | **231.7 s** |
| 2 | 87.8 s | **189.7 s** |

The published range "25–121 s" was wrong in both directions, and the seed
reported as mildest was in fact the worst.

**Fix.** `figures_src/_shared.py` now owns `aoi_series()` and `aoi_stats()`,
both of which take a mandatory `horizon` read from the scenario's
`sim-time-limit`; the figure and the new `analysis/aoi_metrics.py` table share
that one implementation so they cannot diverge again. Reported metrics are now
peak, mean, and time above the freshness budget, not peak alone.

## C3. Alarm reliability was reported on a denominator that hid losses

**Severity: the safety-critical claim was unsupported.**

The manuscript reported alarm deadline misses "once per thirty drives"
(0.033/drive). That counts only alarms that *arrived* late. Across the 30
published rural runs: **98 alarms generated, 69 received, 1 late.** Timely
against generated is **69.4%** — the other 29 never arrived and were not
counted anywhere.

**Fix.** The exporter now emits `generated_`, `received_`, `late_`,
`undelivered_`, `delivered_` and `timely_` per stream, so all three outcomes
stay visible. On corrected per-operator sites rural alarm timeliness is
84.0–95.2%.

**New limitation found while fixing it.** At `exponential(300 s)` the corpus
yields only 50–98 alarms per config, giving Wilson 95% CIs 12–20 pp wide. The
corpus cannot resolve alarm reliability, and no confident alarm claim should
be made from it. A dedicated higher-rate alarm study is required.

## C4. Delivery excluded pre-uplink loss from its denominator

**Severity: reversed the sign of a headline finding.**

`delivery` was `received / packetsSentToCloud`, so anything the BLE sensor
link dropped before the uplink left the denominator. Pooled over 3,600 runs
per arm:

| edge | published (rcv/sent) | true (rcv/generated) | camera frames delivered |
|---|---|---|---|
| BLE | 94.88% | **81.33%** | 69.28% |
| wired | 93.34% | 93.34% | 90.94% |

The reported "+0.88 pp delivery advantage for the smartphone/BLE edge"
reverses to **−12.67 pp** on the corrected denominator. The mechanism is real
— BLE throttling does protect vitals timeliness, which gains 1.78 pp — but it
pays for that with 21.7 pp of camera frames. It is a trade, and was published
as a free win.

The payload effect was also understated four- to tenfold for the same reason
(urban −1.62 → −15.28 pp; rural −4.21 → −17.58 pp), because dropped 60 KiB
frames were excluded from the denominator.

**Fix.** `delivery_e2e` (generated-to-received) and `delivery_uplink`
(the old ratio) are both exported and the distinction is documented in
`EFFECTS_SUMMARY.md`. `main_effects.csv` and `fig3` use `delivery_e2e`.
`bleDrops` now counts every BLE link rather than only `bleWearable`.

## C5. The room and vehicle configurations are not comparable

**Severity: the room-to-road comparison as framed is invalid.**

The room scenario uses a 0.1 s camera interval against 0.5 s in the vehicle,
`uniform(1ms, 5ms)` edge processing against `uniform(0.5ms, 2ms)`, and no OBD
stream. The two settings are different deployment configurations, not one
system observed in two places.

**Status: documented, not yet fixed.** `EFFECTS_SUMMARY.md` now states the
mismatch wherever the room results appear. A matched room configuration is
outstanding work. Until it exists the manuscript must describe these as
distinct configurations.

## C6. Abstract compared quantities of different kinds

The abstract set 121 s of information age against 7 ms of room packet delay.
These are not the same quantity and must not be presented as comparable
outcomes. Not yet fixed — the manuscript has not been rewritten.

---

## What survives

The Family A factorial is **unaffected by C1**: it sweeps synthetic site
spacing, not OpenCellID geometry. Its primary findings stand —
infrastructure density dominates timeliness (−10.26 pp timely vitals from 5
to 10 km ISD), speed is second-order (≤2.1 pp), background load is nil, and
the payload × density interaction is the failure mode. The de-confounded
design and the refutation of the old thesis's r=0.97 speed claim also stand.
What changed within Family A is the magnitude of the payload effect and the
sign of the edge-type effect, both from C4.

## What does not survive

- The 7.6% "measured coverage gap" on the rural corridor.
- The 121 s AoI headline and the digital-health-divide framing built on it.
- The 65% rural delivery figure and the 33 pp urban/rural contrast.
- The claim that alarms are near-perfectly delivered on rural infrastructure.
- The "+1.7 pp free advantage" reading of the smartphone/BLE edge.
- Route-level gap audits as a planning instrument, since the full-data profile
  shows no gap to audit on these corridors.

## C7. The edge-type effect was confounded (raised in the second review round)

**Severity: invalidated the attribution, not the finding.**

In `[Config Rural]` the camera link, the OBD link and the edge processing time
are tied by parallel iteration (`! camlink`), so "smartphone vs embedded edge"
changed three things simultaneously. The reported effect could not be
attributed to camera admission.

**Fix.** Added `[Config RuralEdgeDeconf]`, a 2 × 2 × 2 × 30-seed factorial
crossing the three factors independently in the stressed cell (rural, 10 km
ISD, 60 KiB camera). 240 runs, QC passed.

**Result: the attribution survives.** The camera link carries the whole
effect (+16.28 ± 1.69 pp timely vitals, −28.23 ± 1.70 pp timely camera);
the OBD link (+1.46 ± 2.66) and processing time (+0.72 ± 2.67) are both null
within CI. Family A's edge-type row should still be cited only with the
caveat, and the mechanism claim should cite `RuralEdgeDeconf`.

> **Numbers corrected 2026-11-04 — see C14. The conclusion above stands; every
> figure in it is wrong.** None of the published estimates reproduces from
> `analysis/deconf/`, and all three processing-time effects had the wrong sign.
> Use the recomputed table in C14, or regenerate it with
> `tools/analyze_deconf.py`.

## C8. The sensor-link drop counter missed two of three links

`bleDrops` matched module names containing `ble`, but the rig's link
submodules are named `bleWearable`, `camLink` and `obdLink`
(`src/nodes/SensorRig.ned`), and the latter two keep those names whichever
`ILink` type is plugged in. The counter therefore only ever saw the wearable,
regardless of link type. Renamed to `linkDrops` and matched on the three
submodule names.

Diagnostic only: `delivery_e2e` and `preUplinkLoss` compare generated against
sent-to-cloud and were never affected.

## C9. The camera-link effect size is set by an untuned buffer default

**Severity: qualifies C7's magnitude; does not overturn it.**

`BleLink.queueCapacity` defaults to 65536 B while the stressed camera frame is
61440 B, so one frame occupies 94% of the queue and the drop-tail test
(`queueBytes + 61440 > 65536`) rejects every second frame while the first
drains. At 60 KiB the link is therefore a one-frame-in-flight system, and the
"accidental admission control" behaviour could be an artifact of that ratio
rather than of BLE bandwidth.

`[Config RuralBufferSweep]` varies only the buffer (150 runs, BLE camera,
60 KiB frames, rural 10 km). Results in `analysis/EFFECTS_SUMMARY.md`. Three
findings:

- Beyond two frames of buffer the packet counts are **bit-identical** —
  bandwidth fixes throughput once the queue holds more than one frame, and
  the buffer only decides whether excess frames are dropped or delayed.
- **Dropping protects vitals; buffering does not.** The vitals benefit exists
  only at 64 KiB (87.6%); every larger buffer is flat at 79.7%.
- Large buffers destroy camera timeliness without compensating gain: at
  1024 KiB delivery is unchanged but timely camera collapses to 0.2%
  (bufferbloat).

**Consequence.** The exchange rate against the matched wired reference moves
from 0.53 (64 KiB) to 0.75 (128 KiB) to 0.11 (1024 KiB) pp of vitals per pp of
camera surrendered. The default is not the best operating point, and a tuned
static buffer recovers much of what an adaptive controller would claim. The
+16.28 pp figure from C7 is specific to the 64 KiB default and must be quoted
with that condition.

## C10. Alarm deadline censoring at the simulation cutoff

`undelivered_alarm = generated − received` conflates genuine loss with alarms
still in flight when the run ends.

**Quantified.** Alarm arrivals are Poisson, so arrival times are uniform over
the drive and the censored share is the fraction of the observation window
within one deadline of the cutoff: 5 s / 922 s = **0.54%** on the rural
corridor (~0.5 of 98 observed alarms), 0.96% on the urban one. That is about
0.5 pp against a Wilson CI of 12–20 pp, so the bias is immaterial at present.

Note it does **not** shrink as the alarm rate rises — it is a fraction of time,
not of count. The clean fix is `*.rig.alarm.stopTime = <sim-time-limit minus
alarm budget>` (`SensorSource` already has `stopTime`), and it should be
applied as part of the alarm-rate re-run rather than as a separate campaign.

## C11. Resolved — the three outstanding verifications (2026-10-07)

**Site reduction, now verified for outcomes.** `--serving-rank 2` had been
justified only by an unchanged distance-to-nearest-site profile, which is
coverage geometry and nothing more. Serving ranks 3 (25 sites) and 4 (27
sites) were run on the AT&T rural corridor: delivery moves 91.7 / 92.4 / 91.9%
with overlapping intervals, timely vitals 92.3 / 92.4 / 93.0%, mean delay
392 / 408 / 350 ms with no monotone trend. The reduction does not change radio
or application outcomes over that range. A full 41-site mesh is
computationally prohibitive (~24 min per 60 s simulated), so the flatness from
23 to 27 sites is the available evidence. The audit-block wording remains
appropriately narrow.

**Alarm reliability, now measurable.** A controlled study at ten times the
design alarm rate, with generation stopped one deadline before the cutoff,
narrows the Wilson interval from 20.2 pp to 3.7 pp. Rural alarm timeliness is
92.1% [90.0, 93.8] against 99.8% urban: about 8% of alarms miss their 5 s
deadline on the rural corridor (45 never arrive, 19 arrive late, of 810). The
design-rate estimate of 84.0% sits at the edge of the new interval, so the two
are consistent. This supersedes C3's "unresolvable" status for
normal-operation reliability; conditional reliability during outages and
handovers still needs a stress study.

**Room comparison, now matched.** `RoomMatched*` holds the sensor rig
identical to `dc_case`. Matching moves indoor mean delay from 7.0 to 8.7 ms
and leaves delivery at essentially 100%. C5 was valid in principle but the
effect is immaterial — the indoor setting is ~7x faster than urban vehicular
and effectively lossless either way, so the room-to-road contrast survives.
Quote the matched figures when comparing settings.

Remaining known limitation: the `drop` admission policy is burst-limited above
600 kbps (`cameraBurst` 65536 B against a 61440 B frame), so high-rate drop
points need a larger burst before they are valid.

## C12. Simu5G's background generator ignores periodUl (model limitation)

Found while building the pilot conditions, and worth recording because it
bounds what the background load factor can mean.

Changing `bgTrafficGenerator[0].bgUE[*].generator.periodUl` from
`uniform(5ms,15ms)` to `uniform(200ms,400ms)` -- a 40x change in offered rate
-- gives **bit-identical** results: same `totalPacketsReceived` (889), same
`deadlineMisses_vitals` (103). The parameter is declared `volatile` in
`TrafficGeneratorBase.ned` and binds correctly in the recorded run attributes,
so the generator simply never consults it.

`numBgUes` does work: 0 / 20 / 60 UEs give 980 / 889 / 951 packets received and
57 / 103 / 101 vitals misses in the same scenario.

**Effect on existing results: none.** The Family A load factor varies
`numBgUes` (0/8/20), not `periodUl`, so "background load has no measurable
effect" remains a statement about the number of competing UEs and is
unaffected. What it never tested is per-UE offered rate, and that should be
stated rather than implied -- the load axis is "how many competing users",
not "how much traffic".

Note also that in the harsher pilot config, 0 -> 20 background UEs nearly
doubles vitals misses (57 -> 103), where Family A found load immaterial. Not a
contradiction -- different cells -- but it suggests load matters once a cell is
already near its limit, which is worth a sentence wherever the null result is
quoted.

Consequence for the pilot: transient capacity variation is produced by site
geometry (the UE driving deep toward cell edge and back) rather than by a
synthetic load step. See `docs/PILOT_CONDITIONS.md`.

**Superseded on 2026-11-02 by C13, which is worse than C12 and subsumes it.**
The generator does not "ignore `periodUl`" — it never starts, so there is no
period to consult, and `numBgUes` does *not* work either. Read C13 instead.

## C13. No background traffic was ever generated, in any run of this project

Found 2026-11-02 by the low-load campaign, which was run to bound the
headline's external validity and instead invalidated the load axis entirely.

**The observation.** 490 runs at `bgues=2` (7 corridors × 7 arms × 10 seeds),
validated 490/490 with zero failures, produced analysis output *identical to
the `bgues=20` campaign on every line but the directory name* — +34.8 ± 13.9 pp
at TEST 3, +24.0 ± 16.0 pp at TEST 4, c08 at +0.2 ± 9.2, all to one decimal
across seven corridors. Two load levels cannot agree like that.

The `.sca` files do differ, but only in `config`/`attr`/`itervar` lines and in
`scalar *.bg*` lines. Every scalar the metrics read is bit-identical:

```
$ diff <(grep -E '^scalar \S*\.rig\.(wearable|camera) ' results_seeds10/c08-aimd-s07.sca | sort) \
       <(grep -E '^scalar \S*\.rig\.(wearable|camera) ' results_lowload/c08-aimd-s07.sca | sort)
(no output)
```

**The parameter did apply.** 20 `bgUE` modules per eNodeB at high load against
2 at low (4320 vs 432 generator scalars). So the earlier verification — "the
parameter was verified to take effect (2 versus 20 `bgUE` modules
instantiated)" — was true and insufficient: it confirmed the modules exist, not
that they do anything.

**They do nothing.** Every background-UE statistic in every archive is
`count 0`, `mean nan` — checked across `corridorpop`, `pilot`, `dc_case` and
`va_case`. Not one background packet has ever been generated in this project.

**Root cause.** `TrafficGeneratorBase.ned` defaults `startTimeUl` and
`startTimeDl` to `-1s`, and `TrafficGeneratorBase.cc:73` schedules the first
packet only `if (startTime_[UL] >= 0.0)`. No `.ini` in this project sets either
one, and `-1s` is recorded in every result file. The ini set `numBgUes`,
`packetSizeUl` and `periodUl` — and the two that were set are precisely the two
that do nothing until the one that was not set is.

Comparing against Simu5G's own working examples (`simulations/nr/bgTraffic`,
`simulations/nr/videostreaming_dataset_generator`), three settings are required
and all three are absent here:

| Setting | Simu5G examples | This project |
|---|---|---|
| `generator.typename` | `"TrafficGeneratorCbr"` | unset → abstract `TrafficGeneratorBase` |
| `generator.startTimeUl` | `uniform(0s,0.05s)` | unset → `-1s`, never starts |
| `bgUE[*].mobility.initialX/Y` | per-cell, around each gNB | unset → placed off-geometry |

**Setting `startTimeUl` alone is not enough.** A smoke test with
`startTimeUl=0s` on c08 aborts at `t=0s`, event #3:

```
<!> Error: LOS rural macrocell path loss model is valid for d < 10000 m
    -- in module CorridorNet.eNodeB[0].cellularNic.bgTrafficGenerator[0].bgUE[0].generator
```

With no `mobility.initialX/Y`, each `bgUE`'s `StationaryMobility` is placed
without reference to its own eNodeB, and on a playground sized to a real 20 km
corridor it lands outside the RMa model's 10 km validity. A working load axis
needs per-eNodeB placement generated from the tower coordinates — the same
10 km limit already recorded in `docs/PILOT_CONDITIONS.md`.

**What this does not touch.** Both arms of every comparison ran under identical
conditions, so every *policy contrast* stands exactly as measured: the
static-vs-adaptive headline (+34.8 ± 13.9 pp vs the per-corridor oracle,
+24.0 ± 16.0 pp vs the per-seed oracle), the Pareto result, and the
cross-stream signal null (+0.7 ± 1.1 pp). None of them depended on background
load being present.

**What it does touch.**

1. **Scope.** The paper cannot describe its radio as carrying 2 or 20
   competing UEs per cell. There is one active UE in the network: the rig.
   Every number is a single-vehicle, otherwise-idle-cell number.
2. **A null result that was structurally guaranteed.** "Background load is
   immaterial on real corridors" (`CORRIDOR_REGIME.md`) and Family A's "load
   effect of exactly 0.00 pp" are both true and both vacuous — no experiment
   could have returned anything else. A null that was forced by configuration
   is not evidence, and the 0.00 pp figure must not be quoted as one.
3. **C12's `numBgUes` claim is wrong.** The 980 / 889 / 951 packets and
   57 / 103 / 101 vitals misses at 0 / 20 / 60 UEs cannot be background
   contention, because no background packet was sent at any of the three
   settings. The series is also non-monotonic — 20 UEs worse than 60 — which is
   the shape of noise, not load. The likely mechanism is perturbation of the
   RNG stream and event order by the extra modules (`enablePeriodicCqiUpdate`
   defaults `true`, so each `bgUE` schedules CQI feedback events even with no
   traffic to send). *That mechanism is plausible and unverified* — what is
   verified is that background traffic cannot be the cause. The sentence built
   on it, "load matters once a cell is already near its limit", has no support
   and is withdrawn.
4. **The regime story needs re-attributing, not deleting.** The corridors
   genuinely differ — c08 at 97.5/35.0 against c14 at 42.0/15.0 under a
   400 kbps cap — and that spread is real, measured on real tower geometry.
   It comes from site density, distance and handover, not from competing
   traffic. The regime framing survives with contention removed from the
   explanation.

**Method note.** The pre-registered expectations for this campaign were that
the controller would help less at low load, equally, or more. The outcome was
none of the three: the two load levels were the same experiment. A
pre-registered decision rule constrains interpretation only within the
instrument's validity, and that is the second time in a week this project has
had a rule ready to license a conclusion from a broken instrument (see the
frontier-statistic correction in `docs/ABLATION_CROSS_STREAM.md`). The
load-level agreement was caught only because the two campaigns were compared
digit by digit rather than read separately.

## C14. The de-confounding table's numbers were all wrong (conclusion unaffected)

Found 2026-11-04 by the first adversarial pass over C7. The de-confounding
result had been reported without a script that regenerates it, so it had never
been recomputed. When it was, **not one of the nine published point estimates
reproduced from the committed data, and all three processing-time effects had
the wrong sign.**

The data itself is sound: `analysis/deconf/cells_aggregated.csv` matches
`runs_detailed.csv` to 6 decimal places on all 8 cells, the design is the
balanced 2x2x2x30 it claims (240 runs, 8 cells, 30 seeds each, 0..29), and
cell-mean and per-run averaging agree exactly. The error is in the reported
table, not the campaign.

| Factor | metric | published | recomputed | note |
|---|---|---|---|---|
| Camera link BLE vs wired | timely vitals | +16.28 ± 1.69 | **+16.75 ± 1.84** | |
| | timely camera | −28.23 ± 1.70 | **−27.65 ± 2.16** | |
| | delivery_e2e | −18.83 ± 1.20 | **−18.58 ± 1.73** | |
| OBD link BLE vs wired | timely vitals | +1.46 ± 2.66 | **+0.47 ± 1.26** | 3x smaller |
| | timely camera | +1.64 ± 3.97 | **+0.48 ± 1.43** | 3x smaller |
| | delivery_e2e | +1.04 ± 2.67 | **+0.20 ± 1.11** | 5x smaller |
| Processing slow vs fast | timely vitals | +0.72 ± 2.67 | **−0.58 ± 1.78** | **sign flip** |
| | timely camera | +0.74 ± 3.97 | **−1.38 ± 1.62** | **sign flip** |
| | delivery_e2e | +0.32 ± 2.67 | **−1.03 ± 1.13** | **sign flip** |

Exchange rate: the write-up's "about 0.58 pp of vitals per pp of camera given
up" is **0.606** (16.75 / 27.65).

**The conclusion is unchanged and now better supported.** The camera link is
still the entire mechanism, and the other two factors are still null — but null
on a roughly twice-tighter test, which is a much stronger statement than the
original made.

### Why the intervals shrank: the original analysis was not paired

`seed-set = ${repetition}`, so repetition N is the same seed draw in every
cell. The main effect of a factor should therefore be a per-seed block
contrast: that seed's four high-level cells minus its four low-level cells,
with the interval taken over the 30 block differences. The original pooled all
runs instead, which leaves the enormous camera-link split (≈28 pp) inside the
residual variance when estimating the other two factors and roughly doubles
their intervals — OBD on timely camera is ±4.01 pooled against **±1.43**
paired. "Null within CI" was being tested with an interval twice as wide as the
design supports. The nulls survive the sharper test, so this was luck rather
than judgement.

This is the same error as the biased frontier statistic
(`docs/ABLATION_CROSS_STREAM.md`) and the unmatched seed sets in the load
comparison (`docs/CORRIDOR_REGIME.md`): a comparison left unpaired when the
design permits pairing. Third instance in this project.

### One thing worth a second look later

The recomputed processing-time effects are **consistently negative across all
three metrics** (−0.58, −1.38, −1.03), which is physically sensible — slower
edge processing being slightly worse — whereas the published figures were all
positive, implying slower processing *helped*. That coherence is corroborating
evidence that the recomputation is the correct one. All three remain null
within CI, with timely camera closest (−1.38 ± 1.62), so a larger seed count
might resolve a small real penalty. Nothing currently rests on it.

**Lesson applied:** `tools/analyze_deconf.py` now regenerates this table from
source. A result reported without a script that reproduces it is a result
nobody can check, and this one went unchecked for weeks.

## C15. The QC suite had the right rule and it was never read

Found 2026-11-04 while trying to write the manuscript's quality-control
paragraph. The existing draft claims "the full corpus of this paper (7,650
runs) passes all four checks". That sentence could not be written, for two
independent reasons.

### The rule that would have caught C13 fired, on all 15 corridors

R3 -- "no two factor levels may produce bit-identical output, which detects
factors that were configured but never implemented" -- is precisely the rule
for the background-traffic bug. Run on `simulations/corridorpop/results`, the
90-run set where the ini's own `${bgues=2,20}` cross actually lands, it reports:

```
R3 configs 'c08-bgues=20' and 'c08-bgues=2' produced bit-identical results
... one per corridor, 15 in total
```

The instrument was correct, present, and pointed at the right thing. No QC log
exists anywhere in the repo and no document records `qc_check.py` having been
run on the corridor campaigns -- the only recorded invocation is 12 runs in
`docs/TOWER_DATA.md`. **The failure was not the check; it was never reading
it.** C13 was then found three weeks later by a 490-run campaign.

### On the two headline campaigns the checks were silently no-ops

Worse. `config_key()` stripped only OMNeT++'s `-#N` run suffix, but
`tools/corridor_*.sh` name their cells `<corridor>-<arm>-s<NN>.sca`, because
they override every factor on the command line instead of through iteration
variables. So the replication index stayed in the key and every run formed a
config of its own:

```
QC: 490 runs in 490 configs
QC PASSED: no degenerate constants, no impossible delays, ...
```

R1 needs at least three seeds in a config and R3 compares configs against each
other. With one run per config both rules match nothing and the suite returns
**PASSED without testing anything**. A green light from a disabled test is
worse than a red one; this is the same shape of error as C13 itself, where a
parameter bound correctly and did nothing.

Fixed: `config_key()` now strips both suffixes, and the corridor campaigns
group as 490 runs in 49 configs (7 corridors x 7 arms).

### Current QC state of the corpus, honestly

| Result set | runs | verdict |
|---|---|---|
| `corridorA/results_deconf` | 240 | **passes all four** |
| `corridorpop/results_seeds10` | 490 | R1 x8, explained below |
| `corridorpop/results_loaded` | 490 | R1 x9, explained below |
| `corridorpop/results_lowload` | 490 | R1 x8, explained below |
| `corridorpop/results_targets` | 560 | R1 x1, explained below |
| `corridorpop/results` | 90 | **R3 x15 -- the C13 bug** |

Two classes of benign constant were found and are now documented exemptions in
`constant_ok()`, scoped as narrowly as the evidence allows rather than
blanket-suppressed:

1. **`cameraAdmitted` on the static arms** is identically 536 frames in every
   seed -- and identical on c08 and c14, corridors at opposite ends of the
   coverage sample. The camera source is periodic with a fixed frame size and
   admission happens upstream of the radio, so neither the channel RNG nor the
   seed can change the decision. That is the fixed-cap baseline being
   *radio-blind by construction*, which is the effect this paper measures. It
   is a result, not a defect, and it is a compact way to state the thesis.
2. **`finalBucketRateBps` wherever no adaptive policy runs** -- the static caps,
   and all of Family A, whose campaigns predate the controller -- is a
   configured default echoed back.

### The R1 findings that remain are a result

On the adaptive arms the metric is left live, and it fires: the controller's
terminal bucket rate is **bimodal and seed-independent** -- exactly the 1 Mb/s
ceiling on c08/c09/c11 and exactly the 80 kb/s probe floor on c12/c14, in all
10 seeds. The controller saturates at its limits on the easy and the hard
corridors and only operates in between on the middle ones.

`c12-aimd` sits on the floor **only under background load**, which is one of
the cleaner illustrations in the study that the load bites. These are reported
rather than exempted, because they are measurements.

### What the manuscript may now say

Not "the full corpus passes all four checks". The accurate statement is that
R2, R3 and R4 pass on every campaign the paper reports, that R1 fires only on
one metric and only where that metric records a controller saturating at a
configured limit, and that the one genuine R3 failure in the corpus is the
superseded 90-run load cross, retained because it is the evidence for C13.

## Tooling added

- `tools/opencellid_towers.py` — operator filter, route-proximity and
  serving-rank selection, mandatory coverage AUDIT block.
- `tools/export_vectors.sh` — reproducible `.vec` → CSV export (this step was
  previously undocumented and done by hand).
- `tools/run_familyB_v2.sh`, `tools/run_familyB_v2_rest.sh` — the re-run.
- `analysis/aoi_metrics.py` — full-horizon AoI table.
- `figures_src/_shared.py` — `sim_time_limit()`, `aoi_series()`, `aoi_stats()`.

Note on machine limits: the rural per-operator scenarios need ~1.9 GB each, so
on this 15 GB box they run at `-j5`, not `-j20`.

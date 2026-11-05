# Which corridors is the controller actually for?

Added 2026-10-23. Data: `analysis/corridorpop/`,
`simulations/corridorpop/results_thr/`.

## The question

The regime finding says admission control helps when a link is
contention-limited and does almost nothing when it is coverage-limited. Both
earlier case studies turned out to be coverage-limited, so the controller's
real-world population was unknown — and `docs/CORRIDOR_POPULATION.md` then
showed those two corridors are not representative anyway (the "rural" one is
better covered than 73% of US corridors).

This classifies a stratified sample instead of arguing from two routes.

## Method

15 corridors evenly spaced across the national coverage distribution
(`analysis/corridors/stratified.csv`), each a 20 km drive through one
operator's real tower field, 60 KiB video payload. Because the sample is
evenly spaced **in rank**, corridor `cNN` sits at roughly the
`NN/14 × 100`th percentile of the national distribution.

> **Corrected 2026-11-04.** Use the *measured* sample percentiles, not that
> formula: c08 57.0, c09 64.0, c10 71.3, c11 78.3, c12 85.3, c13 92.7, c14
> **97.0** — the formula labels c14 "100th" when it is the 97th of 300. And
> "the national distribution" is not the right population: corridors were
> drawn in proportion to one operator's LTE *cell* density, each passing
> through a cell at its midpoint, so 56% of them have >1,000 sites within
> 50 km. c14 also sits exactly at the sampler's structural ceilings, so the
> simulated sample never reaches the hard end of the distribution. Do not
> describe any corridor here as a national worst case. See
> `docs/CORRIDOR_POPULATION.md`, audit section.

Two tests:

1. **Background load sweep** (2 vs 20 UEs per cell, 3 seeds each, 90 runs).
   *Void — the generators never transmitted; see the withdrawal note below.*
2. **Regime test** (10 degraded corridors, 3 seeds): FIFO against dropPace at
   a 400 kbps cap. The signature of contention is that *throttling camera buys
   vitals*. If throttling gains nothing, the bottleneck is coverage and
   admission control cannot help by construction.

## Background load is immaterial on real corridors

> **WITHDRAWN 2026-11-02. This section is not a finding.** The background
> traffic generators never emitted a packet in any run of this project:
> `startTimeUl` defaults to `-1s` and was never set, so
> `TrafficGeneratorBase.cc:73` never schedules a first transmission. Every
> background-UE statistic in every archive reads `count 0`. The 2-vs-20
> comparison below could not have returned anything but a null, and the
> agreement with Family A's 0.00 pp is two instances of the same configuration
> gap, not independent confirmation. **Do not quote the 0.00 pp figure as
> evidence.** Full diagnosis, including why setting `startTimeUl` alone still
> fails, is in `docs/CORRECTIONS_2026-10.md` C13.
>
> What survives: the corridor-to-corridor spread below is real and large, and
> is produced by site density, distance and handover on measured tower
> geometry. The regime framing stands with contention removed from its
> explanation; the paper's radio carries exactly one active UE, the rig.

Across all 15 corridors, 2 and 20 background UEs per cell gave results
identical to one decimal place on both metrics. The parameter was verified to
take effect (2 versus 20 `bgUE` modules instantiated) — which confirmed the
modules existed, not that they generated anything. This independently
confirms Family A's load effect of exactly 0.00 pp, now on measured geometry
rather than synthetic chains.

## Regime test: throttling camera to 400 kbps

| Corridor | ~pctile | max dist | FIFO vitals/camera | throttled vitals/camera | vitals gain |
|---|---|---|---|---|---|
| c05 | 36th | 2,935 m | 98.4 / 95.8 | 98.7 / 36.1 | +0.4 pp |
| c06 | 43rd | 3,227 m | 98.8 / 94.4 | 97.2 / 35.7 | **−1.6 pp** |
| c07 | 50th | 3,588 m | 96.2 / 92.1 | 96.8 / 35.3 | +0.6 pp |
| c08 | 57th | 3,982 m | 92.7 / 86.7 | 97.5 / 35.3 | +4.8 pp |
| c09 | 64th | 4,696 m | 90.7 / 88.1 | 94.3 / 35.1 | +3.6 pp |
| c10 | 71st | 5,515 m | 77.2 / 70.3 | 83.3 / 27.5 | +6.1 pp |
| c11 | 79th | 6,301 m | 59.8 / 55.0 | 70.8 / 22.9 | **+11.0 pp** |
| c12 | 86th | 7,834 m | 52.8 / 49.5 | 58.7 / 19.6 | +5.9 pp |
| c13 | 93rd | 9,340 m | 66.7 / 62.9 | 70.6 / 24.6 | +3.8 pp |
| c14 | 100th | 10,000 m | 36.4 / 36.7 | 44.0 / 15.8 | +7.5 pp |

For reference, the synthetic congested condition gains **+18.0 pp** this way.

## Reading

**No real corridor is as contention-limited as the synthetic condition.** The
largest gain here is +11.0 pp against +18.0 pp synthetic, and it costs 32 pp
of camera to get it — an exchange rate of 0.34 against 0.58 synthetic.

**But the population splits cleanly, and the split is the point.**

- **Below roughly the 50th percentile** (c05–c07, max distance under ~3.6 km)
  throttling buys nothing — between −1.6 and +0.6 pp of vitals — while
  destroying camera, 95% down to 36%. A static cap applied here is **pure
  loss**.
- **Above roughly the 57th percentile** (c08 onward) throttling gains 3.6 to
  11.0 pp of vitals. There is a real contention component to exploit.

So **about 43% of corridors have exploitable contention and about 57% would be
actively harmed by static throttling.**

## Why this is the argument for an adaptive controller

A single static cap cannot tell these two halves apart. Deploy one everywhere
and it wrecks camera delivery on the better half of corridors to buy nothing;
leave it off and it forfeits up to 11 pp of vitals on the worse half. Choosing
correctly requires recognising, in flight, which regime the vehicle is
currently in — which is precisely what a freshness-triggered controller does
and what no fixed configuration can.

This is a stronger and better-evidenced motivation than the two case studies
provided, and it replaces the coverage-gap argument that turned out to be a
site-selection artifact.

## Limitations

Single operator, straight-line routes through real tower fields, one payload
size, one throttling rate, 3 seeds per point, and 15 corridors — enough to
establish the split, not to put a tight confidence interval on the 43/57
figure. The percentile mapping assumes the stratified sample's rank spacing
transfers to the population, which holds by construction of the sample but
inherits the sampling caveat in `docs/CORRIDOR_POPULATION.md`: anchoring on
real cells under-represents genuinely unserved areas, so the poorly covered
tail is likely larger than measured — and, as the 2026-11-04 audit found, the
two difficulty statistics are *censored* rather than merely under-sampled,
because each corridor is centred on a tower. `max_m` cannot exceed 10 km and
`frac_beyond_horizon` cannot exceed 0.30; c14 sits at both ceilings.

## The controller on those corridors (2026-10-26)

The regime split above established that about 43% of corridors have
exploitable contention. This runs the freshness-triggered controller on
exactly those, closing the gap between "the controller works in synthetic
contention" and "contention exists on 43% of real corridors" — two claims that
until now were never joined.

21 runs: AIMD (1000 kbps ceiling, adapting below it) on c08–c14, 3 seeds,
compared against the same corridors under FIFO and under a static 400 kbps
cap.

### Against the static cap

| Corridor | max dist | FIFO | static 400k | AIMD | AIMD − static |
|---|---|---|---|---|---|
| c08 | 3,982 m | 92.7 / 86.7 | 97.5 / 35.3 | 96.8 / 73.7 | −0.7 / **+38.5** |
| c09 | 4,696 m | 90.7 / 88.1 | 94.3 / 35.1 | 93.8 / 83.1 | −0.6 / **+48.0** |
| c10 | 5,515 m | 77.2 / 70.3 | 83.3 / 27.5 | 81.4 / 55.9 | −1.9 / **+28.5** |
| c11 | 6,301 m | 59.8 / 55.0 | 70.8 / 22.9 | 82.3 / 57.6 | **+11.5** / **+34.7** |
| c12 | 7,834 m | 52.8 / 49.5 | 58.7 / 19.6 | 66.9 / 47.4 | **+8.2** / **+27.8** |
| c13 | 9,340 m | 66.7 / 62.9 | 70.6 / 24.6 | 75.5 / 65.6 | **+4.9** / **+41.1** |
| c14 | 10,000 m | 36.4 / 36.7 | 44.0 / 15.8 | 54.9 / 40.0 | **+11.0** / **+24.2** |

*(timely vitals % / timely camera %, 3 seeds)*

**AIMD beats the static cap on every contention-limited corridor**, by +24 to
+48 pp of camera. On the four sparsest it also gains +4.9 to +11.5 pp of
vitals — better on both axes at once. The static cap's problem is that one
rate cannot suit corridors spanning 4 km to 10 km of site spacing; it
over-throttles everywhere it is not exactly right, and it is exactly right
nowhere.

The margin is **larger** on real corridors than the synthetic exchange-rate
analysis predicted. That analysis compared against a cap tuned for the
synthetic condition; here the fixed 400 kbps is badly mismatched to most
corridors, and adapting per-corridor recovers more than tuning for one.

### Against doing nothing

| Corridor | AIMD − FIFO | dominates both axes |
|---|---|---|
| c08 | +4.1 / −13.0 | |
| c09 | +3.1 / −5.0 | |
| c10 | +4.1 / −14.3 | |
| c11 | **+22.4 / +2.6** | yes |
| c12 | +14.1 / −2.0 | |
| c13 | **+8.8 / +2.8** | yes |
| c14 | **+18.5 / +3.3** | yes |

Against FIFO the picture is honest rather than uniform. On the three sparsest
corridors (79th percentile and above) **AIMD dominates doing nothing on both
axes** — more timely vitals *and* more timely camera, because FIFO floods a
weak link and loses both to queueing. On the better-covered four it trades,
buying 3–4 pp of vitals for 5–14 pp of camera.

So the controller's clearest case is the poorly served tail: roughly the worst
20% of corridors, where it is strictly better than both alternatives. Over the
middle of the contention range it offers a trade rather than a free win, and
that should be reported as such.

## Audit: against an ORACLE static baseline (2026-10-29)

**The "+24 to +48 pp" above compares against a single static rate — 400 kbps —
on seven corridors spanning 4 to 10 km of site spacing.** The section above
itself says one rate "over-throttles everywhere it is not exactly right, and it
is exactly right nowhere", which concedes the baseline was handicapped. That is
the first thing a reviewer attacks, so the comparison was redone against the
strongest static policy the data permits.

105 runs: caps 200/400/600/800/1000 kbps × c08–c14 × 3 seeds
(`simulations/corridorpop/results_static/`, `tools/corridor_static_sweep.sh`,
`tools/analyze_static_oracle.py`). The static arm is then allowed its **best
cap per corridor, chosen on the same seeds used to evaluate** — an oracle no
deployment could implement, since it requires knowing each corridor's best rate
in advance, which is precisely what the controller discovers in flight.

The static frontier, timely vitals / timely camera:

| Corridor | 200k | 400k | 600k | 800k | 1000k | aimd |
|---|---|---|---|---|---|---|
| c08 | 95.9/17.0 | 97.5/35.3 | 98.0/56.9 | 94.6/71.0 | 92.7/86.7 | 96.8/73.7 |
| c09 | 95.1/17.3 | 94.3/35.1 | 93.1/50.7 | 92.1/70.2 | 90.7/88.1 | 93.8/83.1 |
| c10 | 83.5/12.8 | 83.3/27.5 | 80.4/40.4 | 81.4/59.5 | 77.2/70.3 | 81.4/55.9 |
| c11 | 84.1/13.0 | 70.8/22.9 | 66.1/35.6 | 59.6/43.1 | 59.8/55.0 | 82.3/57.6 |
| c12 | 72.6/10.7 | 58.7/19.6 | 54.0/30.9 | 53.3/41.2 | 52.8/49.5 | 66.9/47.4 |
| c13 | 77.1/12.0 | 70.6/24.6 | 72.9/41.3 | 66.7/51.4 | 66.7/62.9 | 75.5/65.6 |
| c14 | 52.2/8.3 | 44.0/15.8 | 38.5/22.6 | 36.7/29.7 | 36.4/36.7 | 54.9/40.0 |

Extra camera the controller delivers at **exactly its own vitals level**,
interpolated along each corridor's static Pareto frontier (fairer than snapping
up to the next qualifying cap, which credits the controller too much):

| Corridor | frontier camera at aimd's vitals | Δ camera |
|---|---|---|
| c08 | 61.9 | +11.8 |
| c09 | 42.1 | +41.0 |
| c10 | 59.6 | **−3.6** |
| c11 | 14.4 | +43.2 |
| c12 | 14.4 | +33.1 |
| c13 | 23.0 | +42.6 |
| c14 | *no static point reaches 54.9% vitals* | — |

**Mean +28.0 ± 22.1 pp over the six measurable corridors.**

### What the audit changes

**The headline survives, restated.** The defensible claim is *+28.0 ± 22.1 pp
of timely camera at matched vitals against a per-corridor oracle static
policy*, not "+24 to +48 pp against a static cap". The old figure is not
comparable and should not be quoted.

**The mechanism is now correctly identified.** The oracle can tune per corridor
but not *within* a corridor. That it still loses by this much means the
controller's advantage comes from varying the rate **during the drive**, not
from being better matched to the corridor — which is a sharper and more
defensible mechanism claim than the original comparison could support.

**c14 is the strongest single result.** The controller reaches 54.9% timely
vitals where the best of any fixed rate is 52.2%, *and* 40.0% camera against a
best of 36.7% — it dominates every static point on both axes at once. No fixed
configuration reaches its operating region at all.

**c10 is a genuine counterexample and must be reported.** A fixed 800 kbps
matches the controller's vitals and beats its camera by 3.6 pp. At 3 seeds this
is within noise, but the honest statement is that the controller does not help
on every contention-limited corridor.

### Limitations of the audit

3 seeds per point, so per-corridor rows are indicative and the pooled interval
is wide (±22.1 pp on a +28.0 mean). Five cap values, so the interpolated
frontier is coarse. One payload profile, one operator, straight-line routes.
The oracle is favourable to the static arm by construction, which is the point,
but it also means the comparison says nothing about what a *deployable* fixed
configuration would achieve — that is the 400 kbps column, and it is much
worse.

**The seed-count limitation was addressed on 2026-10-30; see below. One
conclusion above — the c10 counterexample — did not survive it.**

## Audit at 10 seeds (2026-10-30)

The ±22.1 pp interval above was wide enough that a reviewer could fairly ask
whether the headline clears zero at all. Every cell of the comparison was
re-run at 10 seeds: 490 validated runs, 7 corridors × (5 caps + aimd +
aimdSelf) × 10 seeds, in `simulations/corridorpop/results_seeds10/` via
`tools/corridor_seeds10.sh`, analysed by the same
`tools/analyze_static_oracle.py`.

The ini ties `seed-set` to `${repetition}` with `repeat = 3`, so runs 3–5 *are*
the three seeds and raising `repeat` would renumber the whole archive. The
runner instead holds `-r 3` and overrides `--seed-set` per run. This was
verified, not assumed: `-r 3 --seed-set=0` reproduced
`results_ctl/c08-aimd-3.sca` with every scalar bit-identical. The same check
incidentally confirms that the `dropsStaleCamera()` fix (7e83ef24c) left the
`aimd` arm unchanged, which had been asserted but never tested.

The static frontier at 10 seeds, timely vitals / timely camera:

| Corridor | 200k | 400k | 600k | 800k | 1000k | aimd |
|---|---|---|---|---|---|---|
| c08 | 95.6/16.9 | 97.5/35.0 | 97.0/55.7 | 95.1/72.5 | 93.3/88.6 | 96.8/78.3 |
| c09 | 94.2/17.0 | 94.6/34.4 | 93.6/52.4 | 91.0/70.0 | 89.6/86.3 | 94.1/81.7 |
| c10 | 83.2/12.9 | 83.6/27.4 | 81.6/41.0 | 80.9/56.9 | 78.5/70.7 | 82.3/56.0 |
| c11 | 80.3/12.5 | 70.1/23.6 | 65.8/35.5 | 63.8/46.4 | 61.9/56.4 | 80.2/59.9 |
| c12 | 69.1/10.1 | 58.6/19.2 | 54.6/29.4 | 53.0/39.5 | 51.2/46.8 | 67.0/46.1 |
| c13 | 76.0/12.7 | 74.5/25.8 | 72.1/40.6 | 69.3/52.6 | 68.3/64.0 | 75.6/64.2 |
| c14 | 50.7/8.1 | 42.0/15.0 | 39.2/22.2 | 36.5/28.6 | 33.7/33.3 | 53.0/37.8 |

### The headline tightened and went up

Interpolated along each corridor's static Pareto frontier, at exactly the
controller's own vitals:

| Corridor | frontier camera | Δ camera (3 seeds) | Δ camera (10 seeds) |
|---|---|---|---|
| c08 | 56.9 | +11.8 | +21.4 |
| c09 | 43.9 | +41.0 | +37.8 |
| c10 | 36.4 | **−3.6** | **+19.7** |
| c11 | 12.7 | +43.2 | +47.1 |
| c12 | 11.9 | +33.1 | +34.2 |
| c13 | 15.8 | +42.6 | +48.4 |
| c14 | *unreachable* | — | — |

**Mean +34.8 ± 13.9 pp over the six measurable corridors**, against
+28.0 ± 22.1 at 3 seeds. The interval narrowed by a third and the point
estimate rose by ~7 pp. This is the number to quote.

### Two conclusions above are now wrong

**c10 is NOT a counterexample.** At 3 seeds a fixed 800 kbps appeared to match
the controller's vitals and beat its camera by 3.6 pp, and that was recorded as
a genuine negative result. At 10 seeds c10 gives **+19.7 pp** and TEST 1 finds
**no corridor dominated by any fixed rate** — the controller is on the Pareto
frontier on all seven. The counterexample was a 3-seed artifact, and the
earlier section's claim that "the controller does not help on every
contention-limited corridor" is not supported by this data.

**c14 is no longer uniquely strongest.** It is still the case that no fixed
rate reaches c14's vitals, but that is now true of the whole frontier rather
than a property distinguishing c14 from corridors that were merely beaten.

### The stronger oracle: per-seed frontier selection

The interval above is *across corridors* — it describes spread between
corridors, not sampling error within one. The 10-seed data supports a better
test, which the 3-seed data could not: rebuild the static frontier **inside
each seed** and pair it against that seed's own controller run.

This is deliberately a *stronger* oracle than the one above. Choosing a cap
within a seed lets the static arm bank seed-level noise in its own favour — it
picks the cap with knowledge of the very run it is scored on.

| Corridor | Δ camera, per-seed paired | seeds where no fixed rate reaches aimd |
|---|---|---|
| c08 | **+0.2 ± 9.2** | 3/10 |
| c09 | +29.7 ± 10.5 | 1/10 |
| c10 | +6.9 ± 12.8 | 1/10 |
| c11 | +44.3 ± 5.2 | 5/10 |
| c12 | +25.7 ± 6.4 | 5/10 |
| c13 | +31.8 ± 16.0 | 3/10 |
| c14 | +29.3 ± 6.2 | 6/10 |

**Mean of per-corridor means +24.0 ± 16.0 pp** (pooled over the 46 scored
pairs: +22.2 ± 5.3 pp).

Two things must be said about this number rather than left implicit:

1. **It is a conservative floor, not a point estimate.** 24 of 70
   seed-corridor pairs are excluded because *no fixed rate reaches the
   controller's vitals in that seed at all* — cells where the controller wins
   outright. Excluding them is the right call (the delta is undefined, and
   scoring them as large positives would let the best cells inflate the mean)
   but it biases the result **against** the controller, and the exclusion is
   large enough to matter.
2. **c08 is now the weak corridor, and this is the real caveat.** +0.2 ± 9.2 pp
   is indistinguishable from zero. Under per-seed oracle selection the
   controller buys essentially nothing on c08. c08 is the *least* contended of
   the seven (57th percentile), which is consistent with the regime finding
   above — but it means the honest version of "the controller does not help
   everywhere" survives, just relocated from c10 to c08.

### Limitations that remain

Five cap values, so the interpolated frontier is still coarse; a finer grid
would weaken the static arm less than it would strengthen it. One payload
profile, one operator, straight-line routes, one background-load level
(`bgues=20`). The oracle remains favourable to the static arm by construction,
so none of this speaks to what a *deployable* fixed configuration achieves —
that is the 400 kbps column, and it is far worse than either oracle.

The two oracle variants bracket the answer: **+34.8 ± 13.9 pp** against a
per-corridor oracle, **+24.0 ± 16.0 pp** against a per-corridor-per-seed
oracle that also discards the controller's best cells. Both clear zero; the
paper should quote the first and cite the second as the adversarial bound.

## Under real background load (2026-11-04)

The limitation listed above — "one background-load level (`bgues=20`)" — turned
out to be worse than stated: there was no background load at *any* level, in
any run of this project. See `docs/CORRECTIONS_2026-10.md` C13. Everything
above this section describes **one active UE in an otherwise idle cell**.

With the generator fixed (`startTimeUl`, generator typename and per-eNodeB
`bgUE` placement, all three of which were missing), the headline cells were
re-run under ~2.5 Mbps/cell of competing uplink: 490 runs, validated 490/490,
zero failures, and verified loaded — every one of the 490 files carries
`bgues=20` with nonzero background activity, against `count 0` everywhere
before. 64 of the 75 analysis output lines differ from the unloaded campaign,
which is the check that the earlier campaign failed.

Run `tools/analyze_load_effect.py` to reproduce.

### The load is real and it bites

| Corridor | ~pctile | unloaded v/c | loaded v/c | Δ vitals | Δ camera |
|---|---|---|---|---|---|
| c08 | 57th | 96.8/78.3 | 93.6/73.5 | −3.2 | −4.8 |
| c09 | 64th | 94.1/81.7 | 90.8/80.4 | −3.3 | −1.3 |
| c10 | 71st | 82.3/56.0 | 77.4/45.0 | −4.9 | −11.1 |
| c11 | 79th | 80.2/59.9 | 65.3/47.3 | −14.9 | −12.5 |
| c12 | 86th | 67.0/46.1 | 55.7/39.8 | −11.4 | −6.4 |
| c13 | 93rd | 75.6/64.2 | 70.9/57.9 | −4.7 | −6.3 |
| c14 | 100th | 53.0/37.8 | 41.7/31.7 | −11.3 | −6.1 |

Absolute timeliness falls on every corridor and both streams.

### The headline survives

Against the per-seed oracle, over the six corridors scorable under both loads:
**+23.1 ± 18.7 pp unloaded against +22.4 ± 11.2 pp loaded.**

The defensible statistic is the matched-seed paired difference — each corridor
restricted to the seeds scorable under *both* loads, differenced within the
seed, so the controller and the oracle are compared on the same draws:

| Corridor | unloaded | loaded | change | n |
|---|---|---|---|---|
| c08 | +1.3 ± 10.2 | +23.6 ± 27.2 | +22.3 ± 35.0 | 6 |
| c09 | +31.8 ± 10.6 | +28.8 ± 21.1 | −3.0 ± 27.7 | 8 |
| c10 | +4.9 ± 12.8 | +2.2 ± 22.3 | −2.7 ± 19.6 | 7 |
| c11 | +44.3 ± 7.7 | +22.5 ± 13.1 | **−21.7 ± 14.0** | 4 |
| c12 | +24.8 ± 8.7 | +23.3 ± 10.1 | −1.5 ± 14.9 | 4 |
| c13 | +34.1 ± 16.6 | +27.6 ± 12.9 | −6.5 ± 26.9 | 4 |
| c14 | — | — | only 1 matched seed | — |

**Overall: −2.2 ± 16.0 pp. The interval spans zero.** So the headline is *not*
an artifact of an idle cell — it holds at ~+22 pp under both conditions — but
no load-dependence *direction* can be claimed from these data. Only c11 is
individually significant, and it narrows (−21.7 ± 14.0).

### Two things not to claim

1. **"The c08 caveat dissolves under load."** Unmatched, c08 appears to go from
   +0.2 ± 9.2 to +32.8 ± 18.0, a +32.6 pp swing, and the mechanism story writes
   itself: c08 is the best-covered corridor, so with nothing to contend against
   there is nothing to adapt to. But which seeds are *scorable* differs by load
   (3 unreachable unloaded, 1 loaded), so that compares 7 seeds against 9.
   Matched to the 6 common seeds the change is **+22.3 ± 35.0 pp — not
   significant.** The caveat is neither confirmed nor dissolved; c08 remains the
   corridor where the oracle is hardest to beat, and the loaded data does not
   settle it.
2. **Anything quantitative about c14 under load.** Nine of its ten seeds have
   the controller's vitals above *every* static operating point, so the oracle
   has no value to compare against and the corridor drops out. That is
   arguably the strongest possible outcome — no static cap reaches where the
   controller operates — but this test cannot quantify it, and `+20.9` from a
   single seed is not a measurement.

### Where this leaves the regime story

The spread across corridors is real and large under both loads, and it is
produced by site density, distance and handover rather than by competing
traffic — the original "contention-limited vs coverage-limited" framing was
built on a load axis that did not exist. What the loaded data adds is that
introducing genuine contention degrades every corridor's absolute timeliness
without reordering which corridors the controller helps on. So the regime
should be described in terms of **coverage geometry**, with background load as
a factor that lowers the whole curve and leaves the adaptive margin
essentially where it was.

### Pre-registration, honestly scored

The expectation recorded in `tools/corridor_loaded.sh` before the run was that
the margin would "narrow but survive". Survive, yes. Narrow — not established:
the point estimate is −2.2 pp and the interval is ±16.0. Half the prediction
was right and the half that would have been the interesting result is not
supported.

Worth recording that the matched-seed check was the sixth instrument or
statistics problem caught in this project in two weeks, and the fifth that
changed a conclusion already being drafted. The unmatched c08 number was
written into a draft paragraph before the seed sets were checked.

# Which freshness signal should drive the controller?

Rewritten 2026-10-28. **An earlier version of this document, and commits
91814720a and 6e4bd86d6, reported the opposite conclusion on the strength of a
bug in this project's own code. See "Correction" below before reading further.**

Data: `simulations/pilot/results_ablation/` (80 runs),
`simulations/pilot/results_ablation_sweep/` (42 runs),
`simulations/corridorpop/results_ctl/` (42 runs). Analysis:
`tools/analyze_ablation.py`, `tools/analyze_ablation_sweep.py`,
`tools/analyze_corridor_ablation.py`.

## The question

The controller throttles camera on the age of the newest *vitals* sample the
server has confirmed — a stream it does not throttle. `docs/RELATED_WORK.md`
establishes this is what distinguishes it from the nearest prior work, A³L-FEC
(arXiv:2410.05852), which drives sender rate from the receiver-measured age
violation of the stream *being* adapted.

So the question a reviewer will ask: why not measure the throttled stream's own
freshness? `aimdSelf` answers it — `aimd` with `freshestCamera` substituted for
`freshestVitals`, nothing else changed.

## Correction

The first run of this experiment reported that the self-signal arm collapses:
0.3% timely camera against 77.0%, 6725 backoffs against 18 probes, the rate
pinned on the probe floor. That result was an artifact.

`drainClosedLoop()` gated its stale-camera-frame discard on an inline
`(policy == POLICY_CTRL || policy == POLICY_AIMD)` test, and `POLICY_AIMD_SELF`
was never added to it. So `aimdSelf` differed from `aimd` in **two** ways, not
one: it also retained camera frames that had gone stale in the pending queue.
The tell was visible and overlooked — `cameraStaleDropped` was 317.2 for `aimd`
and exactly 0.0 for `aimdSelf`.

Fixed by replacing the inline test with a named `dropsStaleCamera()` predicate,
so a future policy cannot diverge the same way silently. All `aimdSelf` runs
were discarded and re-run; the `aimd` arm was unaffected.

**The corrected result reverses the conclusion.** It is reported below, and the
artifact is retained as a deliberate design variant, because it turns out to be
the most informative arm of the three.

## Corrected result: the two signals are comparable

Paired per-seed differences, `aimdSelf − aimd` (pp), 10 held-out seeds.
Workload drift verified at 0 generated packets across all conditions.

| Condition | Δ timely vitals | Δ timely camera |
|---|---|---|
| Healthy | 0.00 ± 0.00 | 0.00 ± 0.00 |
| Congested | **+1.43 ± 0.88** | −4.37 ± 4.70 (ns) |
| Transient | **+5.46 ± 2.42** | −3.95 ± 6.83 (ns) |
| Outage | +5.12 ± 4.94 | −0.63 ± 1.11 |

Operating points, timely vitals / camera:

| Condition | aimd | aimdSelf | backoff:probe (aimd → self) |
|---|---|---|---|
| Healthy | 99.1 / 97.0 | 99.1 / 97.0 | 8:1586 → 0:1595 |
| Congested | 93.7 / 77.0 | 95.1 / 72.6 | 916:5837 → 1411:5322 |
| Transient | 89.2 / 67.4 | 94.7 / 63.4 | 1457:5160 → 2021:4617 |
| Outage | 65.2 / 44.7 | 70.3 / 44.0 | 1295:1683 → 1438:1554 |

On the measured contention-limited corridors c08–c14, pooled over 21 run pairs:
**Δ timely vitals +2.88 ± 1.62 pp, Δ timely camera −5.32 ± 3.26 pp.**

**Reading.** The self-signal arm does not collapse. It backs off somewhat more,
runs a slightly lower rate, and therefore sits at a more conservative point on
the same frontier: a little more vitals, a little less camera. The vitals gains
are significant, the synthetic camera losses are not, and on real corridors
both are small. **Neither signal dominates, and the cross-stream signal is not
necessary.**

Healthy remains an exact null: neither arm has cause to throttle, so the signal
source is irrelevant.

## At 10 seeds on real corridors (2026-10-30)

The corridor arm above was 3 seeds. It was re-run at 10 as part of the headline
seed campaign (`simulations/corridorpop/results_seeds10/`,
`tools/corridor_seeds10.sh`), which gives per-corridor intervals rather than
only a pooled row. `aimdSelf` paired against `aimd`, same seed, same geometry:

| Corridor | Δ timely vitals | Δ timely camera | self backoff:probe |
|---|---|---|---|
| c08 | −1.5 ± 1.6 | **−12.3 ± 7.4** | 407:2571 |
| c09 | +0.3 ± 0.8 | **−7.0 ± 3.6** | 845:3349 |
| c10 | **+2.0 ± 1.8** | **−19.5 ± 6.3** | 2629:1585 |
| c11 | **+4.8 ± 1.5** | **−6.0 ± 2.8** | 2298:4068 |
| c12 | **+7.4 ± 1.6** | **−3.1 ± 2.6** | 2948:3132 |
| c13 | **+1.8 ± 1.1** | −0.9 ± 4.4 | 1440:4580 |
| c14 | **+5.3 ± 2.3** | **−1.7 ± 0.7** | 2805:2553 |

Pooled over 70 run pairs: **Δ timely vitals +2.86 ± 0.85 pp, Δ timely camera
−7.21 ± 2.03 pp.**

**One statement above has to be withdrawn.** "On real corridors both are small"
was a 3-seed reading. At 10 seeds the camera loss is significant on six of
seven corridors and is not small — −19.5 pp on c10, −12.3 pp on c08. The vitals
gain is confirmed at essentially the same magnitude (+2.86 vs +2.88) but is now
tightly bounded.

**What this does and does not establish.** It does *not* establish that the
cross-stream signal is better, and the paper must still not claim that. The two
arms sit at different points on a shared frontier — `aimdSelf` throttles harder
(its backoff:probe ratio is worse on every corridor) and therefore buys vitals
with camera. Trading 2.9 pp of vitals for 7.2 pp of camera is not a dominance
result; it is a different operating point.

Establishing dominance needs the same treatment the static baseline got in
`docs/CORRIDOR_REGIME.md`: retune `aimdSelf`'s `freshnessTarget` until its
**vitals matches `aimd`'s**, then compare camera. Only if the cross-stream arm
still delivers more camera at genuinely matched vitals is the signal choice
itself worth anything. **That experiment was run on 2026-10-30; see below.**

What the tighter data *does* add is that the choice is not neutral: it moves
the operating point by a resolvable and non-trivial amount in a consistent
direction across all seven corridors, which is worth reporting as a design
consequence even without a dominance claim.

## What actually matters: discarding stale frames

The retained artifact is a legitimate third design — an own-stream signal whose
queue keeps stale frames — and it is the one that fails:

| Design | backoff:probe | timely camera (Congested) |
|---|---|---|
| own-stream, stale frames **retained** | 6725 : 18 | **0.3%** |
| own-stream, stale frames discarded | 1411 : 5322 | 72.6% |
| cross-stream | 916 : 5837 | 77.0% |

The mechanism is head-of-line blocking in the gate's pending queue. With stale
frames retained, the queue stays at capacity, fresh arrivals are dropped at the
gate, and the only frames ever admitted are old ones — so the newest camera
sample the server holds is permanently ancient. The signal saturates above any
usable target and can never report "safe", so the controller backs off forever
and the rate sits on the probe floor. Discard the stale frames and the signal
tracks recent admissions instead of the backlog.

So the design rule is not "watch a different stream". It is: **a freshness
signal is only usable if the queue feeding it discards stale work; otherwise
the signal measures the backlog rather than the link, and the controller
deadlocks.** An own-stream signal is especially exposed to this because its
queue is the one being throttled, but the failure is about the queue discipline,
not about which stream is watched.

This narrows the project's standing mechanism result rather than extending it.
"Available capacity cannot be inferred from a signal the policy's own
throttling determines" holds for the throughput estimator, which *is* directly
the consequence of the admitted rate. It does **not** hold for the throttled
stream's own age, provided stale work is discarded — that signal remains
informative because admitted frames stay recent regardless of the rate.

## Target sensitivity

Freshness target swept 1–20 s for `aimdSelf` on dev seeds 100–102, against
`aimd` at the identical baseline on the same seeds (`results_sens_aimd`).
Timely vitals / camera:

| target | aimdSelf, Congested | aimdSelf, Transient |
|---|---|---|
| 1 s | 91.6 / 6.1 | 91.8 / 18.9 |
| 2 s | 92.3 / 6.0 | 91.8 / 29.0 |
| 3 s | 92.9 / 36.1 | 92.2 / 50.6 |
| 5 s | 95.6 / 71.8 | 94.3 / 59.9 |
| 7 s | 95.5 / 66.7 | 90.6 / 62.0 |
| 10 s | 87.5 / 76.8 | 81.3 / 63.9 |
| 20 s | 78.5 / 70.9 | 71.1 / 65.7 |

Intervals are wide throughout at 3 seeds (camera reaches ±34 pp at one point),
so these rows are indicative, not precise.

`aimd` over its own swept range (3/5/7 s) gives 95.7/67.1, 94.5/72.7, 89.5/74.4
in Congested and 93.0/60.6, 90.9/70.9, 80.6/64.9 in Transient.

Both controllers are sensitive to the target, in opposite directions:
`aimdSelf` degrades below 3 s (the signal is tight enough that throttling is
near-constant), `aimd` loses vitals above 7 s. Three dev seeds with these
interval widths cannot support a claim that either is more robust, and no such
claim should be made.

## What this means for the contribution

The cross-stream signal is novel — nothing in the surveyed literature throttles
one stream on another's receiver-confirmed freshness — but it is **not
better**, and the paper must not claim it is. The defensible statements are:

1. Adaptive admission control substantially beats tuned static caps
   (`analysis/EFFECTS_SUMMARY.md`, `docs/CORRIDOR_REGIME.md`). This result is
   untouched by anything here and does not depend on the signal source.
2. Either freshness signal works, at slightly different operating points. The
   own-stream variant is the natural baseline from prior art, and reporting it
   as comparable is more credible than omitting it.
3. The queue discipline feeding the signal is load-bearing in a way the signal
   source is not.

## Limitations

Four synthetic conditions and seven corridors, one payload profile, one
operator. 10 held-out seeds per synthetic cell, 3 per corridor, 3 per swept
setting — the per-corridor and per-target rows are indicative only. The
stale-retained arm is a single configuration measured on the synthetic
conditions, not swept.

## The frontier comparison: the signal choice buys nothing (2026-10-30)

560 validated runs, `freshnessTarget` ∈ {2,3,7,10} s × both arms × c08–c14 ×
10 seeds (`simulations/corridorpop/results_targets/`,
`tools/corridor_target_sweep.sh`), plus the 5 s column from `results_seeds10/`
— five frontier points per arm per corridor. Analysis
`tools/analyze_target_frontier.py`.

### The robust result

Maximum achievable timely camera, each arm tuned to its own best target. This
statistic needs no interpolation and no overlap between the arms, so it is the
one to quote:

| Corridor | cross best cam | self best cam | Δ |
|---|---|---|---|
| c08 | 87.0 | 86.0 | +1.0 |
| c09 | 84.9 | 83.4 | +1.5 |
| c10 | 64.5 | 63.1 | +1.4 |
| c11 | 59.9 | 59.3 | +0.5 |
| c12 | 48.0 | 46.6 | +1.4 |
| c13 | 65.1 | 66.5 | **−1.4** |
| c14 | 37.8 | 37.6 | +0.2 |

**+0.7 ± 1.1 pp — indistinguishable from zero, and the sign reverses on c13.**

**The cross-stream signal confers no camera advantage once both arms are
allowed their own tuning.** The −7.21 pp camera gap reported at a shared 5 s
target was a tuning artifact, exactly as suspected. The question is now closed
in the direction the project did not want.

### What the signal choice actually changes

Not efficiency, but *reachable range*:

| Corridor | cross vitals range | self vitals range | overlap |
|---|---|---|---|
| c08 | 94.8–97.0 | 95.3–96.4 | 1.1 |
| c09 | 92.1–94.6 | 93.0–94.8 | 1.6 |
| c10 | 81.2–84.1 | 82.9–84.3 | 1.2 |
| c11 | 80.2–85.3 | 76.4–85.0 | 4.8 |
| c12 | 62.0–74.8 | 73.9–74.4 | 0.5 |
| c13 | 71.9–77.8 | 75.9–77.4 | 1.4 |
| c14 | 53.0–56.4 | 56.3–58.3 | 0.0 |

The own-stream arm sits in a **narrower, higher-vitals** band; the cross-stream
arm spans a **wider** range reaching lower vitals. On c12 the contrast is
extreme: cross is tunable across 12.8 pp of vitals, self across 0.5 pp. On c14
the two ranges do not overlap at all — the own-stream arm cannot be tuned down
to any vitals level the cross-stream arm can reach.

So the design consequence is about *where* on the trade-off curve a deployment
can be placed, not how much it gets there. A system needing a specific vitals
target may be unable to reach it with one of the two signals.

### Within the overlap, and why it is not the headline

Envelope-to-envelope on a 21-point vitals grid across each overlap: mean
**−7.7 ± 6.9 pp**, i.e. favouring the *own-stream* arm. Per-seed paired, which
is the version with honest intervals: **−1.2 ± 6.4 pp**, indistinguishable from
zero, with the sign reversing seed-to-seed on 4–7 of 10 seeds per corridor.

Neither is quoted as the result, for a stated reason: the overlaps are 0.0–4.8
pp wide, and they sit at the *edge* of the cross-stream arm's range, where it
is tuned to an extreme and its camera has collapsed. A comparison over a 0.5 pp
slice of one arm's worst region is not a statement about either arm's quality.
The best-achievable-camera figure above avoids all of this.

### A methodological correction worth recording

The first version of this analysis scored each arm's **raw** operating points
against the other arm's **Pareto envelope**, in both directions. That is biased
toward whichever arm supplies the envelope: the scored arm is charged for its
own badly-tuned configurations — both arms collapse to ~5% camera at a 2 s
target — while the reference arm is always credited with its best envelope.

Run symmetrically it made **both** directions positive on all seven corridors
(+12.7 and +5.6 pp), which looks precisely like genuinely crossing frontiers.
The interpretation rule had been fixed in advance, and it said both-positive
means the frontiers cross and no dominance claim is available — so the
pre-registered rule would have licensed a confident, wrong conclusion drawn
from a biased statistic. Pre-registering an interpretation does not protect
against the statistic itself being wrong.

Corrected to compare envelope with envelope, the sign **reversed**. The lesson
is the one this project keeps relearning: a result that falls out cleanly
deserves a check of the instrument before it is believed.

## Standing conclusion

1. **The cross-stream signal is novel and confers no measurable advantage.**
   +0.7 ± 1.1 pp of best achievable camera, sign reversing across corridors.
   The paper must not claim the signal as a contribution.
2. **The queue discipline is what is load-bearing** — a freshness signal is
   usable only if the queue feeding it discards stale work. That result stands
   untouched and is the mechanism finding.
3. **The signal choice determines reachable operating range**, which is a real
   design consequence and worth a paragraph, not a contribution claim.
4. `aimdSelf` is the natural A³L-FEC baseline and should be reported as a
   comparable alternative, which is more credible than a dominance claim the
   data refuses.

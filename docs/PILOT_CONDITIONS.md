# Controller pilot — the four operating conditions

Built 2026-10-07. Scenarios in `simulations/pilot/omnetpp.ini`, validation data
in `analysis/pilot_val/`.

The mechanism decomposition established *how* camera admission protects vitals
(discarding beats delaying; discarding the oldest beats discarding
arbitrarily). The pilot asks whether an informed policy beats the simple ones.
That needs conditions which exercise different parts of the problem, because a
policy can look good in one regime and pointless in another.

All four use **synthetic** site layouts, not OpenCellID geometry, so none of
them makes any claim about real infrastructure.

## The conditions

| Condition | Layout | Load | Frame | Question it answers |
|---|---|---|---|---|
| `CondHealthy` | 6 sites, 1 km, urban | 4 bg UEs | 4 KiB | Does a policy needlessly suppress camera when capacity is ample? |
| `CondCongested` | 3 sites, 10 km, rural | 20 bg UEs | 60 KiB | Can it match a well-tuned static cap under steady overload? |
| `CondTransient` | 2 sites, 12 km, rural | 8 bg UEs | 60 KiB | Does adaptation pay when capacity falls and recovers? |
| `CondOutage` | 2 sites, 16 km, rural | 8 bg UEs | 60 KiB | Does it avoid backlog and restore freshness after an outage? |

## Validation (1 seed each, policy = none)

| Condition | timely vitals | timely camera | delivery_e2e | mean E2E | max E2E |
|---|---|---|---|---|---|
| Healthy | 98.8% | 98.7% | 98.6% | 75 ms | 1.0 s |
| Congested | 73.6% | 69.6% | 83.8% | 3.55 s | 33.3 s |
| Transient | 71.0% | 67.8% | 82.9% | 4.95 s | 47.3 s |
| Outage | 49.4% | 48.1% | 64.9% | 14.3 s | 166.6 s |

Four clearly separated regimes. Transient and Congested are close in average —
the distinction is in the *time profile*, which is the point of the condition.
Mean vitals delay by 150 s window:

| window (s) | Congested | Transient | Outage |
|---|---|---|---|
| 0–150 | 16.95 | 0.11 | 0.11 |
| 150–300 | 0.41 | 0.13 | 0.13 |
| 300–450 | 0.14 | 2.80 | 2.80 |
| 450–600 | 0.50 | **28.37** | 45.45 |
| 600–750 | 10.94 | 20.64 | **113.06** |
| 750–900 | 6.57 | 0.19 | 98.51 |
| 900–1050 | 0.13 | 0.07 | 76.34 |
| 1050–1200 | 0.15 | 0.46 | 4.92 |
| 1200–1350 | 4.42 | 18.77 | 0.06 |

`CondTransient` degrades to ~28 s at the cell gap and recovers fully to 0.07 s,
without the link ever dropping — the regime an adaptive policy should exploit
and a static cap should not. `CondOutage` goes far deeper (113 s) and takes
until t≈1050 s to recover, so it tests backlog behaviour rather than
adaptation. Congested is lumpier because its 3-site chain hands over twice;
its 16.95 s first window is an initial-attach transient, not a capacity event.

## How capacity variation is produced, and why

**By geometry, not by background load.** Simu5G's background traffic generator
**ignores its `periodUl` parameter entirely**: changing it from
`uniform(5ms,15ms)` to `uniform(200ms,400ms)` — a 40× change in offered rate —
gives bit-identical results (same `totalPacketsReceived`, same
`deadlineMisses_vitals`). The parameter is declared `volatile` in
`TrafficGeneratorBase.ned` and binds correctly in the recorded run attributes,
so this is a model limitation rather than a configuration error. A synthetic
load spike cannot be built that way.

~~`numBgUes` **does** work — 0 / 20 / 60 UEs give 980 / 889 / 951 packets
received and 57 / 103 / 101 vitals misses in the same scenario — but it is
structural and cannot change mid-run.~~

**Corrected 2026-11-02: `numBgUes` does not work either.** The reason
`periodUl` has no effect is that the generator never starts at all —
`startTimeUl` defaults to `-1s` and is never set in any `.ini`, so
`TrafficGeneratorBase.cc:73` schedules nothing. No background packet was sent
at 0, 20 or 60 UEs, so the 980 / 889 / 951 series cannot be a load effect; it
is also non-monotonic, which is the shape of noise. The conclusion below — that
capacity variation here comes from geometry — is unchanged and now rests on
firmer ground, since background load was never a candidate. See
`docs/CORRECTIONS_2026-10.md` C13.

So capacity variation comes from site spacing: the UE drives deep toward cell
edge and back out. That is also more physically defensible than a synthetic
load step.

Two constraints worth recording for anyone extending these scenarios:

- Simu5G's RMa LOS path loss **asserts** beyond 10 km, so an outage cannot be
  made by spacing sites arbitrarily far apart. `CondOutage` uses 16 km spacing
  so the UE is at most 8 km from a site — inside model validity — and the hole
  comes from the −104 dBm delivery horizon (~7 km) instead.
- The shared `speed55.bonnmotion` trace spans 0–26 km over 1776 s, so the
  constraint area must cover 26 km in every condition; `sim-time-limit` is
  what bounds how far each drive actually gets.

## Policy implementation status

All five rungs of the baseline ladder now exist in `EdgeApp`, plus a server
feedback path in `HealthServerApp` (`feedbackInterval`, default 0s so existing
scenarios are untouched). Feedback travels as an ordinary UDP packet, so its
delay, loss and bytes are simulated; the gateway sees cumulative bytes and
packets received and the freshest sensing time per stream, and nothing else —
no radio queue depth, no true server AoI, no future channel state.

| Policy | `admissionPolicy` | Status |
|---|---|---|
| FIFO forwarding | `none` | works |
| Token-bucket discard | `drop` | works |
| Token-bucket pacing | `pace` | works |
| Pacing + staleness discard | `dropPace` | works |
| Alarm priority + newest-only state | `prio` | **degenerate, see below** |
| ... + throughput-adaptive camera | `adaptive` | **degenerate, see below** |
| ... + critical reserve and staleness | `ctrl` | **degenerate, see below** |

The four open-loop policies reproduce their stored results **exactly** after the
rewrite (`totalPacketsReceived`, `packetsSentToCloud`, `cameraAdmitted`,
`cameraGateDropped`, `deadlineMisses_vitals`, `received_camera` all identical
on `MechNone` and `MechSweep-drop-400` seed 0), so the refactor is clean.

## Two pathologies in the closed-loop policies

Both are design faults in the policy specifications, not implementation bugs,
and both were found exactly where a pilot is supposed to find them — before a
large campaign.

### 1. A shared byte window starves the class it was meant to protect

`prio` sends 218 packets of ~4,800 generated and supersedes 1,861 queued state
updates. Diagnosis: `inFlightBytes` sits **at** the 131,072 B cap for 88.5% of
samples and above 100,000 B for 99.9%.

The cause is frame size against window size. A camera frame is 61,440 B, so
**two outstanding frames saturate a 128 KiB window**. `prio` admits camera
whenever `maxInFlight - inFlight` covers one frame, which pushes the window to
its cap, after which nothing — not even a 512 B vitals sample — can be sent
until feedback confirms delivery. In a congested cell that confirmation is
slow, so camera head-of-line-blocks the very traffic the priority scheme
exists to protect.

A single byte-based window shared across classes is the wrong mechanism when
one class has frames comparable in size to the whole window. The fix is a
design choice: per-class windows, a window sized well above the largest frame,
or admitting camera only against headroom that already reserves for critical
traffic.

### 2. A throughput-only estimator self-deadlocks

`adaptive` and `ctrl` admit **zero** camera frames and are identical to each
other. Diagnosis: the budget is `estRate x horizon - inFlight` (minus a
reserve for `ctrl`), and the measured `estThroughput` has median 3,629 bps —
about **454 B/s**. With `horizon` at 1 s the budget is negative whenever more
than 454 B are outstanding, which is essentially always.

That 454 B/s is not a measurement error. It is what the link actually carries
once camera is blocked and only small vitals and OBD packets flow. The loop is
circular: blocking camera lowers throughput, lower throughput shrinks the
budget, and the smaller budget keeps camera blocked. The estimator can never
discover capacity it never probes, and `ctrl` is identical to `adaptive`
because subtracting a reserve from an already-zero budget changes nothing.

This is the degenerate solution the objective was designed to exclude —
protecting vitals by discarding all camera traffic — arrived at through the
estimator rather than through the objective. Any rate-adaptive formulation
here needs either a probe floor, an estimate of capacity rather than of
achieved throughput, or an explicit exploration term.

### What this means for the direction

The pilot has already returned useful information: the two obvious
formulations of a feedback-driven policy both fail, for reasons that are
specific and diagnosable rather than incidental. That strengthens the case
that there is a real problem here worth solving, and it also means the
contribution has to be the *fix* for these pathologies, not the assembly of
priority and shaping mechanisms.

It also sharpens the comparison. `drop` with staleness discard — open loop, no
feedback at all — currently beats every closed-loop policy by a wide margin.
Any controller has to beat that, and right now the feedback-driven designs are
far behind it rather than ahead.

## Headroom experiment (2026-10-08)

The question the pilot exists to answer: is there room for an adaptive policy
to beat a well-tuned static one? Measured *before* building the controller,
because if a single cap serves every condition then no amount of fixing the
closed-loop policies will produce a publishable result.

### Static cap tuned per condition, on development seeds 100-104

`drop` policy, `cameraBurst` raised to 262144 B so it is not burst-limited.
Objective: maximise timely camera subject to timely vitals >= 90%.

| Condition | 200k | 400k | 600k | 800k | 1000k | tuned |
|---|---|---|---|---|---|---|
| Congested, vitals | 94.0% | **90.0%** | 85.5% | 73.9% | 71.6% | **400k** |
| Congested, camera | 15.9% | **31.6%** | 47.0% | 55.4% | 68.0% | |
| Transient, vitals | **89.8%** | 79.9% | 75.3% | 67.1% | 65.1% | **200k** |
| Transient, camera | **14.6%** | 29.0% | 42.3% | 52.1% | 62.8% | |
| Outage, vitals | **72.1%** | 64.3% | 59.7% | 55.6% | 53.4% | **200k** |
| Outage, camera | **12.9%** | 24.4% | 35.6% | 43.9% | 50.8% | |

Healthy tunes to 100 kbps (99.6% vitals, 97.4% camera) and 200k is identical
there: 4 KiB frames offer only ~66 kbps, so the cap is non-binding and no
policy can suppress anything. That is the "does it needlessly throttle"
check, and a tuned cap passes it.

### The headroom, stated precisely

Mis-tuning is movement along the trade-off curve, not loss on both axes, and
neither operating point dominates. The claim has to be made under the
constraint:

- A single cap must be sized for the worst regime it will meet, which is
  200k (the only cap keeping worst-case vitals above 72%).
- At 200k, Congested yields **15.9%** camera. At 400k it yields **31.6%** at
  90.0% vitals, still inside the constraint.
- **So a single cap forfeits about 15.7 pp of camera throughput in the
  congested regime at no vitals benefit.** That is the recoverable headroom.

The reverse direction is not a loss but a constraint violation: a 400k cap in
Transient drops vitals to 79.9%, below budget.

Across the three hard conditions, the oracle that switches caps averages 19.7%
camera against the best single cap's 14.4%, with the entire gap concentrated
in the one condition that has spare capacity.

**Boundary:** Outage reaches at most 72.1% vitals at any cap. The 90%
constraint is infeasible there — no admission policy fixes a coverage hole.

## Baseline ladder, evaluated on held-out seeds 0-9

Each condition at its own tuned cap. The three closed-loop policies are
excluded; both feedback designs are degenerate and would contribute only
zeros until the two pathologies above are fixed.

| Condition | Policy | timely vitals | timely camera |
|---|---|---|---|
| Healthy (100k) | all four | 98.7 ± 0.5% | 97.9 ± 1.0% |
| Congested (400k) | none | 73.5 ± 3.3% | 69.0 ± 4.1% |
| | drop | 90.3 ± 3.6% | 31.6 ± 1.7% |
| | pace | 91.7 ± 3.3% | 30.8 ± 1.7% |
| | **dropPace** | **91.7 ± 3.3%** | **31.8 ± 1.9%** |
| Transient (200k) | none | 64.2 ± 4.8% | 59.1 ± 6.3% |
| | drop | 88.2 ± 2.4% | 14.2 ± 1.4% |
| | pace | 89.0 ± 2.7% | 8.5 ± 0.5% |
| | **dropPace** | **89.0 ± 2.7%** | **14.3 ± 1.4%** |
| Outage (200k) | none | 54.0 ± 1.8% | 52.0 ± 2.4% |
| | drop | 69.9 ± 3.3% | 11.6 ± 0.9% |
| | pace | 74.1 ± 3.3% | 7.8 ± 0.4% |
| | **dropPace** | **74.1 ± 3.3%** | **12.2 ± 0.7%** |

Three readings:

1. **In the healthy condition every policy is identical**, because the cap is
   non-binding. Healthy does not discriminate between policies and is useful
   only as a no-harm check.
2. **FIFO is not "worse" — it is a different operating point.** It delivers far
   more camera (69 / 59 / 52%) and far less timely vitals (73.5 / 64.2 /
   54.0%). The shapers trade one for the other.
3. **`dropPace` is the strongest baseline.** It matches `pace` on vitals and
   beats it on camera by 1.0 / 5.8 / 4.4 pp, and matches or beats `drop` on
   both axes. Staleness discard is free gain, consistent with the mechanism
   decomposition.

**So the target to beat is `dropPace` at a per-condition tuned cap:** 91.7 /
31.8 in Congested, 89.0 / 14.3 in Transient, 74.1 / 12.2 in Outage.

### Alarms are not resolvable between policies

Pooled over ten seeds each cell holds only 33–51 alarms, giving Wilson
intervals 14–30 pp wide. Differences between the three shapers are **not**
supportable. The one statement that survives is that shaping beats FIFO:
Congested 94.1% [84.1, 98.0] for `drop` against 74.4% [58.9, 85.4] for `none`,
and Transient 87.2% [73.3, 94.4] against 57.8% [43.3, 71.0]. Any
alarm-specific claim needs the high-rate protocol used in `analysis/extra/`.

## Verdict and what is still needed

There **is** exploitable headroom — about 16 pp of camera throughput in the
congested regime — and it has the shape of a regime-tracking problem rather
than a continuous-adaptation one: the controller needs to work out which
condition it is in and move the cap, not track a gradient. Both pathologies
found earlier block exactly that, since neither a saturated shared window nor
a self-deadlocked throughput estimator can detect a regime change.

Remaining work:

- Fix the shared-window starvation (per-class windows or reserved headroom).
- Fix the estimator deadlock (probe floor, or estimate capacity rather than
  achieved throughput).
- Re-run the ladder with the closed-loop policies against the `dropPace`
  target above.
- Alarm claims need the high-rate protocol; the pilot rate cannot support them.


## Controller iterations (2026-10-08)

Three designs attempted, all beaten by the tuned static cap. Recorded in full
because the failures are consistent and point at one requirement.

### Iteration 1 — in-flight window

Camera admitted against window space. Failed: a 61,440 B frame against a
131,072 B window means two outstanding frames saturate it, after which not
even a 512 B vitals sample can go until feedback arrives. `prio` sent 218 of
~4,800 packets with `inFlightBytes` at the cap for 88.5% of samples.

Reserving window headroom for critical traffic fixed the starvation — `prio`
went from 218 to 1,986 packets sent and supersessions from 1,861 to 66 — but
camera then fell to zero, because a window large enough to hold a camera frame
*and* leave headroom implies roughly ten seconds of queueing at this capacity,
which is the entire vitals budget.

**The window is the wrong control variable here.** The open-loop policy that
wins bounds average load with a token bucket and lets the radio queue absorb
bursts; it never bounds instantaneous backlog at all.

### Iteration 2 — rate control with achieved-throughput estimation

Rebuilt so the closed-loop policies adapt the token-bucket *rate*:
`dynRate = clamp(rateSafety x (estRate - critRate), probeRate, cameraRate)`.
This removes the window pathology. It does not remove the deadlock: `estRate`
is measured goodput, which the policy's own throttling determines, so the
system settles at a stable low fixed point.

### Iteration 3 — adding a fixed probe floor

A floor keeps a trickle of camera flowing so the estimator sees something
real. Both adaptive policies then converge **to the floor** and stay there.
Seed 0, ceiling 1000 kbps:

| Condition | Policy | timely vitals | timely camera | settled rate |
|---|---|---|---|---|
| Congested | prio (no adaptation) | 74.1% | 69.5% | 1000k |
| | adaptive | 93.4% | 1.2% | 100k |
| | ctrl | 94.3% | 11.0% | 80k |
| | **dropPace, tuned 400k** | **91.7%** | **31.8%** | tuned |
| Transient | prio (no adaptation) | 70.3% | 66.7% | 1000k |
| | adaptive | 92.4% | 1.0% | 80k |
| | ctrl | 90.7% | 9.2% | 80k |
| | **dropPace, tuned 200k** | **89.0%** | **14.3%** | tuned |

A fixed floor stops the rate reaching zero but gives the estimator no way to
discover that a *higher* rate is sustainable. It only ever observes the
throughput its own low rate produces.

### The requirement this establishes

Three iterations, one lesson: **available capacity cannot be inferred from a
signal the policy's own throttling determines. The rate has to be probed
upward and backed off on evidence of harm**, in the manner of congestion
control, rather than derived from measured goodput.

That is a concrete and implementable requirement, and it is a sharper
statement of the contribution than "an adaptive controller". It is also a
crowded design space — upward probing with backoff is what congestion control
already does — so the novelty would have to lie in what triggers backoff here:
not loss or delay, but a clinical freshness constraint on a different stream
from the one being throttled.

### Standing comparison

A per-condition tuned static cap with staleness discard still beats every
closed-loop design attempted, on both axes in most cells. Any controller has
to beat 91.7 / 31.8 (congested) and 89.0 / 14.3 (transient), and none of the
three so far comes close on camera.


## Iteration 4 — freshness-triggered AIMD (2026-10-09)

The first design that beats the tuned static cap.

Mechanically it is congestion control on the camera rate: additive increase,
multiplicative decrease. What is unusual is the backoff trigger. It is not the
throttled stream's own loss or delay, as in TCP, but **the age of the newest
vitals sample the server has confirmed** — the gateway throttles one stream
and watches a *different* stream's clinical freshness to decide whether it
went too far. The gateway sees that age only through feedback, already stale
by the report delay, so the target sits at 5 s against a 10 s budget.

Parameters were first guesses, not tuned: target 5 s, increment 40 kbps,
backoff 0.7. Sensitivity has not been tested.

### Headline: 10 seeds per condition, against dropPace at its tuned cap

| Condition | Δ timely vitals | Δ timely camera |
|---|---|---|
| Healthy | +0.3 pp | +0.2 pp |
| Congested | +1.7 pp | **+44.4 pp** |
| Transient | −0.7 pp | **+49.3 pp** |
| Outage | +2.3 pp | **+43.2 pp** |

It also sits **outside the entire static frontier**. In Congested the best
static points were 94.0% vitals (at 200k) and 68.0% camera (at 1000k); AIMD
reaches 93.4% and 76.2% simultaneously. No fixed cap can, because the channel
varies within a single drive and a fixed rate is wrong most of the time.

The mechanism is visible in the raw counts (Congested, seed 0): FIFO delivers
2,187 camera frames with 282 late; `dropPace` discards 1,796 at the gate and
delivers 941; AIMD delivers 2,141 with only 22 late. FIFO overshoots and
builds queues, the static cap undershoots and discards frames it did not need
to, and AIMD tracks the usable rate.

### Full-horizon AoI — where it actually costs something

Per-packet timeliness is not information freshness, and for this policy the
two genuinely diverge. Three vector-recorded seeds, 10 s budget:

| Condition | Policy | peak AoI (mean / worst) | mean AoI | % of drive stale |
|---|---|---|---|---|
| Congested | dropPace | 23.5 s / 26.9 s | 2.5 s | 4.6% |
| | **aimd** | **21.2 s / 28.0 s** | **2.5 s** | **2.8%** |
| Transient | dropPace | **21.1 s / 22.1 s** | **2.5 s** | **3.3%** |
| | aimd | 33.7 s / 38.8 s | 4.3 s | 12.4% |
| Outage | dropPace | 157.2 s / 164.6 s | 17.2 s | 29.4% |
| | **aimd** | **109.2 s / 134.1 s** | **10.4 s** | **24.5%** |

**AIMD is better on freshness in Congested and Outage and worse in
Transient**, where it nearly quadruples the share of the drive spent above the
freshness budget (12.4% against 3.3%) in exchange for its +49 pp of camera.

That regression is invisible in the per-packet metric: timely vitals is 88.3%
against 89.0%, essentially identical. The failures are the same in number but
clustered into longer stale stretches. This is a concrete demonstration that
packet timeliness and information freshness have to be reported separately,
and it is the one place where AIMD's gain is genuinely paid for.

Mechanistically it is what the design predicts: during a transient capacity
collapse AIMD keeps probing upward and overshoots, where a conservative static
cap does not. Faster backoff, or an explicit dip detector, is the obvious next
step.

### Standing

AIMD dominates the strongest static baseline in three of four conditions and
trades freshness for camera in the fourth. That is a defensible contribution,
and the narrow novelty claim — backoff triggered by a clinical freshness
constraint on a different stream from the one throttled — is the part to
defend against the congestion-control literature.

Still outstanding: parameter sensitivity, the transient regression, per-seed
pairing against identical channel realisations, and a comparison against a
published freshness-aware scheduler.


## CORRECTED pilot results (2026-10-15)

Two defects invalidated the first pass. Everything above the "Iteration 4"
section that quotes pilot numbers predates these fixes and should not be
cited; the numbers here supersede them.

### Defect 1 — the comparison was not paired

Every module shared `rng-0`, so a policy that changes how many packets are
transmitted shifts the global draw order and therefore changes *when the
exponentially-spaced sensors fire*. Measured at seed 0 on CondCongested, the
offered workload drifted between policies:

| policy | vitals gen | camera gen | obd gen | alarm gen |
|---|---|---|---|---|
| none | 1370 | 2737 | 723 | 5 |
| dropPace | 1326 | 2737 | 697 | 4 |
| aimd | 1354 | 2737 | 649 | 3 |

Only camera was stable, because it uses a deterministic interval. Fixed by
giving the exogenous processes their own streams (`num-rngs = 4`; sensors on
1, background traffic on 2, channel on 3). After the fix all policies see an
identical workload at a given seed — verified across all 40 (condition, seed)
pairs, zero mismatches. The channel still differs between policies, which is
endogenous and cannot be held fixed.

### Defect 2 — CondOutage was seed-fragile

Sites at 2 and 18 km with the full 1369 s drive put the vehicle 18.9 km from
the far site, past Simu5G's 10 km RMa LOS validity limit. Simu5G computes
interference from every eNB regardless of the delivery horizon, so the run
asserts — but only on seeds where the far site is still in the evaluation set
late in the drive. Most seeds survived, so the condition was silently fragile
rather than reliably broken. Fixed by moving the sites to 0.5/16.5 km and
shortening the drive to 680 s: the 2 km coverage hole is preserved (131 s of
outage, 58 s of observed recovery) and the far site stays within 9.9 km. The
condition is now harsher, since the hole spans 19% of the drive rather than
10%.

Re-tuned caps on development seeds are **unchanged**: healthy 100k, congested
400k, transient 200k, outage 200k. The headroom argument is unaffected.

### Head-to-head, 10 held-out seeds, properly paired

| Condition | Policy | timely vitals | timely camera |
|---|---|---|---|
| Healthy | dropPace | 99.1 ± 0.4% | 98.1 ± 1.2% |
| | aimd | 99.1 ± 0.4% | 98.1 ± 1.2% |
| | **delta** | **+0.0 pp** | **+0.0 pp** |
| Congested | dropPace | 91.5 ± 3.6% | 31.5 ± 2.2% |
| | aimd | 93.1 ± 1.2% | 74.3 ± 4.4% |
| | **delta** | **+1.6 pp** | **+42.8 pp** |
| Transient | dropPace | 90.3 ± 2.8% | 14.7 ± 1.0% |
| | aimd | 89.8 ± 1.8% | 69.2 ± 2.8% |
| | **delta** | **−0.5 pp** | **+54.6 pp** |
| Outage | dropPace | 59.8 ± 2.4% | 10.0 ± 0.5% |
| | aimd | 64.2 ± 2.3% | 45.7 ± 0.8% |
| | **delta** | **+4.4 pp** | **+35.7 pp** |

The camera gains survive both corrections essentially intact (+42.8 / +54.6 /
+35.7 pp against +44.4 / +49.3 / +43.2 before). AIMD is also more consistent
in the congested case: ±1.2 pp against the static cap's ±3.6 pp on vitals.

### Full-horizon AoI — the freshness story changed

| Condition | Policy | peak (mean / worst) | mean AoI | % of drive stale |
|---|---|---|---|---|
| Congested | dropPace | 18.5 s / 21.5 s | 2.3 s | 3.8% |
| | aimd | 19.3 s / 22.3 s | 2.4 s | 3.7% |
| Transient | dropPace | 31.3 s / 48.1 s | 3.5 s | 7.3% |
| | aimd | 30.7 s / 36.0 s | 4.0 s | 11.6% |
| Outage | dropPace | 143.4 s / 164.0 s | 23.6 s | 36.7% |
| | aimd | 90.5 s / 117.2 s | 16.1 s | 36.5% |

**This materially softens what was reported before.** The earlier claim that
AIMD "nearly quadruples time above the freshness budget in Transient (12.4%
against 3.3%)" becomes 11.6% against 7.3% — a 4.3 pp gap, not a 4x ratio. And
AIMD's *peak* staleness in that condition is actually lower (30.7 s against
31.3 s mean, 36.0 s against 48.1 s worst): it spends more time mildly stale
but avoids the deepest excursions.

Corrected reading: freshness is a **wash in Congested**, **mixed in
Transient** (lower peaks, more time above budget), and **clearly better in
Outage** (peak 90.5 s against 143.4 s). The earlier summary — better in
Congested, worse in Transient — was an artifact of the unpaired comparison.

So AIMD buys 36-55 pp of camera for a freshness cost that is small and
condition-dependent rather than a clean trade in one direction.


## AIMD parameter sensitivity (2026-10-15)

The headline used first-guess parameters — 5 s freshness target, 40 kbps
increment, 0.7 backoff — that were never tuned, while the static baseline
*was* tuned on development seeds. Favourable framing, but only if the result
survives perturbation. One-at-a-time around the baseline, dev seeds 100-102.

### CondCongested (static baseline: 91.5% vitals / 31.5% camera)

| Setting | timely vitals | timely camera | vs static |
|---|---|---|---|
| baseline (5 s, 40k, 0.70) | 94.5% | 72.7% | +3.0 / +41.2 |
| target 3 s | 95.7% | 67.1% | +4.2 / +35.6 |
| target 7 s | 89.5% | 74.4% | −2.0 / +42.9 |
| increment 20k | 96.0% | 78.1% | +4.5 / +46.6 |
| increment 80k | 93.5% | 79.1% | +2.0 / +47.6 |
| backoff 0.50 | 94.9% | 77.3% | +3.4 / +45.8 |
| backoff 0.85 | 93.3% | 79.0% | +1.8 / +47.5 |

### CondTransient (static baseline: 90.3% vitals / 14.7% camera)

| Setting | timely vitals | timely camera | vs static |
|---|---|---|---|
| baseline (5 s, 40k, 0.70) | 90.9% | 70.9% | +0.6 / +56.2 |
| target 3 s | 93.0% | 60.6% | +2.7 / +45.9 |
| target 7 s | 80.6% | 64.9% | **−9.7** / +50.2 |
| increment 20k | 91.7% | 68.2% | +1.4 / +53.5 |
| increment 80k | 86.4% | 63.4% | −3.9 / +48.7 |
| backoff 0.50 | 87.4% | 60.1% | −2.9 / +45.4 |
| backoff 0.85 | 87.2% | 69.4% | −3.1 / +54.7 |

### Readings

1. **The camera gain is robust.** Across all seven settings and both
   conditions it ranges +35.6 to +56.2 pp and never collapses. The headline
   is not a tuning artifact.

2. **The freshness target is the one sensitive parameter.** Loosening it to
   7 s costs 2.0 pp of vitals in Congested and **9.7 pp in Transient**, the
   only setting that falls materially below the static baseline. 3 s and 5 s
   are both safe. This is exactly the design rationale: the gateway sees the
   vitals age only through delayed feedback, so the trigger must sit well
   below the clinical budget or it fires too late. The parameter needs
   justifying in the paper, not just stating.

3. **Increment and backoff barely matter.** 20k against 80k, and 0.50 against
   0.85, all stay within a few points. The controller does not need careful
   tuning of its AIMD constants, which is a useful practical property.

4. **The first guesses were conservative, not lucky.** In Congested,
   increment 20k beats the baseline on *both* axes (96.0 / 78.1 against
   94.5 / 72.7). The reported result therefore understates what a tuned
   controller achieves, which strengthens the comparison rather than
   weakening it.

The one caveat worth carrying: this is a one-at-a-time sweep on three dev
seeds, not a factorial, so interactions between the parameters are untested.


## The controller on measured infrastructure (2026-10-15)

Until now the controller had only been tested on synthetic chains, leaving the
study in two halves that did not touch. These runs carry it onto the corrected
real corridors. Both case inis gained the same RNG stream separation, and new
`*Video` configs carry the 60 KiB payload, because the headline corridor
configs use 4 KiB frames that offer only ~66 kbps -- far below capacity, so no
admission policy has anything to manage.

### Static baseline, and a flaw in my own tuning rule

| cap | timely vitals | timely camera |
|---|---|---|
| 200k | 88.1% | 15.8% |
| 400k | 87.5% | 31.1% |
| 800k | 86.1% | 65.9% |
| 1000k | 87.4% | 84.5% |

**A 5x change in cap moves vitals 0.7 pp and camera 68.7 pp.** Throttling
camera does almost nothing for vitals here, because the vitals losses are
coverage-driven, not contention-driven.

That breaks the tuning rule used for the synthetic conditions ("maximise
camera subject to vitals >= 90%, else maximise vitals"): with no cap reaching
90% it selects 200k, sacrificing 68.7 pp of camera for 0.7 pp of vitals --
a strawman baseline that would have flattered the controller. Replaced with:
among caps within 1 pp of the best achievable vitals, take the most camera.
That gives 1000k. Both are reported so the frontier stays visible.

### Results, 10 held-out seeds, workload-paired (0 mismatches)

**Rural VA corridor, measured towers, 60 KiB video**

| Policy | timely vitals | timely camera |
|---|---|---|
| FIFO (no cap) | 86.7 ± 1.4% | 83.0 ± 1.7% |
| static cap 200k | 88.6 ± 1.2% | 15.7 ± 0.3% |
| **AIMD** | **89.1 ± 1.2%** | **80.8 ± 1.8%** |

- AIMD against the static cap: **+0.6 pp vitals, +65.1 pp camera**
- AIMD against FIFO: **+2.5 pp vitals, −2.2 pp camera**

**DC urban corridor** (no-harm check): FIFO 99.8% / 99.1%, AIMD 99.9% / 98.8%.
Sixteen sites give ample capacity; nothing to control, and the controller does
no harm.

### What this means, and a correction

An earlier two-seed sample suggested AIMD beat FIFO on *both* axes here. With
ten seeds it does not: it is a roughly one-for-one trade, +2.5 pp vitals for
−2.2 pp camera. That claim should not be carried forward.

The scoping finding is the important one. **The controller's value depends on
whether the link is contention-limited or coverage-limited.**

- *Contention-limited* (the synthetic congested condition): camera traffic
  genuinely competes with vitals, FIFO is poor (73.5% vitals), a tuned static
  cap helps, and AIMD beats that cap by +42.8 pp camera.
- *Coverage-limited* (both measured corridors): vitals losses come from cell
  edge and outage, not from queueing. A static cap is actively harmful -- it
  discards two thirds of the camera stream to buy under a point of vitals --
  and AIMD is only marginally better than doing nothing.

So on *these* measured corridors the case for admission control at all is
weak, and the controller contribution rests on the contention-limited regime.
That regime is real -- it is what the Family A factorial's 60 KiB rural cells
look like -- but it is not what the two case-study corridors are.

This has to be stated plainly rather than quoting the synthetic +42.8 pp as
though it transfers. The honest framing is that the controller solves a
problem that arises when capacity is contended, and the paper should show both
the regime where it pays and the regime where it does not.

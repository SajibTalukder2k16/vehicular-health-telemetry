# Positioning against freshness-aware scheduling and rate control

Added 2026-10-27. This was the gating risk for the novelty claim: IoT-J
publishes a great deal of AoI-aware scheduling, and the claim had never been
checked against it.

**Verification depth differs by entry and is stated per entry.** Two were read
in full text, two from the abstract/landing page only, one from an indexed
abstract behind a paywall. Nothing here should be cited in the manuscript
without the full text in hand.

## The claim, restated

The contribution is not "freshness drives rate control" — that exists (see
A³L-FEC below). It is the conjunction of three properties:

* **(E) Endpoint-only.** The decision is made at a single sender. No
  programmable switch, no scheduling support at intermediate nodes, no
  network-wide optimizer, no knowledge of topology or competing demand.
* **(X) Cross-stream signal.** The throttled stream is *not* the stream whose
  freshness is measured. Camera rate is driven by the age of the newest
  *vitals* sample the receiver has confirmed, arriving as delayed feedback.
* **(W) Time-varying wireless capacity with mobility.** Capacity changes
  continuously with position and handover, and — the mechanism result — cannot
  be inferred from any signal the policy's own throttling determines.

Each prior work below has at most two of the three.

## The five nearest works

### A³L-FEC (arXiv:2410.05852, 2024) — closest on mechanism
*Read in full text (HTML v2).*

Receiver-side rate adaptation for freshness: the receiver measures average
chunk delay, age-violation ratio and delivery ratio per monitoring interval,
computes a rate and feeds it back to the transmitter. Application layer over
UDP with rateless FEC. Control law is multiplicative decrease on persistent
violation plus a probe on high delivery ratio — structurally close to ours.

**Has (E), partially (W). Does not have (X).** The signal is the monitored
stream's *own* age violation. The main evaluation is a single flow. The
multi-transmitter extension (Sec. IX) couples rates through a system-wide
average violation, but it ranks no stream by criticality, is unevaluated
("Future work will refine this extension"), and moves in the *opposite*
direction from protection: "Transmitters with higher age violations are
assigned higher rates." Evaluated in MATLAB, ns-3 and Mininet-WiFi over fixed
wired-style bottlenecks; cellular and vehicular settings are motivation only,
never evaluated.

**This is a must-cite and arguably a must-compare.** See the ablation below.

### FATE / IFC (arXiv:2106.02156, Tseng, Han, Wierman, 2021) — closest on the trade
*Read from the abstract/landing page only.*

Wired networks shared by throughput-oriented and low-AoI flows; the same trade
we make. Two layers: freshness-aware traffic engineering computes sending rates
by optimization, and in-network freshness control enforces them "through
scheduling at each node's outport." Reports ~5% throughput given up for 49–71%
lower AoI.

**Has the two-class trade. Has neither (E) nor (W).** Explicitly not
endpoint-only — it requires scheduling support at every in-network node — and
explicitly wired, positioning itself against prior wireless AoI work. Rates
come from a network-wide optimization, not from online feedback.

### FAIFO (Ad Hoc Networks, 2022) — different layer
*Indexed abstract only; full text is paywalled. Flagged for library check.*

Programmable packet scheduling in the PIFO / SP-PIFO / AIFO lineage. Two
queues: an admission step filters high-priority low-latency packets into queue
A, then freshness decides whether *discarded* packets are worth caching in
queue B, balanced by a modified credit-based shaper.

**Has none of the three as stated.** It is a data-plane queue discipline
requiring a programmable switch; it reorders and salvages packets already
offered rather than controlling an offered rate, and it uses no receiver
feedback. Cited as the freshness-aware-queueing alternative to rate control.

### LGFS family (PP-MAF-LGFS, NP-LGFS; Bedewy, Sun, Shroff et al.) — server discipline
*Read from surveys and the AoI survey PDF, not the primary papers.*

Serve the last-generated packet first; the age-penalty multi-flow variant
PP-MAF-LGFS combines preemptive priority, maximum-age-first across streams and
LGFS within a stream, and is lex-age-optimal for symmetric non-decreasing age
penalties under exponential service.

**Has none of the three.** A queue discipline, not a rate controller: it
reorders what is already queued, assumes the server knows every generation
timestamp instantly rather than through delayed feedback, and serves
maximum-age-first *across* streams rather than throttling one stream *for*
another. Its optimality is for abstract service distributions, not a mobile
radio. Cited as the theoretical optimum our setting cannot reach.

### Mixed-criticality AoI (arXiv:2211.05797, 2022) and vehicular-edge MC scheduling
*Abstracts only.*

The 2022 paper introduces mixed-criticality by assigning different age-penalty
functions per stream and optimizing transmission time and outage probability
for dense sensor–actuator networks — PHY-layer resource allocation, not
gateway admission. The 2026 arXiv entry a reviewer may raise
(arXiv:2608.19557, Zakerian, Aug 2026, "Deadline-Aware Mixed-Criticality Task
Scheduling at the Autonomous-Vehicle Edge") schedules *computation*: perception
tasks placed on MEC servers by a deadline-ordered contract-net auction. It
shares our vocabulary and none of our problem — the scheduled object is a task,
not an uplink byte.

## What the check changed

1. **The claim had to be narrowed.** "Freshness-driven rate adaptation" was
   not available to claim; A³L-FEC has it. The cross-stream signal, at an
   endpoint, over a mobile radio, is.
2. **Two must-cites were missing** from the draft entirely: A³L-FEC and
   FATE/IFC. Both are freely available, so this is not blocked.
3. **It exposed a missing ablation**, which is the real finding here.

## The missing ablation

A reviewer who knows A³L-FEC will ask the obvious question: *why must the
signal come from the other stream? Measure the throttled stream's own
freshness.* We cannot currently answer it. None of the seven implemented
policies is own-stream age control — `adaptive` and `ctrl` use a throughput
estimate (failed design #2), and `aimd` uses cross-stream vitals age.

The experiment is small and the plumbing already exists: `GatewayFeedback`
carries `freshestCamera` alongside `freshestVitals`, so an `aimdSelf` policy is
`aimd` with one substituted field, identical in every other respect.

**This was run on 2026-10-28 and the prediction was WRONG; see
`docs/ABLATION_CROSS_STREAM.md`.** The first pass appeared to confirm it, but
that was a bug in this project's own code — `aimdSelf` was accidentally also
denied the stale-camera-frame discard, giving it a second difference from
`aimd`. Corrected, the two signals are comparable: the self-signal arm sits at
a more conservative point on a shared frontier (+1.4 to +5.5 pp vitals, camera
differences not significant synthetically; **+2.86 ± 0.85 / −7.21 ± 2.03 pp
on real corridors at 10 seeds**). Neither dominates — the arms were never
matched on vitals, so the comparison is between operating points, not between
a better and a worse signal.

So **the cross-stream signal is novel but not better**, and the paper must not
claim necessity. What is load-bearing turns out to be the queue discipline: a
freshness signal is only usable if the queue feeding it discards stale work,
otherwise it measures the backlog rather than the link and the controller
deadlocks on the probe floor.

**Settled on 2026-10-30 by a frontier comparison** (560 runs, `freshnessTarget`
swept for both arms): with each arm tuned to its own best target, the
difference in best achievable timely camera is **+0.7 ± 1.1 pp and reverses
sign across corridors**. The signal choice confers no measurable advantage; the
−7.2 pp gap seen at a shared target was a tuning artifact. What it does change
is the *reachable* vitals range — the own-stream arm sits in a narrower, higher
band, and on c14 the two ranges do not overlap at all. See
`docs/ABLATION_CROSS_STREAM.md`.

This narrows rather than extends the project's mechanism result. "Capacity
cannot be inferred from a signal the policy's own throttling determines" holds
for the throughput estimator, which is directly the consequence of the admitted
rate; it does not hold for the throttled stream's own age once stale work is
discarded.

Practical consequence for positioning: A³L-FEC is not only a must-cite, it is
the natural **baseline**, and `aimdSelf` is our implementation of its signal
choice in this setting. Reporting it as comparable is more credible than
claiming a mechanism advantage the data does not support.

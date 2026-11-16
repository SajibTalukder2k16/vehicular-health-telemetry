# Phase 2: the waveform rung at the right W, and both deferral rules invert

**480 runs, 2026-11-10/11.** `results_phase2/`, extract in `analysis/phase2/`.
Four arms × four conditions × 30 seeds, seeds matched to the Gate A corpus so
every arm pairs directly against `results_escalation_vec/` at the same rung.

Predictions were recorded in `tools/escalation_phase2.sh` **before** the run and
in `PLAN_2026-11.md` §8.1. All three resolved. Two were right; one was right for
the wrong reason, which is worse than being wrong and is written up as such.

Companions: `VERIFICATION_FRONTIER.md` (the frontier), `GATE_A_RESULT.md`
(C2's refutation), `PARAMETER_PROVENANCE.md` §A.5 (W), §A.2 (M4).

---

## 1. Result: the design rule holds at the W the frequency domain requires

`PARAMETER_PROVENANCE.md` §A.5 established that W = 30 s is SDNN-grade, and
that LF/HF — which C1's variability case actually uses — needs W ≥ 120 s, so the
waveform rung is **14,400 B**, not 3,584 B. That size falls between the measured
E2 and E3 arms, so it was measured rather than interpolated.

Median dispatch gap (how much later the decision can be made than the alert
arrives), seconds:

**CORRECTED 2026-11-11** — every gap in this document was ~1.7 ms low, because
`dispatch_times.py` compared two delays measured from different creation
instants (`EDGE_COST_RESULT.md` §1). At this corpus's 1.28 ms edge the error is
≤1.3 ms, every budget-miss percentage below is unchanged, and no conclusion
moves; the tables carry the corrected figures.

| condition | E2 3.5 KiB | **E2′ 14.4 kB** | E3 56 KiB | E2′ vs E3 |
|---|---|---|---|---|
| CondHealthy | 0.0040 | **0.0330** | 0.1280 | **3.9× better** |
| CondCongested | 0.0200 | **0.0800** | 0.2590 | **3.2× better** |
| CondTransient | 0.0170 | **0.0970** | 0.3270 | **3.4× better** |
| CondOutage | 0.0280 | **0.1235** | 1.1110 | **9.0× better** |

Escalations exceeding the 4 s eCall budget: CondCongested 2.1 % (E2 0.7 %, E3
5.6 %), CondTransient **5.0 %** (E2 7.4 %, E3 15.6 %), CondOutage 36.1 % (E2
34.3 %, E3 38.9 %).

**The rule survives, with one honest qualification.** Waveform verification at
LF/HF-grade W is **3.2–9.0× cheaper than one JPEG** and halves the budget misses
in congested and transient conditions. But it is **not free the way E2 is** —
33–124 ms of dispatch delay against E2's 4–28 ms, roughly an order of magnitude
more. So the paper's rule should read:

> **Verify from the waveform, not the image.** At SDNN grade (W = 30 s, 3.5 KiB)
> verification is effectively free. At LF/HF grade (W ≥ 120 s, 14.4 kB) it costs
> tens of milliseconds — still 3–9× less than a single still frame, and inside
> the 4 s budget everywhere except a coverage outage.

Interpolating from E2 and E3 would have been safe here. It was still right to
measure it, because the claim is about exactly this point.

---

## 2. Result: pacing at E3 is a bit-identical no-op, by construction

Predicted in `tools/escalation_phase2.sh` from the bucket arithmetic, not from
the data: the inherited gate is `cameraRate = 1 Mbps`, `cameraBurst = 65536 B`,
and a burst smaller than the bucket is admitted whole and instantly.
E3 = 57,344 B < 65,536 B.

| condition | E3 / policy none | E3 / policy pace |
|---|---|---|
| CondHealthy | 0.1444 / gap 0.1280 | **0.1444 / gap 0.1280** |
| CondCongested | 0.3242 / gap 0.2590 | **0.3242 / gap 0.2590** |
| CondTransient | 0.4155 / gap 0.3270 | **0.4155 / gap 0.3270** |
| CondOutage | 1.6501 / gap 1.1110 | **1.6501 / gap 1.1110** |

Identical to four decimal places on every statistic, in every condition.

**This is a structural null, not a statistical one**, and that makes it more
useful: no sample size can change it. **The mechanism layer's gate does not
engage at all below E4** — not for E1, E2, E2′ or E3. Any paper or system that
reports "we applied admission control to the evidence" at these volumes is
reporting a no-op. The gate's parameters were set for a continuous 2 Hz camera
stream; an escalation burst is a different object, and the same numbers do not
transfer.

---

## 3. Result: C4.1 inverts — temporal spreading now harms

C4.1 was "volume reduction beats temporal spreading", measured as an *alert*
protection rule. Under C2′ the alert needs no protection, so pacing can only
delay what dispatch waits on. Predicted to invert. It does.

E4 (138,000 B, the only rung that exceeds the bucket — 72,464 B must wait for
tokens at 1 Mbps ≈ 0.58 s):

| condition | gap, policy none | gap, policy **pace** | penalty | > 4 s, none → pace |
|---|---|---|---|---|
| CondHealthy | 0.2330 | **0.5850** | **2.51×** | 0.0 % → 0.0 % |
| CondCongested | 0.6705 | **0.9440** | 1.41× | 4.9 % → **10.6 %** |
| CondTransient | 0.7630 | **1.0270** | 1.35× | 17.3 % → 18.8 % |
| CondOutage | 1.8700 | **2.0780** | 1.11× | 41.7 % → 44.9 % |

Pacing more than doubles budget misses in CondCongested and costs 1.1–2.5× the
dispatch gap everywhere. **The penalty is largest where the link is healthiest**
(2.51× in CondHealthy, 1.11× in CondOutage) — because where the radio is the
bottleneck the gate is not, so spreading adds nothing to a delay the network
already imposes. A rule that was free under the old framing is a tax under the
derived one.

---

## 4. Result: C4.2 inverts, and the instrumentation hides it

> ## ⛔ WITHDRAWN 2026-11-12 — THIS ENTIRE SECTION MEASURED A BUG IN OUR CODE
>
> Everything below about `dropPace` delivering **45–47 %** of the evidence is an
> artefact of this project's own staleness test and is **withdrawn**. It is kept
> in full, unedited, because the failure is instructive and because a withdrawn
> claim that disappears is worse than one that stays visible.
>
> **The defect.** The test was
> `simTime() - head->getArrivalTime() > cameraMaxAge`. Evidence is built with
> `new` inside `EdgeApp::escalate()` and handed on by function call — never
> *sent* — so the kernel never stamps its arrival time and it reads **0**. The
> test therefore degenerated to `simTime() > cameraMaxAge`: once the clock
> passed `maxAge`, **every** pending chunk was discarded regardless of how long
> it had actually waited.
>
> **The signature, which is worth recognising.** In the gate sweep, dispatch
> latency, delivered fraction *and* the stale-drop count were **byte-identical
> across a 16× range of `cameraMaxAge`** (0.5 s → 8 s). A parameter that changes
> nothing over 16× is either irrelevant or not being read. And the drop count
> equalled exactly the chunks that did not fit the initial bucket — a bucket
> quantity wearing a staleness label.
>
> **The decisive test.** Set `maxAge` *above* the 1369 s simulation horizon, so
> that `simTime() > maxAge` can never hold. Drops went **416 → 0** and delivery
> **365 → 785** of 792 chunks. Nothing but the degenerate comparison explains
> that.
>
> **The fix**, `EdgeApp.cc`: use `getCreationTime()`, which `cMessage` stamps at
> construction. It is correct for edge-built evidence and a better question for
> a camera frame — *how old is this observation*, not *when did it reach the
> gate*. After the fix: `maxAge` 0.5 s drops 64 chunks (the tail past the
> 0.58 s drain), `maxAge` 2 s and 8 s drop **nothing**.
>
> **What replaces it is stronger, and derived.** The inherited
> `cameraMaxAge = 2 s` is a **third structural no-op**: staleness discard fires
> iff `maxAge < (B−b)/r = 0.5797 s`, so at 2 s it cannot fire at all. With
> Prop 1 (the bucket) and Props 2–3 (pacing is a Pareto loss), **all three
> inherited gate parameters provably do nothing useful on evidence traffic.**
> See `GATE_DERIVATION.md` Prop 4 and `GATE_SWEEP_RESULT.md`.
>
> **What survives as written.** Only the methodological warning, and it now has
> two independent demonstrations rather than one: *score a deferral policy on
> verification completeness, never on dispatch latency.* This project was fooled
> twice here — first by a counter scoped to the wrong class (§4's own correction
> note below), then by this. Both times the latency metric looked fine.

C4.2 was "staleness discard is free — and under C2 it is *principled*: stale
evidence of a health event cannot verify one." The second half still reads well.
The first half is now actively dangerous.

`dropPace` adds `cameraMaxAge = 2 s`. On the latency statistics it looks like a
**win over doing nothing**:

| condition | gap, none | gap, **dropPace** | apparent change |
|---|---|---|---|
| CondHealthy | 0.2330 | 0.0950 | **2.5× "better"** |
| CondCongested | 0.6705 | 0.3890 | 1.7× "better" |
| CondTransient | 0.7630 | 0.4600 | 1.7× "better" |
| CondOutage | 1.8700 | 1.0520 | 1.8× "better" |

**It is not better. The server is verifying on half the evidence.** Chunks the
server actually received, as a fraction of chunks emitted:

| condition | E4 / none | E4 / **dropPace** |
|---|---|---|
| CondHealthy | 99.0 % | **47.1 %** |
| CondCongested | 97.4 % | **46.2 %** |
| CondTransient | 93.6 % | **45.1 %** |
| CondOutage | 92.1 % | **45.4 %** |

Median chunks per paired burst falls from **99 to 47**. A faster decision made
on 45 % of a verification payload is not a faster decision — it is a
verification failure that reports as a latency improvement.

**And the discard hides in plain sight.** `evidenceChunksDropped` reads **0** in
every `dropPace` run, because that counter records buffer refusals and the
staleness-discard sites never tested `getSourceType()`. So the policy improves
the headline latency, leaves the obvious drop counter at zero, and halves the
evidence. **Anyone evaluating this policy on dispatch latency alone would adopt
it.**

> **CORRECTED 2026-11-12 — "silently" was an overstatement, and the precise
> version is more useful.** The loss was *not* invisible: `cameraStaleDropped`
> recorded all of it — 20,800 chunks across the 120 `dropPace` runs, a mean of
> 173 per run. And because these runs set `cameraTerminatesAtEdge=true`, the
> camera never enters that queue, so **every one of those was an evidence
> chunk**. The failure is **misattribution, not absence**: the loss is fully
> counted under a name that says "camera", while the correctly-named counter
> reads zero and nothing points from one to the other.
>
> Fixed in the model rather than only in prose: `EdgeApp` now records
> `evidenceChunksStaleDropped` and `evidenceChunksLost`
> (= refusals + staleness), leaving `evidenceChunksDropped` with its original
> meaning so the corpora on disk stay comparable. Verified on a probe run —
> `evidenceChunksStaleDropped` = 416 = `cameraStaleDropped`, exactly, with
> `evidenceChunksDropped` = 0 and 371 of 792 chunks delivered (46.8 %).
>
> The design rule is unchanged. What changes is the instrumentation lesson: the
> counter an implementer would reach for is not wrong, it is *scoped to the
> wrong class*, which is harder to notice than a missing counter.

> **The design rule, stated as a warning.** Under an architecture whose server
> verifies before dispatching, evidence-side staleness discard must be scored on
> *verification completeness*, never on dispatch latency — and the latency
> metric will actively mislead. This is C4.2 not merely inverting but becoming a
> trap, and it is a trap this project walked into with its own instrumentation.

---

## 5. What is not solid here

1. **"Verification completeness" is a proxy.** Fraction of chunks received is
   not the same as whether a server could actually verify from a partial
   waveform or a partial JPEG. The real question — how much of each evidence
   type suffices — is a detection question this project has no basis to answer
   (`PLAN_2026-11.md` §15, out of scope). The paper must say "45 % of the bytes
   arrived", not "verification failed".
2. **One gate configuration.** All of §2–§4 is at `cameraRate = 1 Mbps`,
   `cameraBurst = 65536 B`, `cameraMaxAge = 2 s`, inherited deliberately from
   the mechanism layer to answer RQ4 as written. A retuned gate would behave
   differently; the finding is that the *inherited* rules do not transfer, not
   that no gate could work.
3. **Edge processing is at the unsourced `uniform(0.5ms, 2ms)`** (M4,
   `PARAMETER_PROVENANCE.md` §A.2). Common to every arm, so the contrasts here
   are unaffected — **now measured rather than assumed**: a 960-run sensitivity
   campaign finds the dispatch gap invariant to edge cost in 23 of 24 paired
   cells, and this document's E2′-beats-E4 rule holding in 20 of 20
   (`EDGE_COST_RESULT.md` §3). The absolute dispatch figures here are
   **30–283 ms optimistic**, not 20–90 ms: the edge is a single FIFO shared with
   the vitals stream, so its per-frame latency is 1.3–3.0× the service time.
4. **The 4 s budget** maps eCall's MSD span onto a wider span (§A.6); the
   comparison is conservative but not like-for-like.
5. **CondHealthy remains thin** — 37 escalations, 320 s window, 10 of 30 seeds
   with no escalation at all.

---

## 6. Provenance

```sh
python3 tools/dispatch_times.py analysis/phase2/escalation_latencies.csv.gz
```

reproduces §1–§4's dispatch table **identically** to the 480-run corpus.
The scalar extract is verified value-by-value:

```
OK: 2704204 values match exactly; 38880 histograms sum to their recorded count
```

Pairing diagnostic: **100 % of escalations paired** in all 16 cells
(`--report-pairing`), median creation offset 1.22–1.28 ms as expected from edge
processing.

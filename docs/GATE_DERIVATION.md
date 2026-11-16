# C4, derived: a token bucket in front of the verification payload

**Written 2026-11-12.** This document replaces C4.1's empirical claim with a
derivation, for the same reason C1 is a derivation: a measured result invites
*"you chose bad parameters"*, and a derivation has no parameters to choose.

C4.1 was measured at one inherited gate configuration — `cameraRate = 1 Mbps`,
`cameraBurst = 65536 B`, `cameraMaxAge = 2 s` — and the honest limit in
`PHASE2_RESULT.md` §5.2 was that *the inherited rules do not transfer*, not that
no gate could work. That is weaker than it sounds, and a reviewer will say
*retune it*. So: derive first, then search the space to confirm (§6).

Companions: `PHASE2_RESULT.md` (the measurements), `VERIFICATION_FRONTIER.md`
(C3, the budget), `PLAN_2026-11.md` §6 (C2′), §8.1 (C4).

---

## 1. The gate, as a model

`EdgeApp`'s deferrable path is a token bucket of depth `b` bytes filling at `r`
bytes/s, draining to the uplink. An escalation emits its evidence as `B` bytes
in one instant (`EdgeApp::escalate()` — M2 emits the alert and all of its chunks
together), so the burst meets a full bucket.

Write `A(t)` for cumulative bytes the gate has admitted to the uplink by time
`t` after the escalation. Then

```
    A_none(t) = B                      for all t >= 0      (no gate)
    A_pace(t) = min(B, b + r*t)                            (token bucket)
```

Two assumptions, both stated rather than assumed silently:

* **(A1)** The uplink is **work-conserving**: it does not idle while it holds
  deliverable work. This is a property of the radio scheduler, not of our code.
* **(A2)** Both arms deliver the **same byte set**. Where they do not — because
  one arm overflows a buffer and the other does not — latency and completeness
  must be read together, not separately. §5 is where this is checked.

---

## 2. Proposition 1 — the engagement condition is exact

> The gate alters an escalation burst **iff `B > b`.**

Immediate from the model: if `B <= b` then `A_pace(0) = B = A_none(0)`, so the
admitted process is identical at every `t` and the gate is a no-op — not
approximately, identically.

**This is the structural null, generalised.** It was found empirically as
*"E3/pace is bit-identical to E3/none to four decimals in all four
conditions"*. It is not a fact about E3, or about four conditions, or about 480
runs. Against the ladder:

| rung | bytes | `> b = 65,536`? | gate engages |
|---|---|---|---|
| E1 | 512 | no | **no-op** |
| E2 | 3,584 | no | **no-op** |
| E2′ | 14,400 | no | **no-op** |
| E3 | 57,344 | no | **no-op** |
| E4 | 138,000 | **yes** | engages on 72,464 B |

> **Admission control cannot act on a payload smaller than the bucket it was
> sized for.** The inherited parameters were set for a continuous 2 Hz camera
> stream; an escalation burst is a different object, and four of the five rungs
> fall entirely inside the bucket. No sample size can change this, and neither
> can a reviewer's preferred configuration — only `b` can.

---

## 3. Proposition 2 — the sign is never favourable

> Under (A1) and (A2), pacing **weakly increases** the burst's completion time,
> for every `(b, r)`. It can never reduce it.

`A_pace(t) <= A_none(t)` for all `t >= 0`, by inspection of §1. For a
work-conserving, non-anticipative server, the cumulative departure process is
monotone in the cumulative arrival process: making work available *later* can
never make it depart *earlier*. Hence `D_pace(t) <= D_none(t)` for all `t`, and
with `T = inf{t : D(t) = B}`,

```
    T_pace  >=  T_none
```

Under **C2′** the server verifies before dispatching, so the decision waits on
`T`, and C3 measures that `T` dominates the alert's arrival at E3 and above.
Therefore

> **pacing the verification payload can never speed the dispatch decision, at
> any bucket depth and any fill rate.**

This is the proposition that answers *retune it*. It is a statement about the
class of mechanisms, not about a configuration.

**Cross-traffic does not rescue it.** With other flows present, pacing yields
service to them — which delays the burst further, not less. A fair scheduler
reduces the paced burst's share precisely because it has less queued.

**A coverage outage does not rescue it either.** When capacity returns, the
unpaced burst has all `B` bytes ready; the paced one has only
`min(B, b + r*t)`. So pacing is worse there too — measured at +0.208 s, the
smallest penalty of the four conditions but still positive.

---

## 4. Proposition 3 — the magnitude is bounded, not equal

> `0 <= penalty <= (B - b) / r`.

The last byte is admitted at `t = (B - b)/r`, so the burst cannot complete later
than that plus whatever the unpaced burst's own transit took — giving the bound.
It is **not an equality**, because tokens refill *while the first `b` bytes are
in flight*: pacing delay overlaps radio transit rather than adding to it.

Checked against the measurement at `(b = 64 KiB, r = 1 Mbps)`, where the bound
is `(138,000 − 65,536)/125,000 = 0.5797 s`:

| condition | E4 gap, none | E4 gap, pace | penalty | fraction of bound |
|---|---|---|---|---|
| CondHealthy | 0.2330 | 0.5850 | 0.3520 | **61 %** |
| CondCongested | 0.6705 | 0.9440 | 0.2735 | **47 %** |
| CondTransient | 0.7630 | 1.0270 | 0.2640 | **46 %** |
| CondOutage | 1.8700 | 2.0780 | 0.2080 | **36 %** |

All four inside `[0, 0.5797]`. **Had I quoted the formula as an equality I would
have overstated the harm by 1.6–2.8×** — which is why it is written as a bound.

### Corollary — the realised fraction falls as the link degrades

61 % → 47 % → 46 % → 36 %, monotone in condition severity. That is the overlap
mechanism showing itself: the slower the radio, the more of the pacing delay
hides behind transit that was going to happen anyway. It also explains C4.1's
most counter-intuitive measurement — **the penalty is largest where the link is
healthiest** — which was reported as an empirical curiosity and is in fact
forced by the same argument. Where the radio is the bottleneck, the gate is not.

---

## 4b. Proposition 4 — staleness discard cannot fire either

> Evidence-side staleness discard fires **iff** `cameraMaxAge < (B − b) / r`.

The oldest chunk in the burst is the last one admitted, at `t = (B−b)/r` after
the escalation. If `cameraMaxAge` exceeds that, no chunk ever reaches the age
threshold and the policy is a no-op; if it is below, only the tail past
`cameraMaxAge` is discarded.

At the inherited gate — `B = 138,000`, `b = 65,536`, `r = 1 Mbps` — the drain is
**0.5797 s** against a `cameraMaxAge` of **2 s**. So the third inherited
parameter **cannot fire at all.** Measured, CondCongested seed 3, 792 chunks:

| `cameraMaxAge` | stale-dropped | received |
|---|---|---|
| 0.5 s | 64 | 719 |
| 2 s | **0** | 785 |
| 8 s | **0** | 785 |

0.5 s is below the drain and clips the tail; 2 s and 8 s are above it and do
nothing — exactly as derived.

> **All three inherited gate parameters provably do nothing useful on evidence
> traffic.** The bucket cannot act on four of five rungs (Prop 1); pacing can
> only add delay and buys no completeness (Props 2–3); staleness cannot reach
> its threshold (Prop 4). The gate was tuned for a continuous 2 Hz camera
> stream, and an escalation burst is a different object in all three respects.

**This proposition exists because the measurement was wrong first.** C4.2
previously reported that `dropPace` delivered 45–47 % of the evidence. That was
an artefact of an unset arrival timestamp (`PHASE2_RESULT.md` §4); the true
behaviour is the no-op above. The lesson is the one Prop 1 already taught in a
milder form: **derive what the mechanism can do before measuring what it did.**
A derivation would have predicted a no-op at 2 s and made the 45 % impossible to
believe.

---

## 5. The one escape, closed by measurement

Proposition 2 assumes **(A2)**, the same byte set. The escape it leaves open is
real and worth taking seriously: an unpaced burst might **overflow a buffer**
and lose chunks that a paced burst delivers. Then pacing would not be a pure
cost — it would buy *completeness* with *latency*, and C3's budget would decide
whether the trade is worth it. That would be a considerably more interesting
finding than "the rule inverts".

It does not happen. Delivered fraction, `received_evidence /
evidenceChunksEmitted`, per seed, at E4:

| condition | none | **pace** | dropPace | pace vs none, per-seed |
|---|---|---|---|---|
| CondHealthy | 100.0 % | 99.6 % | 47.5 % | +3 / **−9** |
| CondCongested | 99.6 % | 99.3 % | 47.2 % | +8 / **−16** |
| CondTransient | 99.3 % | 99.0 % | 46.8 % | +7 / **−18** |
| CondOutage | 99.0 % | 99.0 % | 46.5 % | 9 / 9 |

Pacing is **equal or slightly worse** on completeness, never better, and the
per-seed sign counts favour *not* pacing in three of four conditions.

> **So pacing the verification payload is a Pareto loss**: strictly worse
> latency (§3, §4) with no completeness gain to pay for it. That is a stronger
> claim than "C4.1 inverts", and unlike the inversion it is half proof and half
> measurement rather than wholly measurement.

`dropPace` looked like the separate case — a real trade at a terrible exchange
rate, 46.5–47.5 % of the evidence for a 1.7–2.5× latency gain. **That is
withdrawn**: it was an artefact of an unset arrival timestamp, not a property of
staleness discard (`PHASE2_RESULT.md` §4). The derived replacement is §Prop 4.

---

## 6. What the sweep is for, and what it must find

The derivation covers the **sign** universally and the **magnitude** as a bound.
What it does not cover is where in `[0, (B−b)/r]` the penalty actually lands as
a function of `(b, r)` — and, more to the point, it does not *demonstrate* to a
reader that no configuration helps. `tools/gate_sweep.sh` searches the space.

Predictions, recorded **before** the run:

1. **`b = 256 KiB` gives a penalty of exactly 0**, in all four conditions, on
   every statistic, to four decimals — because `256 KiB > 138,000 B` and
   Proposition 1 makes it a no-op. **This is a positive control**: if it is not
   0, the derivation is wrong and the rest of the sweep is uninterpretable.
2. **No `(b, r)` yields a negative penalty.** Proposition 2 forbids it. A single
   significant negative refutes the derivation, and that is the point of running
   it.
3. **The penalty decreases monotonically in both `b` and `r`**, approaching 0 as
   `b → B` or `r → ∞`, and is bounded above by `(B−b)/r` at every cell.
4. **The realised fraction of the bound falls with condition severity** at every
   `(b, r)`, per §4's corollary.
5. For the `cameraMaxAge` sweep: **latency improves monotonically while
   completeness degrades monotonically**, so the two never agree — there is no
   setting at which dispatch latency is a safe score for a deferral policy.
   This is the generalisation of C4.2 from one `maxAge` to the axis.

---

## 7. What this does not settle

1. **Proposition 2 is about a token bucket**, i.e. the mechanism this system
   inherited. It does not prove that *no* admission mechanism can help. A
   mechanism that reorders rather than delays — sending the chunks most useful
   for verification first — is not covered and is not refuted. That is a real
   open direction, and it needs the detection model this project does not have
   (`PLAN_2026-11.md` §15).
2. **(A1) is a property of the radio**, asserted of Simu5G's scheduler rather
   than proved of it. HARQ retransmission and grant acquisition make the real
   uplink only approximately work-conserving. The measurement in §4 is the check
   that the approximation holds well enough; the 36–61 % spread is partly that.
3. **"Completeness" remains a byte fraction**, not a statement about whether a
   partial payload can verify — a detection question, out of scope
   (`PHASE2_RESULT.md` §5.1). The paper says "45 % of the bytes arrived".
4. **The ladder's sizes are themselves derived, not free.** Proposition 1's
   table is only as good as §7 of the plan; if E3's size changed, which rungs
   are no-ops would change with it.

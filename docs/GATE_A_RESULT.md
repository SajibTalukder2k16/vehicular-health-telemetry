# Gate A result: the burst does not delay the alert, and the reason matters

> **Sequel, 2026-11-10 — `docs/VERIFICATION_FRONTIER.md`.** C2's refutation left
> the question of what *does* govern the escalation. The answer came out of this
> same corpus at no extra compute: the server cannot dispatch until verification
> lands, verification costs 5–15× the alert, and the price is a modality step *(Withdrawn 2026-11-12: the gap is LINEAR in bytes, slope 0.95–1.21, R² ≥ 0.976 — the sublinear/modality reading was a per-run-max artefact. See `VERIFICATION_FRONTIER.md` §3.)*
> (waveform → image), not a volume budget. That is C2′ and C3, and it is why the
> result below reads as a relocation rather than a loss.

> ## CONFIRMED 2026-11-09 on the corrected model
>
> Everything below was measured on the pre-fix model, whose alert latencies
> were dominated by a missing Scheduling Request (§A.4 of the provenance
> register). The whole 600-run pilot was re-run after the fix
> (`patches/simu5g-scheduling-request.patch`, SR modelled at a sourced 5 ms
> periodicity, `retxBsrTimer` at its legal 320): corpus
> `simulations/pilot/results_escalation_sr/`, 600 of 600 completed, 535
> usable. **The conclusion is unchanged and the evidence is stronger.**
>
> **C2 is dead.** Zero of 16 arm-condition cells show the verification burst
> delaying the alert. Not one, on either statistic, under the worst policy
> for it.
>
> **The reverse effect survives the fix and resolves in more cells** —
> paired per-seed sign test on mean alert delay:
>
> | condition / arm | n | slower | faster | tied | sign p | median Δ |
> |---|---|---|---|---|---|---|
> | CondCongested / E3 | 30 | 6 | 20 | 4 | **0.0094** | −0.0898 s |
> | CondTransient / E4 | 30 | 7 | 20 | 3 | **0.0192** | −0.1872 s |
> | CondOutage / E3 | 27 | 5 | 18 | 4 | **0.0106** | **−0.7310 s** |
> | CondOutage / E4 | 27 | 6 | 17 | 4 | **0.0347** | −0.2300 s |
>
> Four resolvable cells, every one negative. That the direction survives a
> model fix which moved absolute latencies substantially is the strongest
> evidence available that it is a property of the system and not of a timer.
>
> **And the mechanism is now visible as a division of cost**, which is a
> better result than the one the pilot set out to find. Mean end-to-end delay
> by traffic class, same runs:
>
> | condition | arm | ALERT | EVIDENCE | ratio |
> |---|---|---|---|---|
> | CondHealthy | E4 | 0.0276 | 0.1596 | 5.78 |
> | CondCongested | E4 | 0.2729 | 0.7896 | 2.89 |
> | CondTransient | E4 | 0.3472 | 1.0248 | 2.95 |
> | CondOutage | E4 | 2.0481 | 5.0097 | 2.45 |
>
> The ratio rises monotonically with evidence volume in all four conditions
> (CondHealthy E1→E4: 0.99, 2.07, 3.42, 5.78). `escalate()` enqueues the
> alert ahead of its chunks, so **the burst absorbs the queueing its own
> volume creates while the alert does not pay it.** Tail prevalence agrees:
> alerts ≥ 0.5 s, CondHealthy 5.4% (ref) → 0.0% (E2–E4); CondCongested 24.8%
> → 11.2% at E3; CondOutage 56.5% → 43.1% at E3.
>
> **One honest gap.** The 1 s mechanism is fixed and gone, so the residual
> 0.09–0.73 s benefit has a *different* cause which is not yet identified.
> Aggregate UE RLC uplink delay cannot isolate it — that statistic pools the
> evidence chunks' own queueing and is accordingly *higher* in the evidence
> arms (CondOutage 2.97 s ref vs 3.66 s E4), which is itself consistent with
> the burst paying. Attributing the alert's own wait needs per-packet
> instrumentation the rig does not yet have. The effect is measured; its
> remaining mechanism is not explained, and the paper must not assert one.
>
> **Also corrected by the fix:** CondOutage absolute latencies got *worse*
> (ref 2.2693 → 3.3618 s), as they should — in a coverage hole the SR path
> cannot help and the backstop now sits at the legal 320 rather than the
> illegal 40.


Date: 2026-11-08. Corpus: `simulations/pilot/results_escalation/`, 600 runs
(4 conditions x {ref,E1,E2,E3,E4} x 30 seeds), policy `none`,
`cameraTerminatesAtEdge=true`. Analyzer: `tools/analyze_escalation.py`.

## Verdict

**C2 as written does not survive, and the pilot found the opposite sign.**

Zero of 16 arm-condition cells show the verification burst *delaying* the
alert. Two cells show it *accelerating* the alert at p < 0.05 on an exact
two-sided sign test (CondCongested/E3 p = 0.004, CondTransient/E4 p = 0.013),
and the acceleration is concentrated where evidence volume is largest.

This is not a null result. It is a mechanism running the other way.

## The mechanism, traced packet by packet

Diagnostic cell: CondHealthy, seed 3, with the channel made deterministic
(`fading=false shadowing=false dynamicLos=false pduErrorRate=0`) so that the
two arms share one radio realization. Both arms generate the same two alarms
at the same instants; the second is generated at t = 132.2731 s in both.

| | ref (no evidence) | E4 (138 kB evidence) |
|---|---|---|
| UE PDCP accepts the alarm | t = 132.274124 | t = 132.274124 |
| eNB receives it off the radio | t = **133.283** | t = **132.289** |
| alarm e2e delay | **1.009952 s** | **0.015952 s** |
| `rlcDelayUl` for that SDU | **1.008876 s** | 0.0146 (next SDU) |
| `macDelayUl` | 0.004 s | 0.004 s |

The 1.009 s is spent entirely in the **UE's RLC uplink buffer waiting for a
grant**. MAC transfer is 4 ms in both arms, and the eNB's `pppIf` first sees
the packet at 133.283, so the time is not backhaul and not server-side.

In the E4 arm, PDCP accepts the alarm *and all 99 evidence chunks at the same
instant*. `escalate()` queues the alert first, so the alert leaves on the
grant that the burst's buffer-status report provokes. **The burst pays for the
alert's grant.** A 156-byte alert on its own is too small to get the UE
scheduled promptly; arriving at the head of a 138 kB burst, it is.

Alert delay is therefore bimodal, not noisy: each alert either leaves in
~16 ms or waits ~1 s, and uplink backlog is what selects the fast mode.

## Why the CI-based table in the analyzer is not the thing to quote

The analyzer's `1.96*sd/sqrt(n)` starred four cells. Those stars are
artifacts. The per-seed paired differences are zero-inflated with rare
one-second excursions -- CondHealthy/E1, with `ev_rx = 1` (a single extra
512-byte packet in a 320 s run), produced per-seed deltas of +1.472, +1.296,
+0.664, -0.288, -0.1998 with twelve of twenty seeds at exactly 0.000. A normal
approximation is anti-conservative on that shape. The sign test is the
statistic to report; it agrees with the mechanism and starred nothing in the
C2 direction.

This also retires an earlier suspicion of mine recorded during the analysis:
the arms do *not* merely differ by a re-drawn channel. With fading, shadowing,
dynamic LoS and PDU errors all disabled the 1.009 s / 0.016 s split reproduces
exactly, so it is structural. The ini's own caveat at lines 30-32 ("the
channel still differs between policies because transmissions differ") is true
but is **not** what produced this result.

## RESOLVED 2026-11-08: the 1 s is a missing PUCCH, and the effect survives

The blocking question below was answered the same day. Full write-up in
`docs/PARAMETER_PROVENANCE.md` §A.4; summary and consequences here.

**Root cause.** Simu5G models **no PUCCH and no Scheduling Request** —
`grep -rn "srProhibit\|SchedulingRequest" src/` returns nothing, and PUCCH
appears only in `LteAirFrame.msg`. Grant re-acquisition is contention RACH →
BSR → grant, and `LteMacUe.cc:516-517` blocks a RAC retry for the whole
`retxBsrTimer` after each BSR ("this prevents the UE from sending an
unnecessary RAC request"), with `checkRAC()` at line 850 decrementing it and
returning. A UE whose BSR goes ungranted therefore waits the full timer.

**The default was illegal and flattering.** `LteMacUe.ned:35` sets
`retxBsrTimer = default(40)`. Verified against the primary document — ETSI
TS 136 331 v19.4.0 clause 6.3.2, ASN.1 extracted from `ts_136331v190400p.pdf`
— `RetxBSR-Timer-r12` is `{sf320, sf640, sf1280, sf2560, sf5120, sf10240,
spare2, spare1}`, so **40 is illegal for this timer** (it is a legal
*periodic*-BSR value). Simu5G's own NR stack uses the legal minimum:
`NrMacUe.ned:27`, `retxBsrTimer = default(320)`. The whole earlier corpus ran
on the illegal, most optimistic value in the range.

**No timer value fixes the tail.** CondHealthy, ref arm, 30 seeds, fraction of
alerts with e2e delay >= 0.5 s: 11.1% at 40 (illegal), 17.1% at 320, 21.9% at
640, 25.7% at 2560. Monotone, as the mechanism predicts — one ungranted BSR
costs one full timer. An earlier single-seed sweep suggested 320 "fixed" it;
that was an alignment coincidence and is withdrawn.

**The Gate A effect strengthens under a standards-legal configuration.**
Re-ran ref vs E4, 30 seeds, `retxBsrTimer=320`. Paired per-seed sign test on
the fraction of alerts in the >= 0.5 s tail:

| configuration | condition | pairs | ref worse | E4 worse | tied | sign p |
|---|---|---|---|---|---|---|
| 320 (legal) | CondHealthy | 20 | 5 | **0** | 15 | 0.0625 |
| 320 (legal) | CondCongested | 30 | 14 | 2 | 14 | **0.0042** |
| 40 (illegal default) | CondHealthy | 20 | 4 | 0 | 16 | 0.125 |
| 40 (illegal default) | CondCongested | 30 | 12 | 5 | 13 | 0.144 |

Absolute tail prevalence at 320: CondHealthy 17.1% (ref) vs **0.0%** (E4);
CondCongested 30.4% vs 15.3%. So the effect is *marginal at the illegal
default and resolvable once the configuration is legal* — the bad default was
suppressing it, not manufacturing it.

Tail prevalence is the statistic to report, not per-run mean alert delay: a run
yields ~2 alarms, so a mean over them is dominated by single events, which is
what produced the uninterpretable CI table in the first place.

### What may and may not be claimed

- **May:** the mechanism and its direction. A sporadic small alert must
  re-acquire an uplink grant; the verification burst it triggers removes that
  cost by keeping the buffer backlogged. Evidence is not the alert's
  competitor — it is what gets the alert scheduled. This is a design rule.
- **May not:** the magnitude, as a statement about real networks. The
  re-acquisition cost here is floored at 320 ms by a missing PUCCH/SR path; a
  real UE raises an SR and is granted in roughly 5-10 ms. The mechanism is
  real, the magnitude is a property of this model, and the paper must say so.
- **May not:** absolute alert latency, or any deadline scored against it — the
  unsourced 5 s alarm budget included. Arm-to-arm contrasts remain usable
  because the path is common to all arms, stated with the limitation.

### The superseded open question, kept for the record

## The open question this creates, and it is load-bearing

**One second to acquire an uplink grant is not LTE/NR-realistic, and it is not
consistent with Simu5G's own defaults.** `LteMacUe.ned` bounds the RACH
procedure at `maxRacAttempts=10` x (`raResponseWindow=3` + `racBackoffMax=20`)
TTIs ~= 230 ms, and sets `retxBsrTimer=40` TTIs = 40 ms. Nothing there reaches
1009 TTIs. The cell is also nearly idle: `avgServedBlocksUl:mean` = 0.0031 in
ref and 0.0226 in E4.

So the 1 s is either (a) a Simu5G uplink-scheduling pathology for a sporadic
small-packet UE, or (b) a gap in `simulations/pilot/omnetpp.ini`, which sets no
uplink scheduling discipline and leaves the SR/BSR configuration at defaults.

Until that is resolved, **every absolute alert-latency number in this project
is suspect**, including those in the earlier 19,090-run corpus, because they
all ride on the same grant-acquisition path. The *contrasts* between arms are
less exposed, since the path is common to them, but the alert-deadline results
specifically are not: a 5 s budget scored against a latency whose dominant term
is an unexplained 1 s wait is not a measurement of anything.

This must be settled before any alert-latency claim is written.

## Consequences for the paper

1. C2 ("the evidence that justifies the alert is what delays it") is
   **withdrawn** in its current form. It was built on the continuous 2 Hz
   camera-stream corpus that C1 invalidated, and under the derived
   burst architecture the sign reverses.
2. There is a candidate replacement contribution, stronger because it is
   counter-intuitive and mechanistic: *under a derived edge partition the
   alert is too small to be scheduled promptly on its own, so the
   verification burst it triggers is what gets it out.* That makes the
   evidence payload part of the alerting path rather than its competitor,
   and it is a design rule, not a tuning result.
3. That replacement is **now claimable in mechanism and direction, but not in
   magnitude.** Resolved 2026-11-08: the 1 s is real within the model and
   fully explained (no PUCCH/SR; grant re-acquisition gated by a timer whose
   3GPP-legal floor is 320 ms), and the effect *strengthens* when the
   configuration is made standards-legal rather than vanishing. What cannot
   be carried into a claim about real networks is the size of the effect,
   because a real UE's SR round trip is ~5-10 ms, not >= 320 ms. See the
   resolution section above for exactly what may and may not be said.
4. Phase 2 as planned (sweep evidence volume x deferral policy for a
   verification-budget frontier) is **not spent yet**. A frontier trading
   alert timeliness against evidence volume presumes a trade-off whose sign
   is now in doubt.

## Provenance

- Pilot: commit `c59781664`; model changes `10cbcbfd6`.
- The 1 s is reproducible: `CondHealthy`, seed-set 3, deterministic channel,
  `evidenceBytes` 0 vs 138000.
- Statistics: exact two-sided sign test on paired per-seed differences,
  intersected to seeds usable in both arms. 66 of 600 runs were unusable
  because no alert was delivered, which confirms the thin-denominator risk the
  pilot script recorded in advance (~2 alarms per drive at exponential(300 s)).

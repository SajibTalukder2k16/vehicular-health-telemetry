# C4 confirmed: no gate configuration helps, and the optimum is to not exist

**2,160 runs, 2026-11-12/13.** `results_gate/`, verified extract in
`analysis/gate/`. Eighteen arms × four conditions × 30 seeds, with an
**internal `policy=none` baseline** so every contrast is within one corpus at
matched seeds.

This sweep exists to try to **break** `GATE_DERIVATION.md`, not to illustrate
it. C4 used to rest on one inherited gate configuration, which invites the
obvious reply — *you chose bad parameters*. A derivation has none to choose, so
the derivation came first and this sweep searched the space a reviewer would
propose.

**All four propositions survive.** Predictions were recorded in
`tools/gate_sweep.sh` and `tools/gate_dp_rerun.sh` before their runs.

---

## 1. The positive control passes, which makes the rest readable

`b = 256 KiB` exceeds the E4 burst of 138,000 B, so Proposition 1 says the gate
**cannot engage** and the penalty must be *exactly* zero. It is — `0.0000` in
all twelve cells (4 conditions × 3 fill rates), on every statistic.

That is the cell that licenses the others: had it been non-zero, the derivation
would be wrong and nothing else here would be interpretable.

| verdict | result |
|---|---|
| **P1** — `b > B` ⇒ penalty exactly 0 | **PASS** |
| **P2** — no significant *negative* penalty at any `(b, r)` | **PASS** |
| **P3** — `penalty ≤ (B−b)/r` in every cell | **PASS** |
| **P5** — pacing never improves completeness | **PASS** |

---

## 2. Result: the gate's best achievable outcome is zero harm

Pacing penalty, `gap(pace) − gap(none)`, per-seed median, paired on seed
(`*` = p < 0.05, exact two-sided sign test):

| bucket | rate | bound `(B−b)/r` | Healthy | Congested | Transient | Outage |
|---|---|---|---|---|---|---|
| 16 KiB | 1 Mbps | 0.9729 | +0.8082\* | +0.5362\* | +0.5430\* | +0.4240\* |
| 16 KiB | 4 Mbps | 0.2432 | +0.1200\* | +0.0247 | +0.0750 | +0.0000 |
| 16 KiB | 16 Mbps | 0.0608 | +0.0132 | +0.0077 | +0.0000 | +0.0000 |
| **64 KiB** | **1 Mbps** | **0.5797** | **+0.4442\*** | +0.2535 | +0.3038 | +0.0010 |
| 64 KiB | 4 Mbps | 0.1449 | +0.0060 | +0.0052 | +0.0065 | +0.0000 |
| 64 KiB | 16 Mbps | 0.0362 | +0.0027 | +0.0000 | +0.0000 | +0.0000 |
| 128 KiB | any | ≤0.0554 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| 256 KiB | any | 0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

**Every entry is ≥ 0.** Across 48 cells and a 16× range of bucket depth and
fill rate, the gate never once made the decision faster.

> **The best configuration is the one that disengages.** Penalty falls
> monotonically toward zero as `b → B` or `r → ∞`, and reaches zero exactly
> when the gate stops acting. A mechanism whose optimum is its own absence is
> not a tuning problem.

The row that matters for the inherited system is **64 KiB / 1 Mbps**: a
**0.44 s** penalty in CondHealthy, significant, for nothing in return.

---

## 3. Result: the realised fraction of the bound falls as the link degrades

Penalty as a percentage of `(B−b)/r`:

| bucket | rate | Healthy | Congested | Transient | Outage |
|---|---|---|---|---|---|
| 16 KiB | 1 Mbps | **83 %** | 55 % | 56 % | 44 % |
| 64 KiB | 1 Mbps | **77 %** | 44 % | 52 % | 0 % |
| 16 KiB | 4 Mbps | 49 % | 10 % | 31 % | 0 % |
| 64 KiB | 4 Mbps | 4 % | 4 % | 4 % | 0 % |

Monotone decreasing with condition severity, as `GATE_DERIVATION.md` §4's
corollary predicts: the slower the radio, the more of the pacing delay hides
behind transit that was going to happen anyway. **This is why the penalty is
largest where the link is healthiest** — reported in Phase 2 as an empirical
curiosity, and forced by the derivation.

---

## 4. Result: Proposition 4 — staleness cannot fire either

> Staleness discard fires **iff** `cameraMaxAge < (B−b)/r`. At the inherited
> gate that drain is **0.5797 s** against a `cameraMaxAge` of **2 s**.

Median dispatch, delivered fraction, and stale-drops per run:

| condition | `none` | 0.5 s | 1 s | 2 s | 4 s | 8 s |
|---|---|---|---|---|---|---|
| **Healthy** gap | 0.2260 | 0.5203 | 0.5875 | 0.5875 | 0.5875 | 0.5875 |
| delivered | 100.0 % | 91.8 % | 99.6 % | 99.6 % | 99.6 % | 99.6 % |
| stale-dropped | 0 | 8 | **0** | **0** | **0** | **0** |
| **Congested** gap | 0.6975 | 0.8105 | 0.9605 | 0.9605 | 0.9605 | 0.9605 |
| delivered | 99.6 % | 91.3 % | 99.3 % | 99.3 % | 99.3 % | 99.3 % |
| **Transient** gap | 0.8253 | 1.0325 | 1.1465 | 1.1465 | 1.1465 | 1.1465 |
| delivered | 99.3 % | 90.7 % | 99.0 % | 99.0 % | 99.0 % | 99.0 % |
| **Outage** gap | 2.3790 | 2.3260 | 1.9255 | 1.9255 | 1.9255 | 1.9255 |
| delivered | 99.0 % | 90.9 % | 99.0 % | 99.0 % | 99.0 % | 99.0 % |

**At every `maxAge ≥ 1 s` the discard never fires**: zero drops, delivery equal
to `none`, and all four columns identical — because the threshold is above the
drain. Only 0.5 s, which is *below* 0.5797 s, clips the tail.

Two consequences:

1. **The inherited `cameraMaxAge = 2 s` is a structural no-op.** With the bucket
   (Prop 1) and pacing (Props 2–3), **all three inherited gate parameters
   provably do nothing useful on evidence traffic.**
2. **`dropPace` is therefore just `pace`**, and inherits its Pareto loss: in
   CondHealthy the gap is **0.2260 → 0.5875 s, 2.6× worse** than doing nothing.

### The trap survives, an order of magnitude weaker

Only at `maxAge = 0.5 s` does the policy actually trade: CondHealthy gives up
**8.2 %** of the evidence to save **0.067 s** (11 %) of gap. That is the trap's
direction — latency improves while completeness degrades — but at 8 %, not the
**45–47 %** C4.2 reported. That figure was an artefact of an unset arrival
timestamp (`PHASE2_RESULT.md` §4) and is withdrawn.

**The methodological warning stands, and now has two independent
demonstrations.** Score a deferral policy on verification completeness, never on
dispatch latency. This project was fooled twice: once by a counter scoped to the
wrong class, once by a dead timestamp. Both times the latency metric looked fine.

---

## 5. What this does to C4

C4 is no longer a policy comparison conditional on a configuration. It is:

> **Under an architecture whose server verifies before dispatching, a
> token-bucket gate in front of the verification payload cannot help.** It
> cannot act below its bucket depth (P1); it can only add delay, by work
> conservation (P2), bounded by `(B−b)/r` (P3) and buying no completeness (P5);
> and its staleness horizon cannot be reached unless set below the drain time
> (P4). Searched across 16× in bucket depth, 16× in fill rate and 16× in
> staleness horizon — 2,160 runs — the gate's best outcome is **exactly zero
> harm**, achieved by disengaging.

With C3's linearity, the two results compose into a single design statement:
**the dispatch cost is proportional to evidence bytes, and you cannot schedule
your way around it. The only lever is sending fewer bytes.**

---

## 6. What is not solid here

1. **Proposition 2 is about a token bucket** — the mechanism this system
   inherited. A mechanism that *reorders* rather than delays, sending the chunks
   most useful for verification first, is not covered and is not refuted. It
   needs the detection model this project does not have.
2. **(A1), work conservation, is asserted of Simu5G's scheduler**, not proved of
   it. HARQ and grant acquisition make the real uplink only approximately
   work-conserving; the spread in §3 is partly that. ⚠ **This line read
   "the 36–83 % spread in §3" until 2026-11-16, which mixed two corpora:**
   §3's own table runs **0–83 %** (nonzero minimum 4 %), and the 36 % is the
   Phase-2 minimum from `GATE_DERIVATION.md` §4. Quote one range or the other,
   never a hybrid. The paper states both, each attributed to its corpus.
3. **Only E4 engages the gate at all**, so §2 measures one burst size. That is
   derived (P1), not assumed — but a different ladder would move which rungs
   engage.
4. **CondOutage is the weakest cell everywhere**: 27 paired seeds, the largest
   spread, and the only place the penalty reads 0.0000 at 1 Mbps.
5. **Completeness remains a byte fraction**, not a statement about whether a
   partial payload can verify.

---

## 7. Provenance

```sh
python3 -I tools/gate_contrasts.py        # reproduces every table above
```

**Two input paths, verified identical (2026-11-16).** Until that date this tool
read *only* the raw 3.4 GB `results_gate/`, which is gitignored and not
redistributed — so C4's tables were the one part of the paper a reader could
not regenerate, while the paper claimed otherwise. The tool now defaults to the
committed extract in `analysis/gate/` and falls back to the corpus:

```sh
python3 -I tools/gate_contrasts.py                              # extract, 11 s
python3 -I tools/gate_contrasts.py simulations/pilot/results_gate  # corpus, 13 s
diff <(...) <(...)   # identical apart from the corpus path on line 1
```

**The assumption the propositions make and did not state.** All four assume the
bucket is **full when the burst arrives**. Checked against this corpus: the
shortest interval between consecutive escalations, over all 6,997, is
**1.1860 s**, against a refill time `b/r` of 0.1311–1.0486 s for eleven of the
twelve swept configurations. The twelfth (256 KiB at 1 Mbps) refills in
2.0972 s and *can* be caught partly empty — but at minimum spacing it still
holds 148,250 B > the 138,000 B burst, so Prop 1's conclusion is unaffected,
and that cell measures exactly 0.

The scalar extract is verified value-by-value against the 3.4 GB corpus:

```
OK: 12192061 values match exactly; 174960 histograms sum to their recorded count
```

The 600 `dropPace` runs were re-run after the staleness fix
(`tools/gate_dp_rerun.sh`); the 1,560 `pace` and `none` runs were not, and did
not need to be — `POLICY_PACE` never reaches a staleness branch.

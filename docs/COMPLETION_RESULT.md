# Readiness under a full-evidence policy — the metric was wrong, and it matters

**2026-11-16.** Raised by an external review of v06, verified, and confirmed.
No new compute: this is a re-analysis of the 600-run Gate A corpus
(`analysis/escalation_vec/`) with `tools/completion.py`.

---

## 1. The defect

Every dispatch figure this project has published is the **maximum end-to-end
delay over the chunks of a burst that arrived**. Under the response policy the
paper models — the server verifies before dispatching — that is not readiness.
If one chunk never arrives, the receiver never has what the policy requires,
and a maximum over the survivors is a number about a burst that was never
ready.

The reviewer's phrasing is exact: *"arrival of the last received chunk
establishes readiness only if every required chunk arrived."*

**We also reported completeness as a byte fraction of 99.0–99.6 %**, which is
true and, for this policy, misleading. A burst at E4 is 99 chunks. Losing 1 %
of chunks spread across bursts leaves most *bursts* incomplete while leaving
99 % of *bytes* delivered. The two numbers answer different questions and the
paper quoted the flattering one.

---

## 2. The classification

Expected chunks per burst, read off the corpus as the modal count per rung and
consistent with each rung's byte size: **E1 = 1, E2 = 3, E3 = 41, E4 = 99.**

| class | test | meaning |
|---|---|---|
| **complete** | every expected chunk arrived | readiness is defined |
| **censored** | incomplete **and** `creation + T_obs > horizon` | not observed long enough to complete; outcome unresolved |
| **lost** | incomplete and observed past `T_obs` | the chunks are genuinely missing |

`T_obs` is the slowest observed completion among **complete** escalations in
the same cell; horizons are the per-condition `sim-time-limit` (320 / 1369 /
1369 / 680 s).

> ⚠ **CORRECTED 2026-11-17, second external review.** The first rule censored
> any incomplete burst that was merely the **last** escalation of its run.
> Being last does not mean the horizon interrupted it — a final escalation can
> fall well before the end and lose packets outright — and the rule inflated
> completion badly where runs carry few escalations. CondHealthy averages ~1.2
> escalations per run, so "last" was usually the *only* one. **E4 completion
> falls from 88.6 / 78.5 / 79.1 / 68.5 % to 83.8 / 73.6 / 74.5 / 51.4 %.**
> Censoring nearly vanishes: almost every incomplete burst is genuine loss.
>
> Because the rule only relabels **incomplete** escalations, every latency
> statistic conditioned on completion is unchanged.

---

## 3. Result: a large minority of escalations never become ready

Completion rate = complete / (complete + lost); censored excluded.

| rung | Healthy | Congested | Transient | Outage |
|---|---|---|---|---|
| E1 (512 B) | 100.0 % | 100.0 % | 100.0 % | 100.0 % |
| E2 (3.5 KiB) | 94.3 % | 90.9 % | 90.6 % | 87.5 % |
| E3 (56 KiB) | 81.1 % | 79.9 % | 86.3 % | 61.1 % |
| **E4 (138 kB)** | **83.8 %** | **73.6 %** | **74.5 %** | **51.4 %** |

Note the decline is not monotone everywhere: Healthy reads 81.1 % at E3 and
83.8 % at E4, a difference well inside what 37 escalations resolve.

> **At E4, between 16 % and 49 % of escalations did not become ready within
> the observation window.** In a coverage outage, close to half. This is a larger consequence of
> evidence volume than the dispatch gap, and the paper does not currently
> report it.

It also makes the paper's design rule *more* strongly supported, not less: the
cost of sending more evidence is not only that the decision comes later, but
that for a growing fraction of escalations it cannot be made at all.

---

## 4. Result: the published gap figures were a mixture

Median gap, as published (max over *received* chunks, all escalations) against
the same statistic among **complete escalations only**:

| condition | rung | published | complete-only | change |
|---|---|---|---|---|
| Healthy | E3 | 0.1280 | 0.0880 | −31 % |
| | E4 | 0.2330 | 0.1920 | −18 % |
| Congested | E3 | 0.2590 | 0.2240 | −14 % |
| | E4 | 0.6705 | 0.4575 | −32 % |
| Transient | E3 | 0.3270 | 0.1740 | −47 % |
| | E4 | 0.7630 | 0.3665 | −52 % |
| Outage | E3 | 1.1110 | 0.3625 | −67 % |
| | **E4** | **1.8700** | **0.4020** | **−79 %** |

**The direction is the opposite of the intuitive one, and the reason matters.**
Conditioning on completion *removes the slow bursts* — a burst that lost chunks
was usually a burst having a bad time on the radio. So the complete-only figure
is **survivorship-biased and optimistic**, and must be labelled conditional
wherever it appears.

Neither number is the honest headline on its own:

- the published figure is a median over a mixture in which incomplete bursts
  contributed an understated value;
- the complete-only figure excludes exactly the worst cases.

**Report both, plus the completion rate.** That is what §3 and §4 together are.

---

## 5. What survives

**C3's linearity survives.** Log–log fit of the complete-only median gap on
evidence bytes over E2/E3/E4:

| condition | slope | R² |
|---|---|---|
| CondHealthy | 1.16 | 0.997 |
| CondCongested | 0.89 | 1.000 |
| CondTransient | 0.87 | 1.000 |
| CondOutage | 0.81 | 0.961 |

Slopes 0.81–1.16 against the published 0.95–1.21. Proportionality holds; the
range widens downward. **Three payload sizes cannot exclude a knee**, which the
reviewer also said and which the paper should concede — the supportable claim
is proportionality over the sizes tested.

**C2′ survives in direction, not in magnitude.** The gap still grows by orders
of magnitude over the ladder; the CondOutage endpoint is 0.40 s conditional on
completion, not 1.87 s.

---

## 5a. The gate corpus: `maxAge = 0.5 s` completes **nothing**

Run on the 2,160-run gate corpus (`--expect 99`, every arm is at E4). First,
the consistency check that licenses the rest: the gate corpus's internal
`policy=none` baseline reproduces the Gate A completion rates **exactly** —
88.6 / 78.5 / 79.1 / 68.5 % — from an independently generated corpus.

Then the cell the review singled out as most sensitive to the definition:

| arm | Healthy | Congested | Transient | Outage |
|---|---|---|---|---|
| `none` | 88.6 % | 78.5 % | 79.1 % | 68.5 % |
| `maxAge = 0.5 s` | **0.0 %** | **0.0 %** | **0.0 %** | **0.0 %** |
| `maxAge ≥ 1 s` | 100 % | 100 % | 98.6 % | 100 % |

> **Not one of the 393 escalations at `maxAge = 0.5 s` ever delivers a
> complete burst.** The largest burst that arrives anywhere in that arm is
> **91 chunks of the 99 required**; the modal burst is 91. Zero reach 99.

**The paper currently describes this cell as "gives up 8.2 % of the evidence
to save 0.067 s (11 %) of gap."** That 8.2 % is a byte fraction. In the terms
the modelled policy actually uses it is **100 % failure**: every burst is
missing chunks, so no burst is ever verifiable, and the 0.067 s "saving" is a
median over bursts that never became ready.

This does not weaken the paper's methodological warning. It is the sharpest
possible demonstration of it:

> Score a deferral policy on verification completeness, never on dispatch
> latency. Here the latency metric reported an 11 % improvement while the
> policy was destroying the evidence for **every single escalation**.

Note also that `maxAge ≥ 1 s` completes at 98.6–100 %, *better* than `none`
at 68.5–88.6 %. That is not the gate helping: those arms pace the burst, which
spreads it over a longer window and changes what the horizon truncates. It
needs the same care as any other conditional figure and is not a completeness
gain to claim.

---

## 6. What this obliges the paper to change

1. Report the **completion rate** as a primary result, per rung and condition.
2. Restate every gap figure as **conditional on completion**, and say so.
3. Replace byte-fraction completeness with **burst completion**, or report both
   and name which is which.
4. **Restate C4's 8.2 % trade** at `maxAge = 0.5 s`: under a full-evidence
   policy it is not an 8.2 % cost for an 11 % gain, it is **total loss of
   verifiable evidence** (§5a). Done.
5. Concede that **three sizes cannot exclude a knee.**

All five are restatements of measured results; no new simulation is needed.

---

## 7. Provenance

```sh
python3 -I tools/completion.py                      # Gate A, section 3-5
python3 -I tools/completion.py --expect 99 analysis/gate/escalation_latencies.csv.gz
```

`--expect` is needed for the gate corpus because its arms are named by policy
rather than by rung, and every arm runs at E4.

**One bug found in this tool and fixed before any number above was believed.**
The first `--expect` implementation mutated a module global into a
`defaultdict` and read it with `.get()`, which does not fire the factory — so
every burst read as complete and the tool reported a uniform 100 %. The tell
was that the number was too clean. The second attempt still disagreed with a
direct count on the `none` arm. `classify()` now takes the expected count as
an argument, and its output is checked against both an independent
implementation and the Gate A corpus.

Expected chunk counts are printed by the tool and can be checked against the
modal received count per rung.

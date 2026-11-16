# The verification frontier — C3, from the Gate A corpus

**Computed 2026-11-10 from `simulations/pilot/results_escalation_sr` (600 runs,
the SR-corrected model). No new compute was spent.** The frontier Phase 2 was
scheduled to measure was already latent in the Gate A corpus; this document is
that measurement, with its limits stated before its numbers.

Companion: `GATE_A_RESULT.md` (why C2 was withdrawn), `PLAN_2026-11.md` §7 (the
evidence ladder), `PARAMETER_PROVENANCE.md` §A.4 (the SR patch).

---

## 1. Why this is the right quantity

Gate A asked whether the verification burst delays the **alert**. It does not
(0 of 16 cells; the sign reverses in 4). But the alert's arrival is not the
decision. The server **verifies before dispatching** — that is the system
requirement C2 was built on, and it survives C2's withdrawal intact. So the
decision-relevant latency is

> **time-to-dispatch = max(alert arrival, verification complete)**

measured from the escalation instant. Since the alert now always arrives far
sooner than the burst's slowest chunk, this is dominated by the evidence, and

    time-to-dispatch  ≈  max over the burst's chunks of their end-to-end delay

**RESOLVED 2026-11-10 — measured per escalation.** The first version of this
document could only use `e2eDelayEvidence:max`, the slowest chunk in a whole
run, because `**.vector-recording = false` meant the 600 `.vec` files held
vector declarations and zero samples. The ini now records the two escalation
latency vectors selectively (see the ordering warning at
`simulations/pilot/omnetpp.ini`, at the `vector-recording` block), and the
pilot was re-run:
`results_escalation_vec/`, 600 of 600. **The frontier below is now 37–143
escalations per cell instead of 30 per-run maxima**, and §2's per-run-max table
is kept only as the superseded first estimate — it overstated typical dispatch
delay by up to 40×, exactly as its own caveat warned.

> **A trap worth recording, because it produced a wrong table once.** Chunks
> group to their escalation by creation time, but an alert carries its **sensor**
> creation stamp from the rig while its chunks are stamped at the **edge**,
> after `uniform(0.5ms, 2ms)` of processing. The two differ by a measured median
> of **1.28 ms**. A 1 ms pairing tolerance leaves ~70 % of escalations unpaired
> and silently collapses dispatch onto the alert — erasing the entire effect
> while looking plausible. `tools/dispatch_times.py` defaults to 10 ms, carries
> the reasoning, ships a `--report-pairing` diagnostic, and warns that the
> tolerance must be raised if M4 re-sources edge processing to 40–300 ms.

---

## 2. The frontier, per escalation

`results_escalation_vec/`, all delays in seconds, medians over escalations.
`gap` is `dispatch − alert`: **how much later the decision can be made than the
alert arrives**, which is the quantity C2′ names. `over` is the fraction of
escalations exceeding the **4 s** eCall budget (ETSI TS 122 101 cl. A.27.2 —
`PARAMETER_PROVENANCE.md` §A.6), replacing the unsourced 5 s.

**CORRECTED 2026-11-11.** The table below replaces a version whose dispatch and
`gap` columns were each ~1.7 ms low. `dispatch_times.py` was comparing two
delays measured from *different* creation instants — an alert is stamped at the
rig, an evidence chunk at the edge — so the edge latency was charged to the
alert and credited to the evidence. See `EDGE_COST_RESULT.md` §1. At this
corpus's 1.28 ms edge the error is ≤1.3 ms and **no conclusion changes**; one
*ratio* does, because its denominator is the size of the correction (below).

| condition | arm | rung | esc. | alert | dispatch | p90 | worst | > 4 s | **gap** |
|---|---|---|---|---|---|---|---|---|---|
| CondHealthy | ref | none | 37 | 0.0161 | 0.0161 | 0.2322 | 1.0089 | 0.0% | 0.0000 |
| | E1 | 512 B | 34 | 0.0159 | 0.0162 | 0.2387 | 1.0089 | 0.0% | 0.0000 |
| | E2 | 3.5 KiB | 35 | 0.0160 | 0.0201 | 0.4647 | 1.0479 | 0.0% | 0.0040 |
| | E3 | 56 KiB | 37 | 0.0161 | 0.1444 | 0.7050 | 1.0789 | 0.0% | **0.1280** |
| | E4 | 138 kB | 37 | 0.0161 | 0.2569 | 1.2879 | 1.5571 | 0.0% | 0.2330 |
| CondCongested | ref | none | 141 | 0.0242 | 0.0242 | 1.3353 | 6.3836 | 1.4% | 0.0000 |
| | E1 | 512 B | 141 | 0.0175 | 0.0235 | 1.3638 | 6.3916 | 2.1% | 0.0010 |
| | E2 | 3.5 KiB | 139 | 0.0176 | 0.0516 | 1.3583 | 6.4376 | 0.7% | 0.0200 |
| | E3 | 56 KiB | 143 | 0.0201 | 0.3242 | 2.3607 | 7.5266 | 5.6% | **0.2590** |
| | E4 | 138 kB | 142 | 0.0207 | 0.7826 | 3.1271 | 10.3370 | 4.9% | 0.6705 |
| CondTransient | ref | none | 135 | 0.0319 | 0.0319 | 2.1674 | 13.5844 | 4.4% | 0.0000 |
| | E1 | 512 B | 134 | 0.0215 | 0.0300 | 1.8095 | 10.2522 | 5.2% | 0.0010 |
| | E2 | 3.5 KiB | 135 | 0.0220 | 0.0576 | 2.8967 | 14.6074 | 7.4% | 0.0170 |
| | E3 | 56 KiB | 141 | 0.0220 | 0.4155 | 5.3727 | 20.6892 | 15.6% | **0.3270** |
| | E4 | 138 kB | 139 | 0.0203 | 1.0291 | 6.4513 | 13.2162 | 17.3% | 0.7630 |
| CondOutage | ref | none | 69 | 1.0071 | 1.0071 | 8.5729 | 19.2024 | 29.0% | 0.0000 |
| | E1 | 512 B | 68 | 0.8285 | 0.8906 | 9.9667 | 20.1955 | 25.0% | 0.0035 |
| | E2 | 3.5 KiB | 70 | 0.4039 | 1.0439 | 12.8985 | 27.0211 | 34.3% | 0.0280 |
| | E3 | 56 KiB | 72 | 0.1376 | 1.6501 | 16.4370 | 27.4206 | 38.9% | **1.1110** |
| | E4 | 138 kB | 72 | 0.3704 | 2.2680 | 31.1385 | 71.7929 | 41.7% | 1.8700 |

Every `> 4 s` percentage is unchanged by the correction.

**The step is far sharper than the per-run-max estimate showed.** The gap
between the alert and the decision, E2 → E3:

| condition | E1 | E2 | E3 | E4 | **E2→E3 factor** |
|---|---|---|---|---|---|
| CondHealthy | 0.0000 | 0.0040 | 0.1280 | 0.2330 | **32×** |
| CondCongested | 0.0010 | 0.0200 | 0.2590 | 0.6705 | **13×** |
| CondTransient | 0.0010 | 0.0170 | 0.3270 | 0.7630 | **19×** |
| CondOutage | 0.0035 | 0.0280 | 1.1110 | 1.8700 | **40×** |

Not 2.0–2.6× as the per-run maxima suggested — **13–40×**. The conservative
estimator was hiding the effect, not inflating it.

> **This range was published as 14–53× before the 2026-11-11 correction.** The
> CondHealthy factor moved most (53× → 32×) because its E2 denominator, 4.0 ms,
> is only three times the 1.28 ms error. The lesson is recorded rather than
> buried: a ratio whose denominator approaches the measurement's own resolution
> should not be quoted as a headline, and **32×** is the defensible figure.

**And both halves of C2′ are visible in one table.** Reading down the `alert`
column, the alert gets *faster* as evidence grows (CondOutage 1.0071 → 0.3704;
CondTransient 0.0319 → 0.0203) while the `gap` column grows by one to two
orders of magnitude. The evidence does not delay the alert. It delays the
decision.

**Budget misses** rise at the same seam — CondCongested 0.7 % → 5.6 %,
CondTransient 7.4 % → 15.6 %, CondOutage 34.3 % → 38.9 % — now over escalations
rather than over 30 run-maxima, so the denominators mean something.

Reproducible from the repository alone, without the 956 MB corpus:

```sh
python3 tools/dispatch_times.py analysis/escalation_vec/escalation_latencies.csv.gz
```

Verified to print a table **identical** to the one computed from the corpus.

---

## 2a. Superseded: the same frontier from per-run maxima

Worst time-to-verification per run, seconds; median / 90th percentile / worst
over seeds. `>5 s` counts runs whose worst verification exceeded 5 s — **the 5 s
figure is an unsourced placeholder** (`PLAN_2026-11.md` §13, §14.5) and every
number in that column inherits its arbitrariness.

| condition | arm | rung | esc. | alert (med) | verify (med) | p90 | worst | > 5 s |
|---|---|---|---|---|---|---|---|---|
| CondHealthy | ref | none | 37 | 0.0165 | — | — | — | — |
| | E1 | 512 B | 34 | 0.0166 | 0.0156 | 0.7342 | 1.008 | 0/20 |
| | E2 | 3.5 KiB | 35 | 0.0174 | 0.0302 | 1.0167 | 1.047 | 0/20 |
| | E3 | 56 KiB | 37 | 0.0199 | 0.2831 | 1.0714 | 1.078 | 0/20 |
| | E4 | 138 kB | 37 | 0.0192 | 0.2920 | 1.3036 | 1.556 | 0/20 |
| CondCongested | ref | none | 141 | 0.8586 | — | — | — | — |
| | E1 | 512 B | 141 | 1.0389 | 1.1488 | 4.0645 | 6.390 | 1/30 |
| | E2 | 3.5 KiB | 139 | 0.5998 | 1.0525 | 2.7327 | 6.436 | 1/30 |
| | E3 | 56 KiB | 143 | 0.3703 | 2.1595 | 6.3739 | 7.525 | **7/30** |
| | E4 | 138 kB | 142 | 0.4980 | 2.7633 | 6.4995 | 10.336 | 5/30 |
| CondTransient | ref | none | 135 | 1.1011 | — | — | — | — |
| | E1 | 512 B | 134 | 0.8055 | 1.2847 | 6.1897 | 10.251 | 4/30 |
| | E2 | 3.5 KiB | 135 | 0.8762 | 1.3644 | 8.3966 | 14.607 | 5/30 |
| | E3 | 56 KiB | 141 | 1.3793 | 3.5825 | 14.8995 | 20.688 | **14/30** |
| | E4 | 138 kB | 139 | 0.5706 | 3.7056 | 10.2781 | 13.215 | 12/30 |
| CondOutage | ref | none | 69 | 4.9484 | — | — | — | — |
| | E1 | 512 B | 68 | 3.6730 | 4.7754 | 13.2235 | 20.194 | 12/27 |
| | E2 | 3.5 KiB | 70 | 3.9221 | 4.1410 | 16.0248 | 27.020 | 13/27 |
| | E3 | 56 KiB | 72 | 1.5199 | 8.5357 | 23.6979 | 27.419 | **16/27** |
| | E4 | 138 kB | 72 | 1.0730 | 12.2639 | 41.7466 | 71.792 | 16/27 |

Denominators below 30 are runs in which **no escalation fired at all** —
10 seeds in CondHealthy, 3 in CondOutage. Verified not to be lost evidence: in
every one of those runs `received_alarm = 0` and `evidenceChunksEmitted = 0`,
and it is **the same seeds in all four arms**, which independently confirms the
paired design (identical alarm processes across arms at equal seed).

---

## 3. What the frontier says

> ## ⚠ CORRECTED 2026-11-12 — THERE IS NO KNEE AND NO MODALITY STEP
>
> The claim this section used to make — *"cost is sublinear in bytes and the
> step is a modality change"* — **was an artefact of the superseded per-run-max
> estimator and is withdrawn.** When the per-escalation measurement replaced
> those maxima (§2), the *magnitudes* were updated (2.0–2.6× → 13–40×) and the
> *shape* conclusion was carried over unexamined. It does not survive.
>
> Log–log regression of the per-escalation median gap on evidence bytes,
> rungs E2…E4:
>
> | condition | slope | R² |
> |---|---|---|
> | CondHealthy | 1.11 | 0.976 |
> | CondCongested | 0.95 | 0.998 |
> | CondTransient | 1.03 | 0.993 |
> | CondOutage | 1.21 | 0.983 |
>
> **Slope ≈ 1 with R² ≥ 0.976: the dispatch gap is LINEAR in evidence bytes.**
> CondHealthy tracks pure transmission at the 3 Mb/s uplink almost exactly —
> predicted 0.0384 / 0.1529 / 0.3680 s at E2′ / E3 / E4 against measured
> 0.0330 / 0.1280 / 0.2330 s.
>
> **Why the old estimator lied.** A per-run maximum is the slowest chunk in a
> whole run, so it is set by the worst radio moment that run happened to meet —
> a quantity that does *not* grow with payload. Dividing two such maxima
> therefore understates any true volume dependence, manufacturing apparent
> sublinearity. The E2→E3 ratio of 2.05 for ×16 bytes was that artefact.
>
> **The "grant acquisition dominates transmission" mechanism is withdrawn with
> it.** It was inferred from the same sublinearity. Transmission dominates.
>
> **What survives, and it is simpler.** The E2→E3 gap ratio of 13–40× is
> *mostly the ×16 in bytes*. There is no free region below a knee and no
> qualitative boundary to design around: **every byte of verification costs,
> proportionally.** So the design rule is **send less** — and *verify from the
> waveform, not the image* is a special case of it, because a waveform at
> LF/HF-grade W is 3.2–9.0× **smaller** than one JPEG, not because the two
> differ in kind.
>
> This is a weaker claim about *structure* and a stronger one about *design*:
> there is exactly one lever, and it is total bytes. C4 then shows you cannot
> schedule your way around it either.

**The step is E2 → E3, and it is a VOLUME change.** The superseded per-run-max
table is kept below for the record:

| step | bytes | per-run-max ratio (Congested / Transient / Outage) |
|---|---|---|
| E1 → E2 | ×7 | 0.92 / 1.06 / 0.87 |
| E2 → E3 | ×16 | 2.05 / 2.63 / 2.06 |
| E3 → E4 | ×2.4 | 1.28 / 1.03 / 1.44 |

The budget-miss counts move at the same place — CondCongested 1/30 → 7/30,
CondTransient 5/30 → 14/30 — and then *fall back* at E4 (7→5, 14→12) despite
2.4× the data, which is itself a per-run-max artefact of the same kind.

**E2 is the rung the architecture was built for, and it is now measured.**
`PLAN_2026-11.md` §7 argued E2 delivers the same clinical quantity as E5 for
3.5 KiB because the edge already did the inference. Measured: E2's verification
latency is statistically indistinguishable from E1's — i.e. **independent HRV
verification from the waveform costs the network nothing beyond sending a bare
512 B token**, while independent *visual* verification costs 2–2.6× and pushes
7–14 of 30 runs past a 5 s budget. The design rule is **verify from the
waveform, never from the image** — and it is C1's metric split reappearing in
the verification path, so the paper derives one idea twice rather than asserting
two.

**The alert result replicates on an independent statistic.** Gate A used paired
per-run *means* with a sign test. Here, per-run *maxima*: worst alert delay falls
as evidence grows — CondOutage 4.9484 (no evidence) → 3.6730 → 3.9221 → 1.5199 →
**1.0730**; CondCongested 0.8586 → … → 0.4980; CondTransient 1.1011 → … →
0.5706. Different estimator, same direction.

---

## 4. The evidence deficit is mostly an artifact, and the artifact is mine

`evidenceChunksEmitted − received_evidence` is **not** a loss rate. An escalation
late in the run leaves its burst in flight at the simulation horizon, and that
shortfall is indistinguishable from loss in the aggregate. The discriminator:
truncation can affect **at most one burst per run**, so a per-run deficit
exceeding one burst's chunk count is real loss.

| condition | arm | deficit | % | runs hit | max deficit / burst size | runs > 1 burst |
|---|---|---|---|---|---|---|
| CondHealthy | E1 | 3 | 8.11% | 3/30 | 1 / 1 | 0 |
| | E2 | 9 | 8.11% | 3/30 | 5 / 3 | 1 |
| | E3 | 9 | 0.59% | 4/30 | 4 / 41 | 0 |
| | E4 | 11 | 0.30% | 5/30 | 4 / 99 | 0 |
| CondCongested | E1 | 8 | 5.52% | 8/30 | 1 / 1 | 0 |
| | E2 | 27 | 6.21% | 11/30 | 5 / 3 | 3 |
| | E3 | 120 | 2.02% | 18/30 | 45 / 41 | 1 |
| | E4 | 347 | 2.42% | 22/30 | 104 / 99 | 1 |
| CondTransient | E1 | 12 | 8.28% | 11/30 | 2 / 1 | 1 |
| | E2 | 38 | 8.74% | 15/30 | 5 / 3 | 3 |
| | E3 | 245 | 4.12% | 18/30 | 50 / 41 | 2 |
| | E4 | 898 | 6.26% | 21/30 | 209 / 99 | 4 |
| CondOutage | E1 | 7 | 9.59% | 7/30 | 1 / 1 | 0 |
| | E2 | 16 | 7.31% | 9/30 | 5 / 3 | 1 |
| | E3 | 152 | 5.08% | 19/30 | 56 / 41 | 1 |
| | E4 | 479 | 6.63% | 19/30 | 187 / 99 | 2 |

**Conclusion:** the deficit is dominated by horizon truncation. Genuine loss is
confined to CondTransient and CondOutage at the larger rungs, in at most 4 of
30 runs. **The 5–10% figures must not be reported as loss rates** — an earlier
draft of this analysis did exactly that before the discriminator was applied.

Unresolved: the real losses that remain are unexplained, and would need either
a drop-cause breakdown or a longer horizon to attribute.

---

## 5. What is not solid here

1. **The 5 s budget is unsourced.** The seam's *location* (E2→E3) is visible in
   the latency ratios independently of any budget, but every `> 5 s` count is
   conditional on a placeholder.
2. **W = 30 s is unsourced, and E2's 3.5 KiB is derived from W**
   (`PLAN_2026-11.md` §7, §13). E2 is now the paper's central rung, so the
   central design rule rests on a presumed number. **This is the highest-priority
   provenance hole in the project.**
3. **30 per-run maxima per cell**, not per-escalation distributions — §1.
4. **Edge processing is unsourced and ~2 orders too fast** (M4). Under C2′ it
   sits inside the dispatch budget rather than outside it, so it now biases the
   headline quantity, not just a side figure.
5. **Unequal observation windows across conditions** — `sim-time-limit` is 320 s
   for CondHealthy, 680 s for CondOutage, 1369 s for the other two, set by the
   route each trace covers. Arm-to-arm contrasts within a condition are clean
   (same window); **cross-condition counts and tails are confounded** and must
   be normalised or declared.
6. **CondHealthy is thin** — 320 s window, ~35 escalations, 10 of 30 seeds with
   no escalation. Its cells are not individually resolvable.
7. **The residual alert benefit's mechanism is still unidentified**
   (`GATE_A_RESULT.md`); needs per-packet attribution the rig lacks.

---

## 6. Provenance

Derived from `analysis/escalation_sr/pilot_all.csv.gz`, a lossless extract of
the corpus produced by `tools/extract_sca.py` and verified value-by-value by
`tools/verify_extract.py`:

```
OK: 3364877 values match exactly; 48600 histograms sum to their recorded count
```

See `analysis/escalation_sr/README.md` for what the extract keeps and drops, and
for how to regenerate the corpus from the repository.

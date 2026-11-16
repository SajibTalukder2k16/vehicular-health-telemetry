# The claim → evidence → figure map

**Written 2026-11-12, before any prose.** Its job is to find out whether the
four contributions form one argument or two papers, and to say exactly what has
to be drawn. Every number below is traced to the document that derives it; a
number without a source line is not in this table.

Status key: **D** derived (no simulation), **M** measured, **X** rests on an
extrapolation that is stated in the paper.

---

## 1. The argument, in four sentences

> **C1** PRV-grade camera sensing fails three independent capacity walls — the
> cloud link, the wearable link, and the edge's own compute — while HR-grade
> passes all three, so the partition is forced rather than chosen.
> **C2′** Once the inference is local, the evidence no longer delays the
> *alert*; it delays the *decision*, because the server verifies before
> dispatching.
> **C3** That delay is **linear in evidence bytes** (slope 0.95–1.21,
> R² ≥ 0.976) — there is no knee and no free region, so the only lever is
> total volume.
> **C4** Therefore any mechanism that defers the evidence defers the decision —
> and the gateway's inherited admission machinery is not merely unhelpful but
> structurally incapable of helping, by derivation.

Each step uses the previous one's conclusion as its premise. **C4 is not a
bolt-on once it is derived rather than measured** — which settles the scope
question in §5.

---

## 2. C1 — the partition is forced

| # | Claim as it will appear | Evidence | Status | Source |
|---|---|---|---|---|
| 1.1 | PRV needs 60 fps; HR needs ~20 fps | Cerina et al. | **X** | PROV §A.1, §5.1 |
| 1.2 | PRV-grade video is 25.5 Mb/s; HR-grade telemetry 0.110 Mb/s — a **232×** split. *Corrected 2026-11-13 from "250×", which was the ratio of the rounded operands; 25.5/0.110 = 231.8* | derived from 1.1 | **D** | PLAN §5.2–5.4, PROV §A.1 |
| 1.3 | **Wall 1, cloud link:** 25.5 Mb/s does not cross a 3 Mb/s cellular uplink | derived + measured | **D** | PLAN §5.2 |
| 1.4 | **Wall 2, wearable link:** nor a 0.74 Mb/s BLE radio | derived | **D** | PLAN §5.3 |
| 1.5 | **Wall 3, edge compute:** 60 fps allows 16.67 ms/frame. **Measured for rPPG on a Pi 4B: none of 8 methods fits** — fastest (POS) 27 ms = 1.62× over, fastest learned (EfficientPhys-C) 40 ms = 2.40× over. Device-class extrapolations 22.73 / 94.27 ms = 1.36× / 5.66× retained for the sweep | **Liu et al. WACV 2023 (measured)** + Kim & Koo (**X**) | **M**+X | PROV §A.7b |
| 1.6 | Sustainable **camera** rate is ~42.5 fps (PC) and ~9.1 fps (embedded), because the edge is one FIFO shared with the vitals stream | 960 runs | **M** | EDGE §2 |
| 1.7 | The wall degrades **sensing**, not just latency: 60 fps on embedded forwards 14,521 of 84,227 packets → effective **10.6 fps**, below the HR floor | 960 runs | **M** | EDGE §2 |

**Figure F1 — the three walls.** Requirement vs capacity on three axes, PRV and
HR side by side. This is the paper's keystone figure. **DONE 2026-11-13**
(`figC1_three_walls`); drawn as diverging bars on `log10(requirement/capacity)`
with the wall at true zero, so grayscale-safe and the sign reads in print.
Renders: PRV infeasible on 5 of 6 constraints, HR on 1 of 6.

**~~The load-bearing caveat (1.5)~~ — CLOSED 2026-11-16.** The project's one
outstanding retrieval landed: Liu et al. measure eight rPPG pipelines on a
Raspberry Pi 4B and **not one meets the 60 fps budget**. The constraint is now
measured on the right pipeline. Two consequences, one of them against us: the
wall is **real**, and it is **closer than we reported** — 1.62×, not 5.66×. The
paper states the margin. Kim & Koo stay as the device classes the 960-run sweep
used, still labelled **X**; the measured rPPG cost falls between them.

---

## 3. C2′ — the conflict relocates

| # | Claim | Evidence | Status | Source |
|---|---|---|---|---|
| 2.1 | C2 as written is **refuted**: the burst does not delay the alert in **0 of 16** cells, and the sign reverses in 4 | 600 runs | **M** | GATE_A |
| 2.2 | The alert gets *faster* as evidence grows — CondOutage 1.0071 → 0.3704 s | 600 runs | **M** | VF §2 |
| 2.3 | The decision does not: the gap grows 1–2 orders of magnitude over the same ladder | 600 runs | **M** | VF §2 |
| 2.4 | Dispatch must be referred to the **sensor instant**; the two delay signals sit on different clocks | derivation + fix | **D** | EDGE §1 |

**Figure F2 — one table, two columns, opposite directions.** Alert delay and
dispatch gap against the ladder, four conditions. The whole of C2′ is visible in
one chart: one series flat-or-falling, the other exploding. **DONE 2026-11-13**
(`figC2_alert_vs_decision`) — 2×2 small multiples, both series in seconds on one
log axis (not a dual axis). Alert ratio over the ladder by condition:
**1.00× / 0.85× / 0.64× / 0.37×**, while the gap goes 0 → 0.2330 / 0.6705 /
0.7630 / 1.8700 s.

---

## 4. C3 — the frontier is linear, so the only lever is bytes

| # | Claim | Evidence | Status | Source |
|---|---|---|---|---|
| 3.1 | Gap by rung: E1 ≈ 0 → E2 0.004–0.028 → E3 0.128–1.111 → E4 0.233–1.870 s | 600 runs | **M** | VF §2 |
| 3.2 | The E2→E3 step is **13–40×** | 600 runs | **M** | VF §2 |
| 3.3 | The gap is **linear in bytes** — slope 0.95–1.21, R² ≥ 0.976; no knee, no free region. *Corrected 2026-11-12; the previous "modality step, sublinear" claim was a per-run-max artefact* | 600 + 480 runs | **M** | VF §3 |
| 3.4 | At LF/HF-grade W (≥120 s ⇒ 14.4 kB) verification costs **3.2–9.0× less than one JPEG** | 480 runs | **M** | PHASE2 §1 |
| 3.5 | Budget misses against eCall's **4 s** (TS 122 101 A.27.2) | 600 + 480 runs | **M** | PROV §A.6 |
| 3.6 | The rule survives a 50–190× change in edge cost: **20 of 20** cells, 2.0–22.7× | 960 runs | **M** | EDGE §3 |

**Figure F3 — the frontier.** Gap vs evidence bytes, log–log, four conditions,
with the 4 s budget drawn as a line and a slope-1 reference. The **linearity**
is the claim: no knee to exploit, so the only lever is total bytes. **DONE
2026-11-13** (`figC3_frontier`); the script prints its own slopes and R² on
every render, so the caption cannot drift from the fit.

---

## 5. C4 — the gate cannot help, by derivation

| # | Claim | Evidence | Status | Source |
|---|---|---|---|---|
| 4.1 | The gate alters a burst **iff B > b** — so 4 of 5 ladder rungs are exact no-ops | derivation | **D** | GATE §2 |
| 4.2 | Pacing **weakly increases** completion time at every `(b, r)`, by work conservation ⇒ can never speed dispatch under C2′ | derivation | **D** | GATE §3 |
| 4.3 | `0 ≤ penalty ≤ (B−b)/r`; measured at **36–61 %** of the bound | derivation + 480 runs | **D+M** | GATE §4 |
| 4.4 | The penalty is largest where the link is **healthiest** — forced, not curious | derivation | **D** | GATE §4 |
| 4.5 | Pacing is a **Pareto loss**: no completeness gain (99.0–99.6 % vs 99.0–100 %) | 480+600 runs | **M** | GATE §5 |
| 4.6 | ~~`dropPace` buys 1.7–2.5× latency with 46.5–47.5 % of the evidence~~ **WITHDRAWN 2026-11-12** — an artefact of an unset arrival timestamp. Replaced by: staleness discard fires iff `maxAge < (B−b)/r`, so the inherited 2 s **cannot fire** — a third structural no-op | derivation + 600 runs | **D** | PHASE2 §4, GATE §Prop 4 |
| 4.7 | The loss is **misattributed, not invisible** — counted under `cameraStaleDropped`, while `evidenceChunksDropped` reads 0 | probe + fix | **M** | PHASE2 §4 |
| 4.8 | **Confirmed 2026-11-13:** no `(b, r)` in the swept space helps — all 48 cells ≥ 0, max penalty +0.8082 s at 16 KiB/1 Mbps; the `b > B` control is exactly 0 in all 12 cells | 2,160 runs | **M** | SWEEP §1–2 |
| 4.9 | Two nulls retained from the mechanism layer (freshness-signal source; circular throughput estimation) | prior runs | **M** | PLAN §8.1 |

**Figure F4 — the sweep, with the bound drawn over it.** **DONE 2026-11-13**
(`figC4_gate_bound`), and the form changed on contact with the result: instead of
penalty vs bucket depth with the bound as an envelope, it plots each cell's
*measured* penalty against *its own* derived bound. Props 2–3 then become a
triangle (`y ≥ 0`, `y ≤ x`) and the claim is "nothing escapes it". All 48 cells
inside; the script asserts 0 above the bound, 0 below zero, 0 non-zero controls
on every render, so a change that breaks the derivation breaks the figure build.

~~**Figure F5 — the trap.**~~ **DROPPED 2026-11-13** — see §6.

---

## 6. Figures: one of nine survives

| | Figure | State |
|---|---|---|
| F0 | The architecture, after the partition | **DONE 2026-11-16** `figC0_architecture`. *Not* an edit of `arch_system.py`: four of that figure's five load-bearing statements are contradicted by our own results — it gated the **camera**, drew frames reaching the cloud, drew the gate **admitting**, closed a feedback loop onto `r(t)`, and labelled the server with AoI. Editing it would have left a diagram still composing the old argument, so `arch_system.py` is kept unedited as the record of the withdrawn framing, exactly as `main_v05.tex` is |
| F1 | The three capacity walls | **DONE** `figC1_three_walls` |
| F2 | Alert vs decision, opposite directions | **DONE** `figC2_alert_vs_decision` |
| F3 | The verification frontier | **DONE** `figC3_frontier` |
| F4 | Gate sweep against the derived bound | **DONE** `figC4_gate_bound` |
| ~~F5~~ | ~~The latency/completeness trap~~ | **DROPPED 2026-11-13.** Its content was C4.2, which is withdrawn; what replaced it is "at every `maxAge ≥ 1 s`, nothing happens" — four identical flat lines. A structural null reads better as a table row than as a figure slot. Folded into C4's table |

The other eight existing figures — feasibility heatmap over ISD×speed, delay
ECDFs, delivery vs ISD, AoI timeseries, CQI calibration, oracle frontier, load
effect — belong to the **withdrawn** framing. `fig6_oracle_frontier.py` is
docstringed *"the paper's central claim, drawn"* for a claim that no longer
exists. They are not deleted; they are simply not this paper's figures.

---

## 7. Where a reviewer will push, and whether we can answer

| Attack | Answer | Strong? |
|---|---|---|
| *"Your edge cost is from a different pipeline"* | **Answered 2026-11-16.** The constraint is now measured on rPPG itself (Liu et al., 8 methods, Pi 4B, none meets the 60 fps budget). Kim & Koo remain only as the swept device classes, labelled **X**, and the measured rPPG cost falls between them | **strong** — but the margin is 1.62×, so say so |
| *"You chose a bad gate configuration"* | Derived, not measured, and a 2,040-run sweep searches the space with a positive control | **strong** once the sweep lands |
| *"45 % of bytes is not a verification failure"* | Agreed, and the paper says "45 % of the bytes arrived" — detection is out of scope | **strong** (concedes correctly) |
| *"CondHealthy is thin"* | 37 escalations, 20 paired seeds, 320 s window — stated in every result document | **weak; disclosed** |
| *"Your conditions have unequal sim windows"* (320 / 1369 / 680 s) | Set by the route each trace covers; the per-escalation analysis uses rates not counts, so it is mostly handled — but cross-condition *counts* are not comparable | **partially answered — needs a sentence in the method** |
| *"W = 30 s is SDNN-grade, you need LF/HF"* | Anticipated: re-scoped, and E2′ measured at the right W | **strong** |

---

## 8. What this map settles

**One paper.** The §1 chain is unbroken, each step consuming the last, and C4
stopped being a separate reader's contribution the moment it became a
derivation: 4.1–4.4 are consequences of C2′ and C3, not an independent policy
study. The earlier worry — *"C4 barely needs C1"* — was true of C4 **as
measured** and is false of C4 **as derived**.

**~~The binding constraint is figures, not compute.~~** — **cleared 2026-11-13.**
All four result figures exist and re-render clean from
`analysis/figures_src/figC*.py`; F5 was dropped as a structural null. The PDFs
are staged into `manuscript/figures/` so `\includegraphics` resolves.

**What is genuinely unresolved before prose can be trusted** (checked 2026-11-13):

1. **The rPPG per-frame retrieval** (§2) — one paragraph of C1, and the wall's
   *position* only; its existence is supported. Flagged **X** everywhere it is used.
2. **A method sentence on unequal simulation windows** (§7) — 320 / 1369 / 680 s.
3. **`manuscript/main_v05.tex` is the withdrawn framing.** It is titled *From
   Room to Road*, and line 619 still `\includegraphics{fig6_oracle_frontier}` —
   the figure docstringed *"the paper's central claim, drawn"* for a claim that
   no longer exists. **Drafting means a new `main_v06.tex`, not an edit of v05.**
   Reusable from v05: preamble, author block, `references.bib`, and the method
   and calibration text that survived the pivot.
4. **`arch_system.pdf` draws the admission gate open**, which C4 contradicts.
5. **One quantity has two measured values from two corpora.** The inherited
   gate's penalty in CondHealthy is **0.3520 s (61 % of the bound)** in the
   480-run Phase-2 corpus (GATE §4) and **0.4442 s (77 %)** in the 2,160-run
   gate corpus (SWEEP §2–3). Both are correct for their corpus and both are
   inside the bound; they are *not* interchangeable in prose. **Decide once
   which corpus the paper quotes for the inherited gate, and say so**, or a
   reviewer comparing the two tables finds a 26 % discrepancy with no stated
   cause. The sweep corpus is the better choice: it carries its own internal
   `policy=none` baseline at matched seeds.

Items 1–2 do not block drafting. Item 3 shapes how drafting starts. Items 4–5
must be settled before the C4 section and its figure go in.

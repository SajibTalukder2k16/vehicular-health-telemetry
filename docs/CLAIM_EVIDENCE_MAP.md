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
| 2.3 | The decision does not: the gap grows 1–2 orders of magnitude over the same ladder, to **0.4020 s** in CondOutage **among complete escalations** | 600 runs | **M** | VF §2, COMPLETION §4 |
| 2.4 | Dispatch must be referred to the **sensor instant**; the two delay signals sit on different clocks | derivation + fix | **D** | EDGE §1 |

| 2.5 | **NEW, primary.** Under a full-evidence policy, **11–31 % of escalations never become ready** at E4 (completion 88.6 / 78.5 / 79.1 / 68.5 %). Byte-completeness of 99 % hid this: a burst is 99 chunks | 600 + 2,160 runs | **M** | COMPLETION §3, §5a |
| 2.6 | At `cameraMaxAge = 0.5 s`, **0 of 393 escalations complete** (max burst 91 of 99 chunks) while dispatch latency *improves* 11 %. The sharpest form of the paper's methodological warning | 2,160 runs | **M** | COMPLETION §5a |

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
| 3.3 | The gap is **proportional to bytes over the three sizes tested** — slope 0.81–1.16, R² ≥ 0.961. *Corrected twice: the "modality step, sublinear" claim was a per-run-max artefact (2026-11-12), and the slopes were refitted on complete escalations only (2026-11-16). Three sizes cannot exclude a knee* | 600 + 480 runs | **M** | VF §3, COMPLETION §5 |
| 3.4 | At LF/HF-grade W (≥120 s ⇒ 14.4 kB) verification costs **2.6–4.2× less than one JPEG** among complete escalations (was 3.2–9.0× over the unconditional mixture). Its *completion* rate, 83.9–93.8 %, is not better than the image's 80.0–91.6 % | 480 runs | **M** | PHASE2 §1, COMPLETION §5 |
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

---

## Added 2026-11-18 — the indoor campaigns, and two claims withdrawn

Evidence: `docs/INDOOR_BACKHAUL_RESULT.md`. Corpora
`simulations/room/results_room_wifi/` (300 runs) and
`simulations/pilot/results_indoor_lte/` (150 runs). Tools
`tools/analyze_room_ladder.py`, `tools/compare_backhaul.py`.

| claim in the paper | evidence | status |
|---|---|---|
| A quiet WLAN carries a PRV-grade camera; a busy one does not | 0 of 17,969 frames dropped quiet; 75.95 % dropped at 80 % busy vs a 75.8 % derivation | **measured**, C1's WLAN row promoted from derived |
| The camera's load stays off the verification path | completion 100 % and E4 gap 0.0350 s identical across wired / quiet WLAN / busy WLAN | **measured** |
| The gap cost is dominated by the backhaul | ×3.78 per-seed, Mann–Whitney p = 1.5e-7, mobility/load/window matched | **significant** |
| The completion failure is dominated by coverage loss | 83.8 → 51.4 %, Fisher p = 0.0009 | **significant** |
| Mobility and moderate load move the gap | ×1.54, p = 0.156 | **not detected** — stated as a failure to detect, never as equivalence |
| An LTE backhaul costs completion | 100 → 91.4 %, Fisher p = 0.239 | **not detected** — neither direction is supportable |
| A run's first escalation is slower (cold grant) | ×2.10, p = 0.262; WLAN control flat at ×1.00 | **open question**, explicitly not claimed |

**Two previously published statements withdrawn, both overstatements:**

1. **"The 16–49 % failure is a property of the mobile uplink."**
   (`ROOM_LADDER_RESULT.md` §3, and the paper's §room.) "Mobile" was doing
   work the evidence did not support: with mobility matched, the gap step is
   the backhaul and the completion step is coverage. Replaced with "the
   delivery path", decomposed.
2. **"On cellular the alert falls as evidence grows; the effect is specific to
   cellular grant acquisition."** (`ROOM_LADDER_RESULT.md` §4.) Across E1→E4
   the alert is flat in `CondHealthy`, trendless within a few ms in
   `CondCongested` and `CondTransient`, and falls materially only in
   `CondOutage` — non-monotonically. A stationary unloaded *cellular* arm is
   flat too. It is a coverage-loss effect plus a ref→E1 step.

**One artefact caught and not reported as a result.** An apparent 1.3 → 1.5 ms
alert shift under a busy WLAN came from `camLink` sharing RNG stream 4 with
the BLE link and the edge service (`simulations/room/omnetpp.ini:27`).
Isolating the stream reverses the sign. No published result is affected:
`WiredLink` makes no random draws, and every earlier campaign runs the camera
on a cable.

**Open, and the user's call:** the artifact repository is pinned at commit
`c6f0f81` in §Reproducibility. The two new corpora, three new tools and the
`CondIndoorLte` configuration are **not yet in it**, so the pin is stale with
respect to this document.

## Added 2026-11-18 (second) — the BLE camera

Evidence: `docs/BLE_CAMERA_RESULT.md`. Corpus
`simulations/room/results_room_ble/` (450 runs), driver
`tools/room_ble_ladder.sh`.

| claim in the paper | evidence | status |
|---|---|---|
| A PRV-grade camera cannot use BLE | 97.07 % of 17,969 frames dropped; the 2.93 % surviving is 0.747 Mb/s | **measured**, C1's largest margin |
| A 4 KiB camera at 10 fps *can* use BLE | 0 drops of 2,994; frontier 23.3 fps at that frame size | **measured** |
| Large frames waste a BLE link | 53 kB at 2 fps delivers 0.426 Mb/s vs 0.747 at 60 fps; 64 KiB buffer holds one frame | **measured** |
| A BLE wearable needs one PDU per interval or delivers nothing | cliff between `maxCiUtilization` 0.0823 and 0.0820, against a derived 2468/30000 = 0.08227 | **measured**, derivation confirmed to 3 dp |
| A saturated sensor link does not touch the escalation path | completion 100 %, E4 gap 0.0350 s across wired / WLAN quiet / WLAN busy / BLE | **measured but structural** — the alarm is edge-generated (`SensorRig.ned:68`), so the paper states this as a consistency check, not a finding |

**One label in this repository corrected.** `Room5GHzCameraBle` was described
as "documented-infeasible: 4KiB camera at 10fps over BLE". That configuration
offers 0.33 Mb/s against a ~0.765 Mb/s ceiling and drops nothing. The label
conflated a 4 KiB camera with a PRV-grade one and has been rewritten.

**One prediction wrong in an instructive way.** P5 put the wearable's cliff
below `maxCiUtilization` ≈ 0.05, reasoning from its bandwidth need (512 B/s of
0.765 Mb/s, about 0.5 %). The real threshold is 16× higher at 0.0823 because
the binding constraint is whether a single PDU fits in the interval budget,
not throughput. A BLE link's floor is set by quantisation.

**A metric trap, the same shape as `maxAge = 0.5 s`.** In the stalled arms the
drop counter reads 57.53 % while delivery is **zero**; the other 42.5 % sit in
a queue that never drains. Scoring that arm on drop rate reports a partial
problem where the truth is total failure.

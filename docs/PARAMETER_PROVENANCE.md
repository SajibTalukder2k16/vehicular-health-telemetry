# Parameter provenance register (2026-11-05)

Every number the simulation consumes, where it came from, and whether that
source survives inspection. Standing rule for this project: **a parameter
without a source is a finding waiting to be withdrawn.**

Status key — **✔ sourced** · **~ partial** · **✘ unsourced** · **✘✘ wrong or
misattributed**

---

## A. The two findings that change the model

### A.1 ✘✘ The camera cannot do rPPG at 2 Hz

The application's premise is camera-derived vital signs. The rPPG literature
is consistent about what that needs:

- **~30 fps or higher** for reliable heart-rate variability; a 2021
  telemedicine evaluation found HRV correlation held "when the frame rate was
  higher than 30 fps", and that lower frame rates enlarge pulse-interval error.
- **~20 fps is the rough floor** for heart rate alone (2024 webcam study,
  *Behavior Research Methods*), which also warns that frame rate and
  resolution "cannot be optimized post hoc" — interpolation adds nothing.

Our camera runs at **2 Hz**. That is 10–15× too slow for the sensing the
system is built on.

**But this is a sensor-link requirement, not a backhaul one, and that
resolves it.** The edge device does the inference — which is the architecture
as described. So:

| Tier | What actually flows | Rate |
|---|---|---|
| camera → edge (in-vehicle / in-room) | raw frames for rPPG | **20–30 fps** |
| edge → cloud (cellular / WiFi) | extracted vitals, status; **on escalation**, an evidence clip | low, bursty |

This is a better model than the current one *and* it makes three existing
results matter more: the BLE camera link's documented infeasibility stops
being a curiosity and becomes the reason a wearable-class radio cannot carry
the primary sensor; the WLAN link model earns its place; and the backhaul
contention becomes a contest between *summaries and escalation evidence*,
not raw video.

**Action:** restructure the traffic model along the tier split above. Cite the
rPPG frame-rate requirement for the sensor link; keep `ehealth_qos` Tables 2–3
for the evidence-clip bitrate.

### A.2 ✘✘ Edge processing time is roughly two orders of magnitude too fast

Current: `uniform(0.5, 2) ms` (embedded) and `uniform(2, 8) ms` (smartphone),
unsourced.

The driver-monitoring literature measures this directly, because it is their
headline number:

- ~**57 ms/frame** on a Raspberry Pi 5; ~**40 ms** on a Coral Edge TPU
- **100–300 ms** glass-to-glass on embedded platforms (2026 survey)

Inference on a video frame is tens to hundreds of milliseconds, not single
digits. Our edge is modelled as doing almost no work, which is the opposite of
"the edge device will do the computing".

**Action:** re-source both device classes from the DMS literature. This also
gives the phone-vs-PC contrast a real basis instead of two invented uniforms.
Note the direction: a slower edge adds latency *before* the network, so the
current model **understates** end-to-end time to notification.

### A.2 (M4 resolved 2026-11-10) — one primary measurement retrieved, and the other three figures withdrawn

**First, a withdrawal.** The three figures above — "~57 ms/frame on a Raspberry
Pi 5", "~40 ms on a Coral Edge TPU", "100–300 ms glass-to-glass (2026 survey)"
— were written from search summaries and **were never retrieved**. Same failure
mode as the ≥10 Mb/s retraction. They are withdrawn. The plan's "the DMS
literature measures ≈40–300 ms" rested on them and is withdrawn with them.

**What was actually retrieved.** Kim M, Koo J. *Embedded System Performance
Analysis for Implementing a Portable Drowsiness Detection System for Drivers.*
**Technologies 2023, 11(1):8**, doi `10.3390/technologies11010008`; preprint
`arXiv:2209.15148`, full text retrieved from arXiv. Verbatim from the abstract:

> "Based on our experiments, the average total processing time to run the
> drowsiness detection model was **94.27 ms for the Jetson Nano** and
> **22.73 ms for the Beelink (Mini PC)**."

| Platform | Measured total processing time | Maps to this project's |
|---|---|---|
| Jetson Nano | **94.27 ms** | embedded / phone-class edge |
| Beelink Mini PC | **22.73 ms** | PC-class edge |

So the ini's `uniform(0.5ms, 2ms)` understates a PC-class edge by **~11–45×**
and an embedded edge by **~47–190×**. The direction of the error is confirmed
and its magnitude is now sourced at two points.

**Caveats, stated.**
- The paper measures **one** pipeline — Ghoddoosian et al.'s temporal-blink
  model plus face detection and landmarks — not the three-way camera + wearable
  + OBD fusion this project assumes. It is the closest *measured* analogue, not
  the same system.
- A per-stage breakdown and a reported standard deviation (≈3 ms) exist in the
  paper's tables, but those tables did not survive text extraction here, so
  **only the two abstract figures are quoted**. Anything finer needs the tables
  read by eye.
- Both authors were secondary-school students at the time of writing; the venue
  is peer-reviewed (MDPI *Technologies*) and the measurement is a
  straightforward timing experiment, but the paper is not a heavyweight source
  and the paper should cite it as what it is.

**Model action, deliberately NOT a silent re-tune.** Edge processing is common
to every arm, so it shifts absolute dispatch time without confounding any
arm-to-arm contrast — but under C2′ it now sits **inside** the dispatch budget,
so it biases the headline quantity. Changing it would also break comparability
with the 1,080 runs already on disk. It is therefore recorded as a **two-level
sensitivity factor** rather than a new default:

| Level | `*.rig.edge.processingTime` | Basis |
|---|---|---|
| PC-class | `22.73ms` | Beelink Mini PC, above |
| Embedded | `94.27ms` | Jetson Nano, above |
| *(current)* | `uniform(0.5ms, 2ms)` | **unsourced; retained only so the existing corpora stay comparable** |

Both sourced values are carried in `simulations/pilot/omnetpp.ini` as commented
alternatives next to the live line, so the right number is visible at the point
of use. **No result may be reported as an absolute time-to-dispatch at the
unsourced value** — the 0.5–2 ms line shifts every dispatch figure down by
20–90 ms, which is small against CondOutage's seconds but not against
CondHealthy's 16 ms alert.

**MEASURED 2026-11-11 — the factor was run, 960 runs** (`EDGE_COST_RESULT.md`).
Three things are now settled rather than argued:

1. **The shift is 30–283 ms, not 20–90 ms.** The estimate above assumed the
   shift equals the service time. It does not: `EdgeAggregator` is a single FIFO
   shared with the vitals stream, so the per-frame latency is service **plus**
   queueing — measured at **1.3–1.6× nominal at 30 fps and 2.1–3.0× at 60 fps**.
2. **Every arm-to-arm contrast survives.** The dispatch gap is statistically
   invariant to edge cost in **23 of 24** paired cells (exact sign test; the one
   hit, p = 0.041 across 24 tests, is the expected false positive), and
   "verify from the waveform, not the image" holds in **20 of 20** cells at
   2.0–22.7×. So the sensitivity factor vindicated the decision not to re-tune.
3. **Absolute dispatch times are now reportable**, at 30 fps / PC-class — the
   only measured regime where inference fits the frame interval (§A.7).

One correction in the other direction: in a **coverage outage** the edge cost is
free or even beneficial, because displacing the escalation instant by hundreds
of milliseconds makes it meet a different radio state, and the radio
(0.47–1.18 s of alert delay) dominates the edge entirely.

### A.3 ✔ Two newly sourced quantities now carry the paper's main claim

Added 2026-11-06. These are not corrections — they are new inputs, and
`PLAN_2026-11.md` §2 and §3.1 both rest on them, so they get the strictest
treatment in this register.

| Quantity | Value | Source | Status |
|---|---|---|---|
| ~~rPPG video bitrate floor~~ | ~~≥10 Mb/s~~ | **WITHDRAWN same day — see below** | **✘✘ retracted** |
| rPPG video quality knee | ≈2 Mb/s (VP8) | Zhao et al., CVPR 2018 Workshops | **~** retrieved, but contradicted by the rows below |
| Compression mechanism | inter-frame coding adds noise to the BVP signal | *Biomed. Signal Process. Control*, 2024 | **✔** abstract |
| **PRV-grade bitrate** | **≈25.5 Mb/s** at 60 fps (H.264 CRF 8). Threshold lies in **2.57–25.5 Mb/s**; CRF 16 (2.57 Mb/s) collapses RMSSD 0.9433→0.8319 and IBI SD 0.9532→0.8258 | **Cerina Table 1 × the paper's own stated recording format.** Table 1: FFV1 43.4 %, CRF 8 5.77 %, CRF 16 0.58 % of uncompressed. Format: 640×480, 24-bit RGB, 60 fps ⇒ uncompressed 442.4 Mb/s. Arithmetic verified in place | **✔ FULL TEXT** in `papers/10.1515_bmt-2016-0234.pdf` |
| PRV frame rate | **60 fps**, not 30 | same paper: all PRV params degrade with frame-rate reduction, spectral indices drop significantly ≤20 fps, *"the highest frame-rate (i.e. 60 Hz in our study) should be used"* | **✔** quoted from full text |
| Compression mechanism, PRV | peak displacement **≤4 ms FFV1** (2.9 ms standing) vs **11.3 ms and 98.9 ms at CRF 16** | same paper | **✔** — physical explanation of why HRV dies and HR does not |
| **HR**-grade bitrate | **≈0.11 Mb/s** (MAE 1.4 bpm, 30 s windows, CRF 24 stationary) | **Nowara, McDuff & Veeraraghavan**, *Biomed. Opt. Express* 12(1):494–508, **2021** (corrected 2026-11-13 from 2020 — vol. 12 no. 1 is dated 1 January 2021 on the article's own page furniture; doi `10.1364/BOE.408471`), §4.1: CRF 12/18/24/30/36 ⇒ **890, 534, 110, 87, 67 kb/s** stationary; **1500, 1077, 230, 221, 88 kb/s** under large head motion | **✔ FULL TEXT** in `papers/boe-12-1-494.pdf` |
| → the metric split | **HR 0.110 Mb/s, PRV 25.5 Mb/s — a 232× gap.** ⚠ **CORRECTED 2026-11-13: this row read "HR ≈0.1, PRV ≈25 — a 250× gap".** 250× is the ratio of the *rounded* operands; the sourced values give 25.5/0.110 = **231.8**. Same error class as the 53×/32× ratio: a ratio is only as precise as its operands. **The paper quotes 232×** | two independent primary sources agreeing (Cerina Table 7: HR 0.9996→0.9993 across *all* compression) | **✔** this gap is contribution C1 |
| Cerina et al. population | **60 recorded / 57 analysed**, age 23±4, healthy, **SUPINE**; Sony XCG-C30C at 640×480 | full text | **✔** — the supine/resting population is a **stated limit on extrapolating to a moving vehicle** |
| 802.11 max DCF throughput anchor | TMT = MSDU/(a·MSDU+b); OFDM-54 CSMA/CA a=0.14815 µs/B, b=159.94 µs ⇒ **31.40 Mb/s** at 1500 B | **IEEE 802.11-01/055 NOT RETRIEVED** (mentor.ieee.org HTTP 418) and **must not be cited on a presumed title.** Replaced by Jun, Peddabachagari & Sichitiu, **IEEE NCA 2003**, doi 10.1109/NCA.2003.1201163 (venue verified — NCA, *not* IPCCC) | **✔ FULL TEXT** in `papers/`. Our WifiLink gives 30.882 → **−1.6 %**. First peer-reviewed anchor for this module |
| Motion sensitivity | signal loss **steeper under head motion**; x265 better there | McDuff, Blackford & Estepp, FG 2017 | **✔** abstract; directly relevant to the vehicle case |
| Deep-model breakdown | models trained on lossless **fail at CRF ≥ 22** (H.264 and H.265) | compression-effects study, 2024 | **~** abstract |
| Counter-evidence | learned magnification partly recovers rPPG from compressed video | arXiv:2405.02652, 2024 | **✔** must be cited, not omitted |
| HRV analysis window, W | **30 s** | 10 s valid for RMSSD and 30 s for SDNN in a 3,387-subject resting study; athlete studies find 10 s has the widest limits of agreement vs the 5-min criterion. **Conservative end of a contested range** | **~** report W as a parameter |
| HR-only window | ≈10 s (rPPG evaluation convention) | **not yet confirmed** | **✘** Phase 0 |

### Retraction: the ≥10 Mb/s floor (written and withdrawn 2026-11-06)

Written into this register and into `PLAN_2026-11.md` §2 on the strength of a
**secondary summary**, with the attribution to McDuff, Blackford & Estepp
(FG 2017) marked "presumed". Retrieval found:

- **McDuff et al. says close to the opposite.** Bitrate "can be substantially
  decreased (**by a factor of over 1000**) without destroying the BVP signal
  entirely." It is the foundational compression paper and it is *not* the
  source of the figure.
- The only trace of "≥10 Mb/s" anywhere is **one secondhand sentence** in
  arXiv:2405.02652 about "an earlier study". Three searches did not identify
  the original.
- Independent contradictions: **≈0.3 bpm** HR error across a 26 → 0.26 Mb/s
  cut; clinical IP cameras running rPPG at **85–1500 kb/s**.
- **The pre-committed 2 Mb/s fallback is undercut by the same evidence**, so
  the mitigation recorded in the risk register did not hold either.

**What survives is a metric split**: HR is robust to compression; SNR and
pulse-rate variability are not. The requirement is a **codec-structure
constraint (intra-frame or lossless), not a bitrate floor.**

**Resolved the same day.** Cerina et al.'s abstract was retrieved verbatim
through OpenAlex and Europe PMC — both refused by the publisher and PubMed
directly, both open through bibliographic APIs. It confirms the structural
constraint in the authors' own words and supplies *"less than 45% disk size"*
for FFV1, which converts the constraint to a bitrate **by arithmetic rather
than by citation** (rows above). The requirement that replaced the withdrawn
one is therefore stronger: no contested threshold anywhere in it.

**The standing rule held, and this is what it is for.** The figure was caught
by retrieval, before compute, because it was marked presumed rather than cited.
A parameter without a source is a finding waiting to be withdrawn — this one
was withdrawn on the day it was written, and the claim it supported came back
better founded than before.

**Procedural note worth keeping.** Three publisher/standards hosts refused
automated access in this episode — PubMed (cookie wall), De Gruyter (HTTP 405)
and mentor.ieee.org (HTTP 418). **OpenAlex, Europe PMC and Crossref served the
same metadata and abstracts without obstruction.** Use them first. Where even
they fail, replace the citation or mark the gap; do not soften a claim to fit
what could be reached.

---

### A.4 ✘✘ The uplink grant-acquisition tail: `retxBsrTimer` is not a legal 3GPP value, and no value fixes it

Found 2026-11-08 while diagnosing Gate A (`docs/GATE_A_RESULT.md`). This is a
**model limitation, not a parameter we can re-source**, and it bounds every
absolute alert-latency number the project can report.

**What the rig does.** An alert arriving when the UE's uplink buffer is empty
waits for a grant. Traced on CondHealthy/seed 3 with the channel made
deterministic: the alarm enters PDCP at t = 132.274124 and the eNB first sees
it at t = 133.283 — `rlcDelayUl` = 1.008876 s against `macDelayUl` = 0.004 s.
The time is grant acquisition, not transfer, not backhaul and not congestion
(`avgServedBlocksUl:mean` = 0.0031, i.e. the cell is idle).

**Root cause, read off the source.** Simu5G models **no PUCCH and no
Scheduling Request**: `grep -rn "srProhibit\|SchedulingRequest" src/` returns
nothing, and PUCCH appears only in `LteAirFrame.msg`. Grant re-acquisition is
therefore contention RACH → BSR → grant, and `LteMacUe.cc:516-517` sets
`bsrRtxTimer_ = bsrRtxTimerStart_` after each BSR with the comment "this
prevents the UE from sending an unnecessary RAC request". `checkRAC()`
(line 850) then decrements that timer and returns, so a UE whose BSR goes
ungranted cannot retry for the full `retxBsrTimer`.

**The default is not standards-legal.** Verified against the primary document,
not a mirror: ETSI TS 136 331 v19.4.0 (3GPP TS 36.331, "E-UTRA; Radio Resource
Control (RRC)"), clause 6.3.2 `MAC-MainConfig`, ASN.1 extracted directly from
`ts_136331v190400p.pdf`:

```
RetxBSR-Timer-r12    ::= ENUMERATED { sf320, sf640, sf1280, sf2560, sf5120,
                                      sf10240, spare2, spare1}
PeriodicBSR-Timer-r12 ::= ENUMERATED { sf5, sf10, sf16, sf20, sf32, sf40,
                                      sf64, sf80, sf128, sf160, sf320, sf640, ... }
```

`LteMacUe.ned:35` sets `retxBsrTimer = default(40)`. **40 subframes is a legal
`periodicBSR-Timer` value and an illegal `retxBSR-Timer` value** — the legal
minimum is sf320. Simu5G's own NR stack already uses the legal minimum:
`NrMacUe.ned:27` sets `retxBsrTimer = default(320)`. Our pilot runs the LTE
stack, so it inherited 40. No Simu5G example `.ini` sets this parameter.

**No value fixes it; the legal ones are worse.** CondHealthy, ref arm, 30
seeds each, fraction of delivered alerts with e2e delay ≥ 0.5 s:

| `retxBsrTimer` | 3GPP-legal | alerts ≥ 0.5 s |
|---|---|---|
| 40 (Simu5G LTE default) | **no** | 11.1 % |
| 320 (legal minimum, Simu5G NR default) | yes | 17.1 % |
| 640 | yes | 21.9 % |
| 2560 | yes | 25.7 % |

Monotone in the timer, exactly as the mechanism predicts: one ungranted BSR
costs one full timer. A single-seed sweep is misleading here and was corrected
— at seed 3 alone the tail appears only at 20 and 40 and vanishes at 320,
which is an alignment coincidence, not a fix.

**Consequence, and it is a declared limitation rather than a fix.** In any
standards-legal configuration this model puts a floor of 320 ms on the
empty-buffer alert tail. Real LTE/NR does not, because a real UE raises a
Scheduling Request on PUCCH and is granted in roughly 5–10 ms. So:

- The **sign** of the Gate A effect is sound and corresponds to a real
  phenomenon — a backlogged UE skips re-acquisition, an idle one pays it.
- The **magnitude** in our rig is inflated by one to two orders of magnitude
  by the missing PUCCH/SR path, so it must not be quoted as a network result.
- Absolute alert latency and any deadline scored against it (the unsourced 5 s
  alarm budget included) are **not reportable as physical latencies** from this
  model. Arm-to-arm contrasts remain usable, since the path is common to all
  arms, but they must be reported with this limitation stated.

Do not try to "fix" this by choosing a timer. Choosing one is a lottery — 40 is
both illegal and the most flattering value in the range, and every legal value
is worse. The defect is a missing mechanism, so the fix is to supply it.

### A.4 (resolved same day) — the missing mechanism was added

**Status: ✔ fixed in the model, not declared as a limitation.**

`patches/simu5g-scheduling-request.patch` adds the Scheduling Request path to
our Simu5G fork (`LteMacUe.{ned,h,cc}`, 43 insertions / 2 deletions). Two new
parameters, both sourced from the primary specifications:

| Parameter | Value used | Source |
|---|---|---|
| `srPeriod` | 5 TTIs | TS 36.213 Table 10.1.5-1, `sr-ConfigIndex` 0–4 — read from ETSI TS 136 213 V19.5.0 (2026-09), 3GPP TS 36.213 v19.5.0 Rel-19. Full set: 5/10/20/40/80 ms for indices 0–154, 2 ms for 155–156, 1 ms for 157. |
| `srProhibitTimer` | 0 (SR periods) | TS 36.331 cl. 6.3.2, `sr-ProhibitTimer-r9 INTEGER (0..7)` — legal, and means no prohibit. |
| `retxBsrTimer` | 320 TTIs | TS 36.331 cl. 6.3.2 legal minimum `sf320`, now serving its actual purpose as the slow backstop rather than as the only re-request path. |

The RAC gate becomes `srPeriod * (srProhibitTimer + 1)` TTIs when `srPeriod > 0`.

**Backward compatibility verified, not asserted.** `srPeriod` defaults to 0,
restoring stock behaviour. Full `scalar`/`statistic`/`field` diff of a pre-patch
corpus run against the post-patch binary in legacy mode (CondHealthy/ref/seed 3,
`srPeriod=0 retxBsrTimer=40`): **zero lines removed, zero added** — byte-identical.
The legacy path still reproduces the pathological `1.009952311335 s` exactly.

**Effect of the fix** on the same diagnostic cell: alert e2e delay
**1.009952 s → 0.016035 s**. Grant re-acquisition now costs at most one SR
period plus the grant round, which is the right order for LTE/NR.

Consequently the earlier conclusion is **withdrawn**: absolute alert latency is
now reportable, and the 5 s alarm budget can be scored against it — once that
budget is itself sourced, which is a separate open item. What must still be
disclosed is the patch itself, as a modification to a third-party simulator.

Results before 2026-11-08 used `retxBsrTimer=40` with no SR path; their absolute
alert latencies are superseded, not comparable. Arm-to-arm contrasts from that
corpus remain valid, since the path was common to all arms.

---

## B. Application and traffic

| Parameter | Current | Source | Status |
|---|---|---|---|
| Camera → edge frame rate | 2 Hz | rPPG needs 20–30 fps | **✘✘** see A.1 |
| Camera payload | 4 \| 60 KiB | 65.5 kb/s and 983 kb/s sit inside `ehealth_qos` Tables 2–3 video bands (32–384 kbps; 384 kbps–1.544 Mbps) | **✔** as a bitrate anchor |
| Wearable vitals | 512 B, exp(1 s) | none | **✘** |
| OBD-II context | 256 B, exp(2 s) | none | **✘** — OBD-II PID poll rates are documented; use them |
| Alarm payload | 128 B | none | **✘** — eCall's MSD is a defined size; use it as the anchor |
| Alarm rate | exp(300 s) | chosen for exposure, not realism | **~** stated as a sampling device, which is honest |
| Vitals / camera deadline | 10 s | attributed to `ehealth_qos`, which gives 250–300 ms and no figure for non-real-time tele-monitoring | **✘✘** see `PLAN_2026-11.md` §3 |
| Alarm deadline | 5 s | none | **✘** — should come from emergency-response literature, and the escalation claim rests on it |
| Edge processing | U(0.5,2) / U(2,8) ms | none | **✘✘** see A.2 |

## C. Mobility

| Parameter | Current | Source | Status |
|---|---|---|---|
| Headline corridor speed | constant 55 km/h, straight line | none | **✘** |
| Factorial speeds | 30 / 55 / 80 / 105 | none | **✘** |
| Case-study motion | SUMO over OSM | real road geometry | **✔** |

**The fix is structural, not a citation hunt.** Do not look for a "US average
driving speed" to plug in — drive real roads. SUMO over OpenStreetMap takes
speed from OSM's posted `maxspeed` tags and produces the actual speed profile
through a validated car-following model, including acceleration, intersections
and stops. The provenance then becomes "posted limits on real roads, driven by
a calibrated model", which is stronger than any single average.

Checked and set aside: FHWA Highway Statistics Table VM-1 gives vehicle-miles
by road class, **not speeds**, so it cannot source a speed distribution. HPMS
carries speed fields and would be the fallback if a distributional claim is
needed.

## D. Radio

| Parameter | Current | Source | Status |
|---|---|---|---|
| Path loss | 3GPP UMa / RMa-LOS | TR 36.814, TR 38.901 | **✔** |
| Shadowing / fading | log-normal 3GPP σ / Jakes | 3GPP | **✔** |
| Tower positions | OpenCellID LTE, clustered to sites | crowdsourced; FCC ASR cross-check | **✔** with stated bias |
| Coverage sampling frame | OpenCellID anchors | biased to well-covered areas; censored by anchor-centring | **~ → FCC BDC** |
| UE transmit power | 26 dBm | **inherited from Simu5G's own example configs**, which set `**.ueTxPower = 26dBm`. TS 36.101's default is Power Class 3 = **23 dBm** | **✘✘** 3 dB optimistic, and provenance is "the tutorial said so" |
| eNodeB transmit power | 40 dBm | **not** a Simu5G example value either: `nr/standalone_multicell` uses `eNodeBTxPower = 46dBm` (checked 2026-11-06). So ours matches neither the standard nor the tutorial | **✘** |
| Bandwidth | 25 RB (5 MHz) | a choice; US LTE deployments commonly 10–20 MHz | **✘** and conservative |
| Target BLER | 4×10⁻³ | **not** a Simu5G default — confirmed again 2026-11-06 in `nr/standalone_multicell`, which uses `targetBler = 0.01`. Ours was deliberately changed and the reason is unrecorded | **✘** find the reason or restore the default |
| Handover | X2, event-driven | 3GPP | **✔** |

On UE power: it shifts every arm equally, so it cancels in all comparisons.
**Disclose, do not re-run** — but state the standard value and the direction of
the bias.

## E. Sensor links

| Parameter | Current | Source | Status |
|---|---|---|---|
| BLE 4.2 DLE, T_CI = 30 ms, p_e = 0.01 | calibrated | ceiling within 1.5 % of published measurements; latency law within 8 % (`gomez2012ble`, `tosi2017ble`) | **✔** |
| 802.11 DCF cycle | parametric | analytic DCF exactly; one published worked example to 1.6 % | **~** one external anchor only; IEEE 802.11-01/055 still unretrieved |
| Sensor-link buffer | 65536 B default | never tuned, and it **sets** the +16.75 pp factorial effect | **✘** must be disclosed as a condition |

---

## F. Priority

1. **A.1 and A.2** — they change the traffic model and the device model, and
   both are cheap to re-source from literature already found.
2. **Vitals and alarm deadlines** — the escalation claim rests on the 5 s
   alarm budget, which has no source at all.
3. **Mobility via SUMO/OSM** — structural, unblocked now that SUMO 1.28 is
   installed (`tools/setup_env.sh`).
4. **FCC BDC sampling frame** — replaces the censored anchor-centred sample.
5. **Disclose** UE power, eNB power, bandwidth, BLER, sensor-link buffer.

### A.5 ✘✘ W = 30 s: the source is real, the number is right, and it does **not** cover the indices the paper needs

Retrieved 2026-11-10 from primary full text. The citation the plan carried as
*presumed* ("a 3,387-subject ultra-short-term HRV study") exists and the sample
size is exact, but two things in the plan's use of it are wrong, and the second
one matters.

**The paper.** Munoz ML, van Roon A, Riese H, Thio C, Oostenbroek E, Westrik I,
de Geus EJC, Gansevoort R, Lefrandt J, Nolte IM, Snieder H. *Validity of
(Ultra-)Short Recordings for Heart Rate Variability Measurements.* **PLOS ONE
10(9): e0138921, 2015-09-28**, doi `10.1371/journal.pone.0138921`. Open access;
full text retrieved via the Europe PMC REST API (`PMC4586373/fullTextXML`)
because PMC's web front end serves a bot challenge. Metadata cross-checked
against Crossref.

**Correction 1 — the cohort.** Not Lifelines. The subjects are from the
**PREVEND** study (Prevention of Renal and Vascular End-stage Disease),
Groningen, Netherlands: **N = 3,387**, mean age 53 (range 44.8–63.2), 51 %
women, measured **supine** in a quiet room at 22 °C, breathing spontaneously,
not talking or moving. (Lifelines appears in adjacent work by overlapping
authors, which is presumably where the mix-up came from.)

**Correction 2 — the scope, and this is the one that bites.** The study
measures **only two time-domain indices, SDNN and RMSSD**, against a 240–300 s
gold standard, at 10 s (×3), 30 s and 120 s. Its own words:

> "Unlike other studies [8–11] that also measured frequency domain HRV
> parameters such as the high frequency (HF) component we limited our study to
> time domain parameters RMSSD and SDNN. **This was because ECGs of less than
> 60s duration are not sufficient to assess the HF components and ECGs of at
> least 120s should be used to address the low frequency components** [1–3].
> **Therefore our conclusions do not apply to HRV parameters in the frequency
> domain.**"

What it does conclude:

> "Even a single 10s (standard ECG) recording yields a valid RMSSD measurement,
> although an average over multiple 10s ECGs is preferable. **For SDNN we would
> recommend either 30s or multiple 10s ECGs.**"

Reported agreement with the gold standard (Pearson r): single 10 s 0.758–0.764
(SDNN) / 0.853–0.862 (RMSSD); Avg10s 0.863 / 0.941; 120 s 0.956 / 0.986.
Raw means by window (Table 3): SDNN 25.87 (Avg10s) → 29.14 (30 s) → 33.96
(120 s) → 35.81 (total); RMSSD 28.17 → 28.22 → 29.15 → 29.48.

**Consequence for the evidence ladder (`PLAN_2026-11.md` §7).**
`W = 30 s` is **supported for SDNN, and more than sufficient for RMSSD** — but
C1's variability case rests on Cerina et al.'s Table 7, which includes
**LF/HF**, a *frequency-domain* index. By this paper's own cited basis, HF needs
**≥ 60 s** and LF needs **≥ 120 s**. So:

| What the server must recompute | Defensible W | E2 size |
|---|---|---|
| RMSSD only | 10 s | ≈1.2 KiB |
| SDNN (and RMSSD) | **30 s** — as the plan has it | **3.5 KiB** |
| + HF | ≥ 60 s | ≈7 KiB |
| + LF, LF/HF (what C1 actually uses) | **≥ 120 s** | **≈14 KiB** |

**The design rule survives, and comfortably.** Even at W = 120 s, waveform
verification is ≈14 KiB — still **4× smaller than one JPEG (E3, 56 KiB)** and
10× smaller than E4, and still on the free side of the measured step
(`VERIFICATION_FRONTIER.md` §3). But the paper must state **which W, for which
index**, and 14 KiB falls *between* the two measured rungs E2 (3.5 KiB) and E3
(56 KiB), so a claim about it is an interpolation until an E2′ = 14 KiB arm is
run (4 conditions × 30 seeds = 120 runs). **Do not write "3.5 KiB" next to a
claim about LF/HF.**

### A.6 ✔ The alarm budget is now sourced, and the sourced value is 4 s, not 5 s

Retrieved 2026-11-10 from primary text. **ETSI TS 122 101 V19.4.0 (3GPP TS
22.101), clause A.27.2**, "Requirements for the transfer of eCall MSD in a TS12
call", downloaded from ETSI's `deliver/` tree
(`ts_122101v190400p.pdf`, 146 pp.):

> "The MSD should typically be made available to the PSAP **within 4 seconds**
> measured from the time when end to end connection with the PSAP is
> established"

Same clause, a second figure worth recording: where the serving network does
not support the eCall indicators, PSAP modem discrimination between eCalls and
other TS12 calls "shall not exceed **2 seconds**". MSD size is capped at
**140 bytes** (ETSI TS 126 267 V19.0.0 §3, which also reproduces the TS 22.101
service requirements in §4.2 and Annex A.2).

**Why this is the right anchor.** eCall is the paper's declared comparator
(`PLAN_2026-11.md` §3), so the budget should be eCall's own requirement rather
than a round number. `alarmDeadline = 5s` in the ini was unsourced.

**The span mismatch, stated.** eCall's 4 s starts at *end-to-end connection
established*; this project's `e2eDelayAlarm` starts at **sensor sample
creation** and therefore also contains sensing, the sensor link, edge
processing and connection setup. The project's clock starts strictly earlier, so
**scoring this project's latency against 4 s is conservative** — it charges the
system for work eCall's budget excludes. That direction is the safe one for a
safety claim and is the reason the mismatch is acceptable rather than fatal.

**Effect of switching 5 s → 4 s** (recomputed from
`analysis/escalation_sr/pilot_all.csv.gz`, no new runs; runs whose worst
time-to-verification exceeds the budget):

| condition | E1 | E2 | E3 | E4 |
|---|---|---|---|---|
| CondHealthy | 0/20 | 0/20 | 0/20 | 0/20 |
| CondCongested | 3/30 | 1/30 | **8/30** | 6/30 |
| CondTransient | 5/30 | 9/30 | 14/30 | 14/30 |
| CondOutage | 14/27 | 15/27 | 16/27 | 17/27 |

The E2→E3 seam stays sharp in CondCongested (1 → 8). **It blurs in
CondTransient** (9 → 14 instead of 5 → 14), so at the sourced budget the seam
is clean in one condition and weak in another. The seam's existence does not
depend on the budget — it is visible in the latency *ratios*
(`VERIFICATION_FRONTIER.md` §3) — but its sharpness does, and the paper should
lead with the ratios.

### A.7 ✘✘ A third capacity wall: the edge cannot run the inference at the frame rate the metric requires

**Found 2026-11-11, while pricing M4** — this was not the question being asked,
which is why it is recorded separately rather than buried in §A.2.

C1 derives that PRV-grade inference **must be local**, because 25.5 Mb/s does
not cross a 3 Mb/s cellular uplink or a 0.74 Mb/s wearable radio. That argument
says where the inference cannot go. It does not check whether the place it
*must* go can actually run it.

**The arithmetic.** The edge consumes camera frames — C1 terminates them there —
so per-frame inference cost must fit the frame interval, or the backlog grows
without bound. Against the two measured costs in §A.2:

| Grade | fps | Budget / frame | PC-class 22.73 ms | Embedded 94.27 ms |
|---|---|---|---|---|
| **PRV — what C1 requires** | **60** | **16.67 ms** | **1.36× OVER** | **5.66× OVER** |
| Common HRV figure (§5.1) | 30 | 33.33 ms | fits | 2.83× OVER |
| HR floor (§5.1) | 20 | 50.00 ms | fits | 1.89× OVER |

Sustainable *packet* rates: **PC-class 44.0 /s, embedded 10.61 /s**, which the
960-run campaign confirms to be exactly `1/processingTime`.

**CORRECTED 2026-11-11 — the budget is not the frame interval.**
`EdgeAggregator` is a single-server FIFO that applies `processingTime` to
**every** packet, and the vitals stream shares that server: measured offered
load is **61.5 pkt/s at 60 fps, not 60**. So the sustainable *camera* rate is
≈ **42.5 fps** (PC-class) and ≈ **9.1 fps** (embedded), and the wall is slightly
**closer** than the camera-only arithmetic above implies. The row that mattered
most also needs qualifying: PC-class at 30 fps does fit, but at **ρ = 0.72** —
28 % headroom, 0.18 % of packets already dropped, and a median per-frame
latency of **30.9 ms against 22.73 ms of service**, a third of it queueing.
Details and the measured throughput table: `EDGE_COST_RESULT.md` §2.

> **Neither measured platform sustains PRV-grade sensing, and the embedded one
> does not reach the 20 fps HR floor.** C1 is squeezed from both sides: on these
> numbers, PRV-grade camera sensing is infeasible in the cloud *(link)* **and**
> at this edge *(compute)*.

**Confirmed in the model, not only on paper.** A single CondCongested run at
60 fps with `processingTime = 94.27ms` drops **69,673 of 84,186 packets
(82.8 %)**, forwarding only 14,513 of 82,083 camera frames, with
`queueBytes:timeavg` at 49 kB. The queue does exactly what the arithmetic says.
Reproduced across the 960-run campaign's 120 runs per cell.

**And the wall degrades sensing, not just latency.** At 60 fps on embedded
hardware the edge forwards 14,521 of 84,227 packets, so the pipeline downstream
sees an effective **10.6 fps**. Asking for PRV-grade sensing on that platform
does not yield degraded PRV — it yields a stream too sparse even for the 20 fps
HR floor.

**Kim & Koo reach the same conclusion by the same route**, which is a useful
independent check: they rejected the Jetson Nano because an operation time
longer than the frame interval accumulates as lag, and sized their own budget
against 30 fps. At 60 fps even their chosen Mini PC is 1.36× over.

### A.7b ✔✔ RESOLVED 2026-11-16 — the rPPG per-frame cost, measured

**The project's one outstanding retrieval is closed.** Liu, Hill, Jiang, Patel &
McDuff, *EfficientPhys: Enabling Simple, Fast and Accurate Camera-Based Cardiac
Measurement*, **WACV 2023, pp. 5008–5017**. Table 4 read from the full text of
`arXiv:2110.04447v2`; venue/pages from the publisher's own BibTeX at
openaccess.thecvf.com. **On-device per-frame latency, quad-core Raspberry Pi 4B,
preprocessing + model (ms):**

| method | pre | model | total |
|---|---|---|---|
| EfficientPhys-C | 0 | 40 | **40** |
| EfficientPhys-T2 | 0 | 40 | **40** |
| EfficientPhys-T1 | 0 | 300 | 300 |
| TS-CAN | 3 | 60 | 63 |
| Dual-GAN | 275 | n/a | >275 |
| POS | 0 | 27 | **27** |
| CHROM | 0 | 28 | 28 |
| ICA | 0 | 31 | 31 |

> **Not one of the eight meets the 16.67 ms that 60 fps allows.** Fastest of any
> kind (POS) is **1.62× over**; fastest learned model is **2.40× over**. Against
> the 20 fps HR floor (50 ms) all but TS-CAN and the two slow outliers fit.

**What this changes.** The wall is **real but closer than we reported**: 1.62×,
not the 5.66× the extrapolated embedded figure implied. The paper now states the
margin instead of implying a wide one, and lists this as a constraint hardware
progress could plausibly cross — unlike the 8.5× and 34.6× link constraints.

**What it does not change.** Kim & Koo's 22.73 / 94.27 ms stay, because they are
the two device classes the 960-run campaign actually swept. The measured rPPG
cost (40 ms) falls **between them**, so that campaign's invariance result
brackets the real pipeline. They remain labelled as an extrapolation everywhere.

**Still open:** one board, CPU implementations. An accelerator or a quantised
model would move these numbers.

---

**The caveat, and it is the load-bearing one.** Kim & Koo measure a **blink-based
drowsiness pipeline** — face detection, landmarks, temporal blink analysis — not
**rPPG PRV extraction**. Using their per-frame cost as the rPPG cost is an
extrapolation, in the same family as C1's one acknowledged extrapolation
(Cerina's supine subjects standing in for a driver). So:

- The wall's **existence** is well supported: *some* per-frame cost applies, and
  the only measured values available exceed the 60 fps budget.
- The wall's **position** is not settled, because an rPPG-PRV per-frame cost has
  not been retrieved. It could be cheaper than blink detection (no landmark
  tracking) or dearer (longer temporal windows, spectral estimation).
- **Closing it needs a measured per-frame cost for an rPPG-PRV pipeline.** This
  project will not invent one. Until then the paper states the wall as
  conditional on the only measurement in hand, and says exactly that.

**What it does to the paper.** This strengthens C1 rather than threatening it —
C1's claim is about *requirements versus capacities*, and this adds a third
capacity, derived the same way, from a measured number. It also sharpens the
sequel already recorded in `PLAN_2026-11.md` §15: if the edge cannot run
PRV-grade rPPG in real time, the interesting question is what grade it *can*
run, which is a detection-accuracy-versus-compute frontier and a second paper.

## G. Still to source

Wearable sampling and transmission rates; OBD-II PID poll rates; eNodeB power
and bandwidth for a representative US macro deployment; Simu5G's BLER default
provenance.

**Closed 2026-11-10:** eCall MSD size (140 B, TS 126 267 §3) and the alarm
budget (4 s, TS 122 101 cl. A.27.2) — both §A.6. W = 30 s is **sourced but
re-scoped**, §A.5: valid for SDNN, insufficient for LF/HF. Edge processing is
sourced at two points, §A.2, and its effect measured over 960 runs, §A.2
(2026-11-11).

**The one outstanding retrieval:** a measured **per-frame cost for an rPPG-PRV
pipeline**. It is what settles the position — not the existence — of the third
capacity wall, §A.7. This is a newly opened question, not an old presumption.

**Opened 2026-11-11:** a **per-frame cost for an rPPG-PRV pipeline**. §A.7 shows
a compute wall at 60 fps using a blink-detection pipeline's cost as a stand-in;
the wall's position cannot be settled without the right measurement. This is now
the project's one outstanding retrieval, and it is a *new* one rather than an
old presumption.

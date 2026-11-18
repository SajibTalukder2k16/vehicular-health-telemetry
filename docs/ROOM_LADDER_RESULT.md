# The indoor control: the delivery failure is the uplink, not the policy

**300 runs, 2026-11-18.** `simulations/room/results_room_ladder/`, driver
`tools/room_ladder.sh`. Two WLAN bands × five evidence rungs × 30 seeds.

## 1. Why this run exists

The paper measures that **16–49 % of emitted escalations never deliver
complete evidence** at E4. All four conditions are cellular. A reader can
reasonably ask whether that is a property of *the architecture* — of demanding
whole payloads before acting — or of *the mobile uplink* those four conditions
share. Nothing in the paper answered it.

The v05 indoor arm could not be reused. `simulations/room/omnetpp.ini` sets no
`evidenceBytes` at all, runs the camera at 2 Hz, and predates
`cameraTerminatesAtEdge`. So this is a re-run, not a re-analysis.

**The control:** the sensor rig is identical — wearable on BLE, camera on a
wired link, both delivering to the edge device, which forwards over the
backhaul to the server. Ladder, 60 fps camera at 53,167 B/frame, edge service
time `uniform(0.5ms, 2ms)` and per-PDU error rate 0.01 all match the cellular
campaign (verified in the run's own parameter record).

⚠ **Three things differ, not one.** An earlier version of this document and of
the paper said the backhaul was the only difference. It is not:

| | cellular ladder | indoor control |
|---|---|---|
| backhaul | LTE | 802.11n / 802.11ac |
| competing traffic | 4–20 background UEs per cell | **none** |
| observation window | 320–1369 s | 300 s |

The first two are both properties of the indoor setting, so the control
localises the failure to the mobile cellular setting **as a whole**. It does
not separate radio capacity from contention.

> **This was addressed on 2026-11-18**, by running a stationary, unloaded
> cellular arm over the same 300 s window so that all three differences could
> be taken one at a time. `docs/INDOOR_BACKHAUL_RESULT.md` §3 has the
> decomposition; read it before quoting anything below as a cause.

## 2. Result: completion is total, at every rung

| condition | E1 | E2 | E3 | E4 |
|---|---|---|---|---|
| 802.11n, 2.4 GHz | 100.0 % | 100.0 % | 100.0 % | **100.0 %** |
| 802.11ac, 5 GHz | 100.0 % | 100.0 % | 100.0 % | **100.0 %** |

35 bursts per cell, 1,400 bursts in all, **not one incomplete**. Against
51.4–83.8 % on cellular at the same rung.

## 3. Result: the gap is an order of magnitude smaller

Medians over escalations, seconds. `gap` is conditional on completion, which
indoors is every escalation.

| condition | arm | alert | gap | dispatch |
|---|---|---|---|---|
| 2.4 GHz | ref | 0.0013 | 0.0000 | 0.0013 |
| | E1 | 0.0013 | 0.0004 | 0.0017 |
| | E2 | 0.0013 | 0.0014 | 0.0027 |
| | E3 | 0.0013 | 0.0194 | 0.0207 |
| | **E4** | 0.0013 | **0.0464** | 0.0475 |
| 5 GHz | ref | 0.0013 | 0.0000 | 0.0013 |
| | E1 | 0.0013 | 0.0003 | 0.0016 |
| | E2 | 0.0013 | 0.0010 | 0.0023 |
| | E3 | 0.0013 | 0.0145 | 0.0160 |
| | **E4** | 0.0013 | **0.0350** | 0.0362 |

E4 costs **35–46 ms** indoors against **192–458 ms** on cellular.

> **The conclusion the paper needed.** Requiring complete evidence is not, by
> itself, expensive. Over a backhaul with capacity and no coverage loss, the
> full 138 kB burst completes every time and costs tens of milliseconds. The
> 16–49 % failure is a property of **the delivery path**, not of the policy.
>
> ⚠ **AMENDED 2026-11-18.** This box read "a property of **the mobile
> uplink**". That was as precise as this campaign could be, and it is now
> superseded: with mobility, load and window matched, the failure to deliver
> at all tracks **coverage loss** specifically (p = 0.0009), while mobility
> and moderate load are not distinguishable (p = 0.480). "Mobile" was doing
> work the evidence did not support. See `docs/INDOOR_BACKHAUL_RESULT.md` §3.

## 4. Predictions, scored

Recorded in `tools/room_ladder.sh` before the run.

| | prediction | outcome |
|---|---|---|
| **P1** | completion > 95 % at E4 in both bands | ✔ **100.0 %**, stronger than predicted |
| **P2** | gap at E4 of order tens of ms (~37 ms) | ✔ **35.0 ms** at 5 GHz, within 6 % of the estimate; 46.4 ms at 2.4 GHz |
| **P3** | C2′ holds in direction, compressed | ✔ as stated — the gap grows 0 → 46 ms while the alert stays flat |
| **P4** | the two bands indistinguishable | ✘ **WRONG** |

**P4 is the informative one.** The bands differ consistently: 46.4 vs 35.0 ms
at E4, 19.4 vs 14.5 ms at E3 — about 1.3×, in the direction the nominal rates
predict. v05 found them indistinguishable, but on a *timeliness* metric against
a 10 s budget, where both scored 100 %. A metric that saturates cannot
distinguish two links; this one can. The earlier finding was a property of the
old metric, not of the radios.

**Also unpredicted:** the alert is *perfectly flat* at 1.3 ms across the whole
ladder.

> ⚠ **CORRECTED 2026-11-18.** This paragraph previously continued: *"where on
> cellular it falls as evidence grows. The 'alert gets faster' effect is
> therefore specific to cellular grant acquisition."* **That attribution was
> an overstatement and is withdrawn.** Checking the alert across all four
> cellular conditions (`docs/INDOOR_BACKHAUL_RESULT.md` §5) shows it is flat
> in `CondHealthy` across E1→E4 and varies by a few milliseconds without a
> clear trend in `CondCongested` and `CondTransient`. The large fall is
> **`CondOutage` only**, and is not monotone even there. A stationary,
> unloaded *cellular* arm (`CondIndoorLte`) has a flat alert too, at 15.7 ms —
> so being cellular is not what causes it. The effect is a coverage-outage
> phenomenon plus a ref→E1 step, not a general consequence of grant
> acquisition. Nothing in the paper claimed the broader version.

## 5. What this does not establish

1. ~~**WLAN against LTE confounds access technology with mobility and
   coverage.**~~ **RESOLVED 2026-11-18** by `CondIndoorLte`, a stationary,
   unloaded *cellular* arm over the same 300 s window — see
   `docs/INDOOR_BACKHAUL_RESULT.md` §3. With mobility, load and window
   matched, the backhaul step alone costs ×3.78 in gap (p = 1.5 × 10⁻⁷) while
   mobility and load together are not distinguishable (p = 0.156), and the
   completion collapse is driven specifically by losing coverage (p = 0.0009).
   **So the diagnosis below — "the mobile cellular setting as a whole" — is
   superseded and too coarse.** The step still compares two networks rather
   than two access technologies in isolation; that residual is stated there.
2. **One room geometry**, 10 m, one AP, no competing stations inside the model.
3. **35 escalations per cell** over a 300 s window — thin, comparable to
   `CondHealthy`. Enough for a 100 %/0 % contrast, not for fine comparison.
4. ~~**The camera is on a wired sensor link here.**~~ **RESOLVED 2026-11-18**
   by `tools/room_wifi_ladder.sh`: on a quiet medium the WLAN carries the
   PRV-grade camera with **zero** drops, and at 80 % busy it drops **75.95 %**
   of frames against a 75.8 % derivation — while the escalation path stays
   identical to four decimals. `docs/INDOOR_BACKHAUL_RESULT.md` §2.

## 6. Provenance

```sh
sh tools/room_ladder.sh          # 300 runs, ~90 s on 12 jobs
python3 -I tools/analyze_room_ladder.py simulations/room/results_room_ladder
```

The analysis tool was added on 2026-11-18. Every table in this document was
originally produced inline, which is why this section could at first name only
the driver; the tool reproduces them exactly, and that reproduction is what
validated it before it was used on the two new campaigns.

The room network names its server `cloud`, not `server`, so the pilot ini's
selective `vector-recording` block does not match it. Without the two
overrides in the driver, every run completes and records **zero** escalation
samples. Verified on a smoke run before launching: 0 samples without them,
200 with.

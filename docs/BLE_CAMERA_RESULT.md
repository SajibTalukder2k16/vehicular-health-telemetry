# A Bluetooth camera indoors: the largest C1 margin, and a cliff

**450 runs, 2026-11-18.** Driver `tools/room_ble_ladder.sh`, corpus
`simulations/room/results_room_ble/`. Companion to
`docs/INDOOR_BACKHAUL_RESULT.md`, which covers the wired and WLAN sensor
links and the backhaul decomposition.

---

## 1. Why this run exists

The wearable is on BLE in **every** configuration in this project, and that is
the realistic choice: body-worn sensors are overwhelmingly Bluetooth. So the
natural question is whether the camera can be Bluetooth too, making the whole
rig one radio technology.

C1 says no at PRV grade, by the **largest margin in its table** — and that
margin had never been measured. This campaign measures it, and then asks the
two follow-on questions that matter more:

| part | question | runs |
|---|---|---|
| **A** | the evidence ladder with the camera on BLE, comparable to the wired and WLAN arms | 150 |
| **B** | *which* camera does BLE actually carry? | 150 |
| **C** | if the camera and wearable shared one radio, what would the vitals stream need? | 150 |

### The ceiling, derived before measuring it

From `src/links/BleLink.cc`'s connection-event loop with the NED defaults:
app bytes per PDU $= 251 - 7 = 244$; air bytes $= 244 + 7 + 10 = 261$;
PDU time $= 261 \times 8 / 1\,\mathrm{Mbps} + 2 \times 150\,\mu s + 80\,\mu s =
2{,}468\,\mu s$; a 30 ms connection interval fits
$\lfloor 30000/2468 \rfloor = 12$ PDUs, so $12 \times 244 = 2{,}928$ B per
interval $= \mathbf{0.781\ Mb/s}$ theoretical.

`docs/BLE_VALIDATION.md` measures **0.737 Mb/s**. The 5.6 % shortfall is PDU
quantisation on a message's last fragment, so the **effective ceiling depends
on message size**. Measured here: **0.762 Mb/s** for 4 KiB frames and
**0.744 Mb/s** for 53,167 B frames. Anywhere the paper quotes a single BLE
number it should say which.

---

## 2. Part A: the PRV-grade camera fails, as C1 says

Camera at 53,167 B and 60 fps, i.e. 25.5 Mb/s offered.

| | frames offered | dropped | drop rate | delivered |
|---|---|---|---|---|
| camera on BLE | 17,969 | 17,443 | **97.07 %** | 0.744 Mb/s |

The 2.93 % that gets through delivers **0.744 Mb/s**, which is the link
ceiling. ⚠ **These are measured delivered rates, counted from transmission
completions** (`linkDelay` fires only when a message clears the link), not
`offered × (1 − dropped/sent)` — that subtraction counts a frame still queued
at termination as delivered and reads 0.747 here. Raised by external review;
see `docs/INDOOR_BACKHAUL_RESULT.md` §8e. The queue sits at 52,415 B of 65,536 B. So C1's BLE row
is confirmed: a PRV-grade stream is **34.1×** beyond what BLE carries, the
largest of the eight constraint margins.

### 2a. The escalation path is untouched — and that is NOT a finding

| camera sensor link | completion | E4 gap | alert |
|---|---|---|---|
| wired | 100.0 % | 0.0350 | 0.0013 |
| WLAN, quiet | 100.0 % | 0.0350 | 0.0013 |
| WLAN, 80 % busy | 100.0 % | 0.0350 | 0.0013 |
| **BLE (97 % dropped)** | **100.0 %** | **0.0350** | **0.0013** |

> ⚠ **Do not read this row as evidence that a Bluetooth camera is harmless.**
> It is a property of the model's structure. `src/nodes/SensorRig.ned` gives
> the camera its own `BleLink` instance, separate from `bleWearable`, and the
> alarm is **edge-generated**: line 68 is `alarm.out --> edge.in++`, with no
> sensor-link hop at all. So a saturating BLE camera **cannot** delay the
> alert here by construction.
>
> It is a useful consistency check — it confirms raw frames terminate at the
> edge and the three sensor links are otherwise interchangeable — and it is
> nothing more than that. Part C is the attempt to say something real about
> the shared-radio case.

---

## 3. Part B: which camera *does* BLE carry?

"BLE cannot carry the camera" is true at PRV grade and false in general. The
useful answer is where the boundary is.

| frame | fps | offered | dropped | accepted | **delivered** |
|---|---|---|---|---|---|
| 53,167 B | 60 | 25.52 Mb/s | 97.07 % | 0.747 | **0.744** |
| 53,167 B | 2 | 0.85 Mb/s | 49.96 % | 0.426 | **0.424** |
| 4 KiB | 60 | 1.97 Mb/s | 61.09 % | 0.765 | **0.762** |
| 4 KiB | 30 | 0.98 Mb/s | 22.20 % | 0.765 | **0.762** |
| **4 KiB** | **10** | **0.33 Mb/s** | **0.00 %** | 0.328 | **0.327** |

`accepted` is the `offered × (1 − dropped/sent)` estimate; `delivered` is
counted from transmission completions. The estimate is high by ≤ 0.06 % here,
so the distinction changes no conclusion — but it is the same distinction §4
insists on for the wearable, and it should not have been applied to one and
not the other.

**A 4 KiB camera at 10 fps fits, losing nothing at all.** Saturated goodput is
0.762 Mb/s, so at 4 KiB the feasible frontier is
$0.762 \times 10^6 / (4096 \times 8) = \mathbf{23.3\ fps}$ — consistent with
22.2 % loss measured at 30 fps and zero at 10.

### 3a. Large frames waste the link

The `53{,}167\,B @ 2\,\mathrm{fps}` row is the interesting one. It offers
0.85 Mb/s — barely above the ceiling — yet delivers only **0.426 Mb/s**, well
*below* the 0.747 the same frame size reaches at 60 fps. Almost exactly half
the frames are lost.

The cause is buffer granularity, not capacity. The queue is 65,536 B and a
frame is 53,167 B, so it holds **one** frame. A frame takes
$53167 \times 8 / 0.765\,\mathrm{Mb/s} = 556$ ms to clear, while the next
arrives after 500 ms — so every second frame meets a full buffer and is
dropped whole, and the link then idles.

> **BLE's usable camera envelope is not one number.** It is ~0.765 Mb/s *and*
> frames small enough that a 64 KiB buffer can smooth them. A 53 kB frame
> violates the second condition even when it satisfies the first.

---

## 4. Part C: the shared radio, and a cliff at a derivable threshold

Parts A and B cannot say what happens when the camera and wearable share one
radio, because the model gives them separate links. `maxCiUtilization` — the
usable fraction of the connection interval — is the term that represents a
share, so sweeping it on `bleWearable` **bounds** the risk instead of ignoring
it. This is a sensitivity bound, not a measurement of contention.

| `maxCiUtilization` | budget | vitals dropped | **vitals delivered** |
|---|---|---|---|
| 1.00 | 30.00 ms | 0.00 % | 308 |
| 0.50 | 15.00 ms | 0.00 % | 308 |
| 0.20 | 6.00 ms | 0.00 % | 308 |
| 0.05 | 1.50 ms | 57.53 % | **0** |
| 0.01 | 0.30 ms | 57.53 % | **0** |

**This is a cliff, not a degradation.** And note what the drop column does:
it reads 57.53 %, while delivery is **zero**. The missing 42.5 % are stranded
in the queue forever — 301 messages of 512 B offered, 65,536 B of buffer holds
128, the other 173 are dropped at the door. Scoring this arm on drop rate
would report a 57 % problem where the true answer is total failure. That is
the same metric trap as `maxAge = 0.5 s` in `docs/COMPLETION_RESULT.md` §5a.

### 4a. The threshold is exactly one PDU

A PDU costs 2,468 µs, so if the budget is below that, the loop's
`if (used + pduTime > budget) break;` fires with `used = 0` and **nothing ever
transmits**. The predicted threshold is $2468/30000 = 0.08227$. A fine sweep,
three seeds each:

| `maxCiUtilization` | 0.15 | 0.10 | 0.0830 | **0.0823** | **0.0820** | 0.0750 |
|---|---|---|---|---|---|---|
| budget (ms) | 4.50 | 3.00 | 2.49 | **2.47** | **2.46** | 2.25 |
| vitals delivered | 926 | 925 | 925 | **925** | **0** | 0 |

The cliff falls between 0.0823 and 0.0820 — between a budget of 2.47 ms and
2.46 ms, against a derived PDU time of 2.468 ms. The derivation is confirmed
to three decimal places.

> **The design rule.** A BLE wearable needs at least one PDU time per
> connection interval — $8.23\%$ of a 30 ms interval here — or it delivers
> **nothing**. There is no graceful degradation and no warning in the drop
> statistics. If a Bluetooth camera is greedy enough to push the wearable
> below that share, the vitals stream that triggers detection stops entirely.

That is the honest answer to "can the camera be Bluetooth too?": at PRV grade
it cannot work at all, at low rate it can, and in either case the wearable's
share of the radio is a hard floor rather than something to be traded off.

---

## 5. Predictions, scored

| | prediction | outcome |
|---|---|---|
| **P1** | BLE camera drops 96–98 % at PRV grade | ✔ **97.07 %** |
| **P2** | completion 100 %, E4 gap 0.0350 s | ✔ — but structural, and §2a says so rather than claiming it |
| **P3** | 4 KiB @ 10 fps fits; the ini's "documented-infeasible" label is wrong | ✔ **zero drops**; label corrected |
| **P4** | 4 KiB @ 60 fps ≈ 60 % drops; frontier 20–25 fps | ✔ **61.09 %**; frontier **23.3 fps** |
| **P5** | no vitals loss until `maxCiUtilization` < ~0.05 | ✘ the cliff is at **0.0823** |

**P5 is wrong and the error is instructive.** I guessed a threshold from the
vitals stream's *bandwidth* need (512 B/s against 0.765 Mb/s — about 0.5 %,
hence "0.05 should be safe"). But the binding constraint is not bandwidth, it
is **whether a single PDU fits in the budget**, which is 16× higher. A
BLE link's floor is set by quantisation, not by throughput.

**P3 is the one worth noting separately**: it predicted that a label in this
repository was wrong, and it was. `Room5GHzCameraBle` had been described as
"documented-infeasible" since before this pivot, conflating a 4 KiB camera
with a PRV-grade one.

---

## 6. What this does not establish

1. **Contention between the camera and wearable is not modelled.** They have
   separate `BleLink` instances. Part C bounds the consequence of a share; it
   does not simulate two streams competing for one radio, and a real BLE
   scheduler's allocation is not derivable from this.
2. **The alarm is edge-generated** and crosses no sensor link
   (`SensorRig.ned:68`), so no sensor-link result here can speak to alert
   latency. In a real deployment detection depends on vitals arriving over
   BLE, which Part C shows is the fragile part.
3. **One connection interval (30 ms) and one PHY (1 Mbps).** The 2 Mbps PHY
   and shorter intervals would move every number; the *form* of the cliff
   (one PDU must fit) would not.
4. **`maxCiUtilization` is a parametric share**, like `mediumBusyFraction` for
   the WLAN. It is not a population of contending devices.
5. **35 escalations per cell** in Part A, the same thin cells as the other
   indoor campaigns.

---

## 7. Provenance

```sh
sh tools/room_ble_ladder.sh      # 450 runs, ~18 s on 12 jobs
python3 -I tools/analyze_room_ladder.py <part-A subset>
```

Part A is analysed by `tools/analyze_room_ladder.py`; Parts B and C are
scalar-only sweeps read directly from the `.sca` files, as §3 and §4 show.

**One driver bug, found and fixed before any number above was believed.** The
throttle was written `[ $((n % J)) -eq 0 ] && wait`, copied from the other
room drivers. Inside a shell function that expression returns 1 whenever the
test is false, which makes the function return 1, which under `set -e` exits
the script — **in 0.02 s, having written 0 runs, printing nothing**. It is now
`if ...; then wait; fi`. Noted because it is the fifth silent failure in this
project and the first in the tooling rather than the model.

Also noted: an early check of this campaign used `grep -cE '^[0-9]+ [0-9]+ '`
to count vector samples and reported zero for a corpus that had 200. OMNeT++
writes `.vec` data lines **tab**-separated. The runs were never empty; the
check was. Any smoke test for recorded samples must use `\s`, not a literal
space.

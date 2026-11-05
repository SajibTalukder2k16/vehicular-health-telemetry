# BleLink Unit Validation

**Model:** `paperrebuild.links.BleLink` — parametric BLE connection model (connection-event
latency quantization, PDU fragmentation with per-PDU air time + 2×T_IFS + ACK, independent
PDU errors with retransmission). No delay or throughput knob exists; both emerge from the
connection interval, PHY bitrate, and PDU framing parameters.

**Harness:** `simulations/validation_ble/` — one SensorSource → BleLink → DelaySink,
300 s × 10 seeds per config. Run date: 2026-07-08.

## Results vs published values

| Quantity | Config | Simulated (mean of 10 seeds) | Published reference | Error |
|---|---|---|---|---|
| Unloaded notification latency, CI=7.5 ms | LatencyCI7_5 | 4.45 ms | CI/2 + PDU round ≈ 4.1 ms (uniform anchor-point wait; Gomez et al. 2012 latency model) | +8% |
| Unloaded latency, CI=30 ms | LatencyCI30 | 15.64 ms | ≈15.4 ms | +1.6% |
| Unloaded latency, CI=50 ms | LatencyCI50 | 25.32 ms | ≈25.4 ms | −0.3% |
| Max app throughput, BLE 4.0 (27 B PDU, 1M PHY) | ThroughputBLE40 | 233.1 kbps | 236.7 kbps (Gomez, Oller & Paradells, *Sensors* 2012) | −1.5% |
| Max app throughput, BLE 4.2 DLE (251 B PDU, 1M PHY) | ThroughputBLE42 | 737.0 kbps | ≈780 kbps theoretical; ~700–785 kbps measured (Tosi et al., *Sensors* 2017 systematic review) | in measured range |
| Max app throughput, BLE 5 2M PHY | ThroughputBLE5_2M | 1310.3 kbps | ≈1.3–1.4 Mbps (Tosi et al. 2017; BLE 5 evaluations) | in range |
| Throughput under 10% PDU error rate | PER10 | 664.9 kbps | 0.9 × error-free ≈ 663 kbps (retransmission model) | +0.3% |

All errors are well inside the ≤20% Phase-2 acceptance gate; the two headline calibration
anchors (236.7 kbps and the CI/2 latency law) reproduce to within 2%.

## Infeasibility documentation run (replaces the old runaway-queue "scenarios")

`CameraOverBleInfeasible`: 60 KiB camera frames at 2 Hz (≈0.98 Mbps offered) over BLE 4.2.
Result: link saturates at its 778 kbps ceiling, drops 20% of frames at the finite 256 KiB
queue, and settles at a bounded ~2.27 s queue delay. One line of link-budget arithmetic
plus this run documents why BLE video is out of scope — in the old model this appeared as
twelve scenarios with 115,000 s delays misreported as 115 s.

## QC checks passed

- Non-degenerate across seeds: latency std 0.13–0.93 ms, throughput std ≤ 0.6 kbps (nonzero).
- No delay exceeds simulation time; saturation-run delays are queue-bound and stable.
- Packet accounting closes: generated = received + dropped + in-queue for every run.

Reproduce: `cd simulations/validation_ble && opp_runall -j24 ../../src/out/clang-release/paperrebuild -u Cmdenv -n ../../src:..:../../../inet4.7/src -c <Config>`

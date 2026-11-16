# Patches to vendored dependencies

Changes this project makes to third-party simulators live here as patches, so
the project repo alone is enough to reproduce a result. The dependency trees
themselves (`../../Simu5G`, `../../inet4.7`) are not part of this repo.

Apply from the dependency's root:

```sh
cd ../../Simu5G
git apply /path/to/PaperRebuild/patches/simu5g-scheduling-request.patch
cd src && make -j8          # needs `source $OMNETPP_ROOT/setenv` first
```

## `simu5g-scheduling-request.patch`

Added 2026-11-08. Touches `src/simu5g/stack/mac/LteMacUe.{ned,h,cc}` only;
43 insertions, 2 deletions.

**What it fixes.** Stock Simu5G models no PUCCH and no Scheduling Request
(`grep -rn "srProhibit\|SchedulingRequest" src/` returns nothing; PUCCH appears
only in `LteAirFrame.msg`). A UE whose uplink buffer has emptied can therefore
re-request resources only through a contention RAC, and `LteMacUe.cc` gates that
RAC on `retxBsrTimer` after any BSR that reported a non-empty buffer. That makes
`retxBSR-Timer` the *only* re-request path, where 3GPP makes it the slow
backstop behind SR:

- SR on PUCCH, prohibited for at most `sr-ProhibitTimer` SR periods —
  TS 36.331 cl. 6.3.2, `sr-ProhibitTimer-r9 INTEGER (0..7)`.
- SR periodicity 5/10/20/40/80 ms (indices 0–154), plus 2 ms and 1 ms —
  TS 36.213 Table 10.1.5-1.
- `retxBSR-Timer` legal minimum **sf320** — TS 36.331 cl. 6.3.2,
  `RetxBSR-Timer-r12 ::= ENUMERATED {sf320, sf640, ...}`.

So stock behaviour overstates grant re-acquisition latency by one to two orders
of magnitude for sporadic small-packet uplink traffic, which is exactly the
alert traffic this project measures. Measured here: an alert travelling alone
took **1.009952 s** end-to-end, of which `rlcDelayUl` was 1.008876 s and
`macDelayUl` 0.004 s, on a cell serving 0.3% of its uplink blocks.

Worse, Simu5G's LTE default is not even a legal value for the timer it names:
`LteMacUe.ned` ships `retxBsrTimer = default(40)`, and 40 subframes is a legal
*periodic*-BSR value but is absent from `RetxBSR-Timer-r12`. Its own NR stack
uses the legal minimum (`NrMacUe.ned`, `retxBsrTimer = default(320)`). And 40 is
the most flattering value in the range — the tail gets monotonically worse at
every legal setting (11.1% of alerts ≥ 0.5 s at 40, 17.1% at 320, 21.9% at 640,
25.7% at 2560), because one ungranted BSR costs one full timer.

**What it adds.** Two NED parameters on `LteMacUe`:

| Parameter | Meaning | Default |
|---|---|---|
| `srPeriod` | SR periodicity in TTIs; `0` disables the SR path | `0` |
| `srProhibitTimer` | `sr-ProhibitTimer`, in SR periods (3GPP 0..7) | `0` |

The RAC gate becomes `srPeriod * (srProhibitTimer + 1)` TTIs when `srPeriod > 0`,
and is left at `retxBsrTimer` when it is `0`.

**Backward compatibility is verified, not asserted.** `srPeriod` defaults to `0`,
which restores stock behaviour exactly. A full `scalar`/`statistic`/`field` diff
of a pre-patch corpus run against the post-patch binary in legacy mode
(`CondHealthy/ref/seed 3`) is **zero lines removed and zero lines added** —
byte-identical. The 19,090 runs already on disk keep their meaning.

**Scope.** `LteMacUeD2D` keeps its own copy of the same gate and is not patched,
because this project's UE is not a D2D UE. `NrMacUe` inherits the new parameters
and is unaffected at the default.

**Disclosure.** This is a modification to a third-party simulator and must be
declared in the paper's methodology, with the patch cited by name.

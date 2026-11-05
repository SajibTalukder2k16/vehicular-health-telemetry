package paperrebuild.apps;

import inet.common.SimpleModule;
import inet.applications.contract.IApp;

// Backhaul uplink app running inside the UE (vehicle) or WiFi host (room).
// Receives processed sensor packets from an EdgeAggregator via sendDirect
// on the 'edgeIn' gate, wraps each in a HealthPayload chunk preserving the
// original sensing timestamp, and sends it over UDP to the cloud server.
simple EdgeApp extends SimpleModule like IApp
{
    parameters:
        @class(EdgeApp);
        string destAddress;
        int destPort = default(5000);
        int localPort = default(-1);
        double startTime @unit(s) = default(0s);
        @display("i=block/app");
        @lifecycleSupport;
        double stopOperationExtraTime @unit(s) = default(-1s);
        double stopOperationTimeout @unit(s) = default(2s);

        // ---- camera admission / pacing gate -------------------------------
        // The gate sits here, before socket.sendTo(), because once a packet is
        // handed to UDP it is committed to the RLC/PDCP queues and the
        // application can no longer reorder or withdraw it. Critical classes
        // (vitals=0, OBD=1, alarm=3) always pass immediately; only the camera
        // class (2) is gated.
        //
        //   none     forward everything on arrival (the original behaviour)
        //   drop     token bucket; a frame with insufficient tokens is
        //            discarded at once -- reduces admitted VOLUME, adds no delay
        //   pace     token bucket; a frame with insufficient tokens WAITS in a
        //            bounded queue -- same target volume, spread over TIME
        //   dropPace pace, plus discard of frames older than cameraMaxAge
        //   prio     alarm first, newest-only state updates, camera through a
        //            FIXED-rate token bucket with staleness discard
        //   adaptive prio, but the bucket rate is adapted from a throughput
        //            estimate alone
        //   ctrl     adaptive, plus a reserve for critical load in the rate
        //   aimd     probe the camera rate UPWARD and back off when the
        //            observed vitals age crosses a target -- capacity is
        //            discovered, not inferred from a throttled measurement
        //
        // The three closed-loop policies control a RATE, not an in-flight
        // window. An earlier window-based design failed: a 61440 B camera
        // frame against a 131072 B window meant two outstanding frames
        // saturated it and head-of-line-blocked the vitals the policy exists
        // to protect, and a window large enough to avoid that implies about
        // ten seconds of queueing at this capacity -- the whole vitals budget.
        // Rate control bounds average load instead of instantaneous backlog,
        // which is why the open-loop token bucket outperformed every
        // window-based policy. The window is still tracked, but only to feed
        // the estimator.
        //
        // drop and pace share cameraRate, so comparing them isolates temporal
        // spreading from volume reduction at a matched admitted workload.
        string admissionPolicy = default("none");
        double cameraRate @unit(bps) = default(1Mbps);        // token fill rate
        int cameraBurst @unit(B) = default(65536B);           // bucket depth
        int cameraQueueCapacity @unit(B) = default(262144B);  // pace queue bound
        double cameraMaxAge @unit(s) = default(2s);           // dropPace staleness

        // ---- feedback-driven policies (prio / adaptive / ctrl) ------------
        // These three are the only ones that use server feedback, and they
        // may use nothing else: no radio queue depth, no true server AoI, no
        // knowledge of future channel state. Unacknowledged bytes are not
        // necessarily bytes still queued -- some may have been delivered
        // without the report arriving yet, or lost -- and handling that
        // uncertainty is part of the problem, not something to assume away.
        int maxInFlight @unit(B) = default(131072B);    // bounded in-flight window
        double horizon @unit(s) = default(1s);          // budget lookahead
        double rateEwmaAlpha = default(0.2);            // throughput estimator gain
        double critReserveFactor = default(1.5);        // ctrl: safety margin on the reserve
        int critQueueCapacity @unit(B) = default(65536B);

        // Fix for the shared-window starvation. Camera may only enter the
        // path if it leaves this many window bytes free; critical traffic may
        // use the whole window. Without it, two 60 KiB frames fill a 128 KiB
        // window and head-of-line-block the vitals the policy exists to
        // protect. Must exceed a few state updates' worth of bytes.
        int cameraHeadroom @unit(B) = default(16384B);

        // Fix for the estimator deadlock. A throughput estimator fed by its
        // own admission decisions cannot discover capacity it never probes:
        // blocking camera lowers measured throughput, which shrinks the
        // budget, which keeps camera blocked. This floor keeps a trickle of
        // camera flowing so the estimate tracks something real. 0 disables
        // it, which reproduces the deadlock.
        double probeRate @unit(bps) = default(80kbps);

        // adaptive / ctrl: the adapted bucket rate is
        //   clamp( rateSafety * (estimated goodput - critical load),
        //          probeRate, cameraRate )
        // so cameraRate becomes the ceiling rather than the operating point.
        double rateSafety = default(0.9);

        // ---- aimd ---------------------------------------------------------
        // The three earlier designs all failed the same way: available
        // capacity cannot be inferred from a signal the policy's own
        // throttling determines, so the rate settles at a stable low point.
        // aimd probes upward instead and backs off on evidence of harm.
        //
        // What makes the harm signal unusual is that it is not the throttled
        // stream's own loss or delay, as in congestion control, but the
        // freshness of a DIFFERENT stream: the age of the newest vitals
        // sample the server has confirmed. The gateway sees that age only
        // through feedback, so it is already stale by the report delay --
        // which is why the target sits well below the clinical budget.
        //
        // aimdSelf is the ablation that tests whether the cross-stream signal
        // is load-bearing: same control law, same parameters, but driven by
        // the camera stream's own age. freshnessTarget applies to whichever
        // stream drives the policy, and the two are not a priori comparable at
        // one value -- camera is generated every 0.5 s against vitals'
        // exponential(1 s), so camera's age floor is LOWER. The shared default
        // is therefore the generous setting for aimdSelf, not a handicap; it
        // is swept separately so the result cannot be a tuning artifact.
        double freshnessTarget @unit(s) = default(5s);
        double probeIncrement @unit(bps) = default(40kbps);
        double backoffFactor = default(0.7);
        @signal[inFlightBytes](type=long);
        @signal[estThroughput](type=double);
        @signal[bucketRate](type=double);
        @statistic[inFlightBytes](title="unacknowledged bytes in flight"; unit=B; record=stats,vector,timeavg; interpolationmode=sample-hold);
        @statistic[estThroughput](title="gateway throughput estimate"; unit=bps; record=stats,vector; interpolationmode=linear);
        // The adapted camera rate itself. Recorded because the aimd/aimdSelf
        // ablation turns on whether the rate climbs or collapses to the probe
        // floor, which a final-value scalar cannot show.
        @statistic[bucketRate](title="adapted camera token rate"; unit=bps; record=stats,vector; interpolationmode=linear);

        @display("i=block/app");
        @lifecycleSupport;
        @signal[packetSent](type=inet::Packet);
        @statistic[packetSent](title="packets sent"; source=packetSent; record=count,"sum(packetBytes)"; interpolationmode=none);
        @signal[cameraAdmitted](type=long);
        @signal[cameraGateDropped](type=long);
        @signal[cameraPendingBytes](type=long);
        @signal[cameraGateDelay](type=simtime_t);
        @statistic[cameraAdmitted](title="camera frames admitted by the gate"; record=count,sum; interpolationmode=none);
        @statistic[cameraGateDropped](title="camera frames dropped by the gate"; record=count,sum; interpolationmode=none);
        @statistic[cameraPendingBytes](title="camera bytes pending in the gate"; unit=B; record=stats,vector,timeavg; interpolationmode=sample-hold);
        @statistic[cameraGateDelay](title="delay added by the gate"; unit=s; record=stats,histogram; interpolationmode=none);
    gates:
        input socketIn @labels(UdpCommand/up);
        output socketOut @labels(UdpCommand/down);
        input edgeIn @directIn;
}

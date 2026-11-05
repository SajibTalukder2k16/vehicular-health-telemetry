package paperrebuild.apps;

import inet.common.SimpleModule;
import inet.applications.contract.IApp;

// Cloud-side sink: receives HealthPayload packets, computes true
// end-to-end delay from the original sensing timestamp, and tracks
// per-stream deadline misses and counts.
simple HealthServerApp extends SimpleModule like IApp
{
    parameters:
        @class(HealthServerApp);
        int localPort = default(5000);
        double alarmDeadline @unit(s) = default(5s);     // clinical alarm delivery budget
        double vitalsDeadline @unit(s) = default(10s);   // vitals freshness budget

        // Periodic feedback to the gateway. 0s disables it, which is the
        // default so existing scenarios are unchanged. The report travels as
        // an ordinary UDP packet, so its delay, loss and bytes are simulated
        // like any other traffic -- the gateway never gets a free channel.
        double feedbackInterval @unit(s) = default(0s);
        int feedbackLength @unit(B) = default(48B);
        @display("i=block/sink");
        @lifecycleSupport;
        double stopOperationExtraTime @unit(s) = default(-1s);
        double stopOperationTimeout @unit(s) = default(2s);
        @signal[feedbackSent](type=long);
        @statistic[feedbackSent](title="feedback reports sent to the gateway"; record=count,sum; interpolationmode=none);
        @signal[e2eDelay](type=simtime_t);
        @signal[e2eDelayVitals](type=simtime_t);
        @signal[e2eDelayObd](type=simtime_t);
        @signal[e2eDelayCamera](type=simtime_t);
        @signal[e2eDelayAlarm](type=simtime_t);
        @statistic[e2eDelay](title="end-to-end delay (all streams)"; unit=s; record=stats,histogram,vector; interpolationmode=none);
        @statistic[e2eDelayVitals](title="end-to-end delay, vitals"; unit=s; record=stats,histogram,vector; interpolationmode=none);
        @statistic[e2eDelayObd](title="end-to-end delay, OBD"; unit=s; record=stats,vector; interpolationmode=none);
        @statistic[e2eDelayCamera](title="end-to-end delay, camera"; unit=s; record=stats,vector; interpolationmode=none);
        @statistic[e2eDelayAlarm](title="end-to-end delay, alarm"; unit=s; record=stats,vector; interpolationmode=none);
    gates:
        input socketIn @labels(UdpCommand/up);
        output socketOut @labels(UdpCommand/down);
}

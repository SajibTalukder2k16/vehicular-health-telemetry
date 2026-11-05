package paperrebuild.nodes;

// Edge device compute stage: a single-server queue with a finite byte
// buffer (drop-tail) and a per-packet processing time distribution that
// models the device class (embedded PC vs smartphone). Forwards each
// processed packet either on the 'out' gate (if connected) or via
// sendDirect to <targetModule>'s 'edgeIn' gate (the UE/host app).
simple EdgeAggregator
{
    parameters:
        int bufferCapacity @unit(B) = default(102400B);       // 100 KiB, as in the thesis design
        volatile double processingTime @unit(s) = default(uniform(1ms, 5ms));
        string targetModule = default("");                    // module path of the backhaul app; "" = use out gate
        @display("i=block/server");
        @signal[edgeDelay](type=simtime_t);
        @signal[queueBytes](type=long);
        @signal[packetDropped](type=long);
        @statistic[edgeDelay](title="edge queueing+processing delay"; unit=s; record=stats,histogram,vector; interpolationmode=none);
        @statistic[queueBytes](title="edge buffer occupancy"; unit=B; record=stats,vector,timeavg; interpolationmode=sample-hold);
        @statistic[packetDropped](title="packets dropped at edge buffer"; record=count,sum; interpolationmode=none);
    gates:
        input in[];
        output out @loose;
}

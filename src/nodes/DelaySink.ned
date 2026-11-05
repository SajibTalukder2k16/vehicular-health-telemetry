package paperrebuild.nodes;

// Terminates a link under test: records per-packet delay since creation
// and total received bytes (throughput = totalBits/simTime at finish).
simple DelaySink
{
    parameters:
        @display("i=block/sink");
        @signal[delay](type=simtime_t);
        @statistic[delay](title="delay since packet creation"; unit=s; record=stats,histogram,vector; interpolationmode=none);
    gates:
        input in;
}

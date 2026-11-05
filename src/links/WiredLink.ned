package paperrebuild.links;

// Serialized wired sensor connection (USB/Ethernet-class): packets are
// transmitted back-to-back at dataRate plus a fixed propagation delay.
simple WiredLink like ILink
{
    parameters:
        double dataRate @unit(bps) = default(100Mbps);
        double delay @unit(s) = default(0.1ms);
        @display("i=block/wheelbarrow");
        @signal[linkDelay](type=simtime_t);
        @statistic[linkDelay](title="wired link delay"; unit=s; record=stats,vector; interpolationmode=none);
    gates:
        input in[];
        output out;
}

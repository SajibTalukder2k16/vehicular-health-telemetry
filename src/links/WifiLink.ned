package paperrebuild.links;

// Calibrated parametric 802.11 DCF link for an intra-rig sensor connection.
//
// This is the indoor counterpart to BleLink, and it is built the same way: a
// parametric model whose throughput and latency EMERGE from framing and
// timing parameters. There is no delay knob and no throughput knob.
//
// Per MSDU the model fragments to maxMsduPayload, then for each fragment
// spends one DCF cycle:
//
//     DIFS + backoff + T_data + SIFS + T_ack
//
// with T_data = phyHeaderTime + (macOverhead + bytes)*8/bitrate and
// T_ack = phyHeaderTime + ackBytes*8/ackBitrate. Backoff is uniform over
// [0, cw] slots, cw starting at cwMin and doubling to cwMax on each failure,
// which is binary exponential backoff. A fragment fails with frameErrorRate
// and is retried up to retryLimit, after which the whole MSDU is dropped.
//
// WHY THIS MODULE EXISTS, and what it is for. An indoor installation can
// attach its sensors over the wireless LAN rather than over BLE or a cable.
// On capacity alone that is uninteresting: the whole rig offers about
// 70 kb/s with the 4 KiB camera against tens of Mb/s available, so a WLAN
// sensor link behaves like WiredLink and the wired arm already stands in for
// it. The property that is NOT the wired arm renamed is that indoor sensor
// traffic and indoor backhaul traffic share one medium and contend for it.
// `mediumBusyFraction` is that term: the fraction of time the channel is
// occupied by stations this model does not simulate, during which this
// station must defer. Set it to 0 for an exclusive medium; set it to the
// backhaul's measured channel occupancy to represent a shared one.
//
// Presets (set via ini):
//   802.11a/g 54 Mbps:  bitrate=54Mbps, ackBitrate=24Mbps, slotTime=9us,
//                       sifs=16us, phyHeaderTime=20us, cwMin=15
//   802.11n 2.4 GHz:    sifs=10us, phyHeaderTime=28us (HT mixed preamble)
//   802.11n 20 MHz MCS7: bitrate=65Mbps
simple WifiLink like ILink
{
    parameters:
        double bitrate @unit(bps) = default(54Mbps);          // PHY data rate
        double ackBitrate @unit(bps) = default(24Mbps);       // control-rate ACK
        int maxMsduPayload @unit(B) = default(1500B);         // MTU-limited fragment
        int macOverhead @unit(B) = default(28B);              // MAC header 24 + FCS 4
        int ackBytes @unit(B) = default(14B);                 // ACK frame body
        double phyHeaderTime @unit(s) = default(20us);        // preamble + SIGNAL
        double slotTime @unit(s) = default(9us);
        double sifs @unit(s) = default(16us);
        int cwMin = default(15);                              // slots
        int cwMax = default(1023);
        int retryLimit = default(7);
        double frameErrorRate = default(0);                   // per-fragment
        // Fraction of time the medium is held by stations outside this model
        // (e.g. the indoor backhaul). The station defers during that time, so
        // each cycle is stretched by 1/(1 - mediumBusyFraction). This is the
        // whole reason to prefer this module over WiredLink indoors.
        double mediumBusyFraction = default(0);
        int queueCapacity @unit(B) = default(65536B);
        @display("i=block/rxtx");
        @signal[linkDelay](type=simtime_t);
        @signal[queueBytes](type=long);
        @signal[packetDropped](type=long);
        @statistic[linkDelay](title="WiFi link delay"; unit=s; record=stats,histogram,vector; interpolationmode=none);
        @statistic[queueBytes](title="WiFi queue occupancy"; unit=B; record=stats,vector,timeavg; interpolationmode=sample-hold);
        @statistic[packetDropped](title="packets dropped at WiFi link"; record=count,sum; interpolationmode=none);
    gates:
        input in[];
        output out;
}

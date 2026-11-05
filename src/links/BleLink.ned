package paperrebuild.links;

// Calibrated parametric BLE connection model.
//
// Data transfer is quantized to connection events every connectionInterval:
// a packet waits for the next event, then is fragmented into link-layer PDUs
// that each occupy the air for their transmission time plus two inter-frame
// spaces and the ACK of the opposite direction. PDUs fail independently with
// pduErrorRate and are retransmitted. Throughput is therefore capped by what
// fits into one connection interval, and unloaded latency is uniform over
// (0, connectionInterval] plus the PDU round time -- reproducing the
// published behavior of BLE 4.0/4.2/5 links (Gomez et al. 2012, Tosi et
// al. 2017) without a delay knob.
//
// Version presets (set via ini):
//   BLE 4.0:      bitrate=1Mbps, maxPduPayload=27B,  ackAirTime=80us  (~237 kbps max)
//   BLE 4.2 DLE:  bitrate=1Mbps, maxPduPayload=251B, ackAirTime=80us  (~780 kbps max)
//   BLE 5 2M PHY: bitrate=2Mbps, maxPduPayload=251B, ackAirTime=40us  (~1.4 Mbps max)
simple BleLink like ILink
{
    parameters:
        double connectionInterval @unit(s) = default(30ms);   // 7.5ms..4s per BLE spec
        double bitrate @unit(bps) = default(1Mbps);           // PHY rate: 1Mbps or 2Mbps
        int maxPduPayload @unit(B) = default(251B);           // LL payload per data PDU (27 without DLE)
        int protocolOverhead @unit(B) = default(7B);          // L2CAP(4)+ATT(3) inside the PDU payload
        int llAirOverhead @unit(B) = default(10B);            // preamble+access addr+LL header+CRC on air
        double ifs @unit(s) = default(150us);                 // T_IFS between packets
        double ackAirTime @unit(s) = default(80us);           // empty PDU from central (40us @2M PHY)
        double pduErrorRate = default(0);                     // independent per-PDU error probability
        double maxCiUtilization = default(1.0);               // usable fraction of the connection interval
        int queueCapacity @unit(B) = default(65536B);         // sensor-side buffer; overflow -> drop
        @display("i=block/rxtx");
        @signal[linkDelay](type=simtime_t);
        @signal[queueBytes](type=long);
        @signal[packetDropped](type=long);
        @statistic[linkDelay](title="BLE link delay"; unit=s; record=stats,histogram,vector; interpolationmode=none);
        @statistic[queueBytes](title="BLE queue occupancy"; unit=B; record=stats,vector,timeavg; interpolationmode=sample-hold);
        @statistic[packetDropped](title="packets dropped at BLE queue"; record=count,sum; interpolationmode=none);
    gates:
        input in[];
        output out;
}

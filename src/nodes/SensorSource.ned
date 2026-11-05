package paperrebuild.nodes;

// Generates SensorData packets of messageLength every sendInterval.
// sourceType: 0=wearable vitals, 1=OBD, 2=camera, 3=alarm.
simple SensorSource
{
    parameters:
        int sourceType;
        volatile int messageLength @unit(B);
        volatile double sendInterval @unit(s);
        double startTime @unit(s) = default(uniform(0s, 1s));
        double stopTime @unit(s) = default(-1s);  // -1: run forever
        @display("i=block/source");
        @signal[packetSent](type=long);
        @statistic[packetSent](title="packets sent"; record=count; interpolationmode=none);
    gates:
        output out;
}

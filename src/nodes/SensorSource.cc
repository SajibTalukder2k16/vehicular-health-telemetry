#include <omnetpp.h>

#include "../common/SensorData_m.h"

using namespace omnetpp;

namespace paperrebuild {

class SensorSource : public cSimpleModule
{
  protected:
    cMessage *sendEvent = nullptr;
    long seq = 0;
    int sourceType = 0;
    simtime_t stopTime;
    simsignal_t packetSentSignal;

    static const char *typeName(int t)
    {
        switch (t) {
            case 0: return "vitals";
            case 1: return "obd";
            case 2: return "camera";
            case 3: return "alarm";
            default: return "sensor";
        }
    }

    virtual void initialize() override
    {
        sourceType = par("sourceType");
        stopTime = par("stopTime");
        packetSentSignal = registerSignal("packetSent");
        sendEvent = new cMessage("send");
        scheduleAt(simTime() + par("startTime").doubleValue() + par("sendInterval").doubleValue(), sendEvent);
    }

    virtual void handleMessage(cMessage *msg) override
    {
        auto *pkt = new SensorData();
        char name[64];
        snprintf(name, sizeof(name), "%s-%ld", typeName(sourceType), seq);
        pkt->setName(name);
        pkt->setByteLength(par("messageLength").intValue());
        pkt->setSourceType(sourceType);
        pkt->setSequenceNumber(seq++);
        send(pkt, "out");
        emit(packetSentSignal, seq);

        simtime_t next = simTime() + par("sendInterval").doubleValue();
        if (stopTime < SIMTIME_ZERO || next < stopTime)
            scheduleAt(next, sendEvent);
    }

    virtual void finish() override { recordScalar("packetsGenerated", seq); }
    ~SensorSource() { cancelAndDelete(sendEvent); }
};

Define_Module(SensorSource);

} // namespace paperrebuild

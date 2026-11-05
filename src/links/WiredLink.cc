#include <omnetpp.h>

using namespace omnetpp;

namespace paperrebuild {

class WiredLink : public cSimpleModule
{
  protected:
    double dataRate = 0;
    simtime_t delay;
    simtime_t channelFreeAt;
    simsignal_t linkDelaySignal;

  protected:
    virtual void initialize() override
    {
        dataRate = par("dataRate");
        delay = par("delay");
        channelFreeAt = SIMTIME_ZERO;
        linkDelaySignal = registerSignal("linkDelay");
    }

    virtual void handleMessage(cMessage *msg) override
    {
        cPacket *pkt = check_and_cast<cPacket *>(msg);
        simtime_t txStart = std::max(simTime(), channelFreeAt);
        simtime_t txTime = SimTime(pkt->getByteLength() * 8 / dataRate);
        channelFreeAt = txStart + txTime;
        simtime_t departIn = channelFreeAt + delay - simTime();
        emit(linkDelaySignal, simTime() + departIn - pkt->getCreationTime());
        sendDelayed(pkt, departIn, "out");
    }
};

Define_Module(WiredLink);

} // namespace paperrebuild

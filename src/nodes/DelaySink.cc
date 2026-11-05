#include <omnetpp.h>

using namespace omnetpp;

namespace paperrebuild {

class DelaySink : public cSimpleModule
{
  protected:
    long numReceived = 0;
    long totalBytes = 0;
    simsignal_t delaySignal;

    virtual void initialize() override { delaySignal = registerSignal("delay"); }

    virtual void handleMessage(cMessage *msg) override
    {
        cPacket *pkt = check_and_cast<cPacket *>(msg);
        numReceived++;
        totalBytes += pkt->getByteLength();
        emit(delaySignal, simTime() - pkt->getCreationTime());
        delete pkt;
    }

    virtual void finish() override
    {
        recordScalar("packetsReceived", numReceived);
        recordScalar("bytesReceived", totalBytes);
        recordScalar("throughputBps", simTime() > SIMTIME_ZERO ? totalBytes * 8 / simTime().dbl() : 0);
    }
};

Define_Module(DelaySink);

} // namespace paperrebuild

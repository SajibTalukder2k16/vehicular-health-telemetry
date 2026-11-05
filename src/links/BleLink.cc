#include <omnetpp.h>

using namespace omnetpp;

namespace paperrebuild {

class BleLink : public cSimpleModule
{
  protected:
    simtime_t connectionInterval;
    double bitrate = 0;
    int maxPduPayload = 0;
    int protocolOverhead = 0;
    int llAirOverhead = 0;
    simtime_t ifs;
    simtime_t ackAirTime;
    double pduErrorRate = 0;
    double maxCiUtilization = 1;
    long queueCapacity = 0;

    cPacketQueue queue;
    long queueBytes = 0;
    long headBytesRemaining = -1;
    cMessage *connEvent = nullptr;
    long numDropped = 0;

    simsignal_t linkDelaySignal;
    simsignal_t queueBytesSignal;
    simsignal_t packetDroppedSignal;

  protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
    virtual void processConnectionEvent();
    virtual void finish() override;
    ~BleLink() { cancelAndDelete(connEvent); }
};

Define_Module(BleLink);

void BleLink::initialize()
{
    connectionInterval = par("connectionInterval");
    bitrate = par("bitrate");
    maxPduPayload = par("maxPduPayload");
    protocolOverhead = par("protocolOverhead");
    llAirOverhead = par("llAirOverhead");
    ifs = par("ifs");
    ackAirTime = par("ackAirTime");
    pduErrorRate = par("pduErrorRate");
    maxCiUtilization = par("maxCiUtilization");
    queueCapacity = par("queueCapacity").intValue();

    if (maxPduPayload <= protocolOverhead)
        throw cRuntimeError("maxPduPayload must exceed protocolOverhead");

    linkDelaySignal = registerSignal("linkDelay");
    queueBytesSignal = registerSignal("queueBytes");
    packetDroppedSignal = registerSignal("packetDropped");

    connEvent = new cMessage("connectionEvent");
    // random phase: the peripheral's data is not synchronized to the anchor point
    scheduleAt(simTime() + uniform(0, connectionInterval.dbl()), connEvent);
}

void BleLink::handleMessage(cMessage *msg)
{
    if (msg == connEvent) {
        processConnectionEvent();
        scheduleAt(simTime() + connectionInterval, connEvent);
        return;
    }
    cPacket *pkt = check_and_cast<cPacket *>(msg);
    if (queueBytes + pkt->getByteLength() > queueCapacity) {
        numDropped++;
        emit(packetDroppedSignal, numDropped);
        delete pkt;
        return;
    }
    queueBytes += pkt->getByteLength();
    queue.insert(pkt);
    emit(queueBytesSignal, queueBytes);
}

void BleLink::processConnectionEvent()
{
    simtime_t used = SIMTIME_ZERO;
    simtime_t budget = connectionInterval * maxCiUtilization;
    int appBytesPerPdu = maxPduPayload - protocolOverhead;

    while (!queue.isEmpty()) {
        cPacket *head = queue.front();
        if (headBytesRemaining < 0)
            headBytesRemaining = std::max((long)1, (long)head->getByteLength());

        long chunk = std::min(headBytesRemaining, (long)appBytesPerPdu);
        long airBytes = chunk + protocolOverhead + llAirOverhead;
        simtime_t pduTime = SimTime(airBytes * 8 / bitrate) + 2 * ifs + ackAirTime;
        if (used + pduTime > budget)
            break;  // event over; continue at next anchor point
        used += pduTime;

        if (uniform(0, 1) >= pduErrorRate) {
            headBytesRemaining -= chunk;
            if (headBytesRemaining <= 0) {
                cPacket *done = queue.pop();
                queueBytes -= done->getByteLength();
                emit(queueBytesSignal, queueBytes);
                emit(linkDelaySignal, simTime() + used - done->getCreationTime());
                sendDelayed(done, used, "out");
                headBytesRemaining = -1;
            }
        }
        // on PDU error: same chunk is retried on the next iteration/event
    }
}

void BleLink::finish()
{
    recordScalar("packetsDropped", numDropped);
}

} // namespace paperrebuild

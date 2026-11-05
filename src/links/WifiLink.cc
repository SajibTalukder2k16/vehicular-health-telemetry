#include <algorithm>
#include <omnetpp.h>

using namespace omnetpp;

namespace paperrebuild {

// Parametric 802.11 DCF link. See WifiLink.ned for the model and why it
// exists. Throughput and latency emerge from framing and timing; there is no
// delay or throughput knob.
class WifiLink : public cSimpleModule
{
  protected:
    double bitrate = 0;
    double ackBitrate = 0;
    int maxMsduPayload = 0;
    int macOverhead = 0;
    int ackBytes = 0;
    simtime_t phyHeaderTime;
    simtime_t slotTime;
    simtime_t sifs;
    simtime_t difs;
    int cwMin = 0;
    int cwMax = 0;
    int retryLimit = 0;
    double frameErrorRate = 0;
    double mediumBusyFraction = 0;
    long queueCapacity = 0;

    cPacketQueue queue;
    long queueBytes = 0;
    cMessage *serviceEnd = nullptr;
    cPacket *inService = nullptr;
    long numDropped = 0;
    long numRetryDrops = 0;

    simsignal_t linkDelaySignal;
    simsignal_t queueBytesSignal;
    simsignal_t packetDroppedSignal;

  protected:
    virtual void initialize() override;
    virtual void handleMessage(cMessage *msg) override;
    virtual void finish() override;

    // Air time of one DCF cycle for a fragment of `bytes`, with a backoff
    // drawn uniformly over [0, cw] slots. A failed cycle costs the same: the
    // sender waits an ACK timeout of about SIFS + ACK duration before
    // retrying, so the two are equal to within a slot.
    simtime_t cycleTime(long bytes, int cw);
    // Total air time to deliver one MSDU, including fragmentation, binary
    // exponential backoff and retries. Returns a negative value if the
    // retry limit was exhausted, meaning the MSDU is dropped.
    simtime_t serviceTime(long bytes, bool& dropped);
    void startServiceIfIdle();

  public:
    ~WifiLink() { cancelAndDelete(serviceEnd); }
};

Define_Module(WifiLink);

void WifiLink::initialize()
{
    bitrate = par("bitrate");
    ackBitrate = par("ackBitrate");
    maxMsduPayload = par("maxMsduPayload");
    macOverhead = par("macOverhead");
    ackBytes = par("ackBytes");
    phyHeaderTime = par("phyHeaderTime");
    slotTime = par("slotTime");
    sifs = par("sifs");
    cwMin = par("cwMin");
    cwMax = par("cwMax");
    retryLimit = par("retryLimit");
    frameErrorRate = par("frameErrorRate");
    mediumBusyFraction = par("mediumBusyFraction");
    queueCapacity = par("queueCapacity").intValue();

    if (maxMsduPayload <= 0)
        throw cRuntimeError("maxMsduPayload must be positive");
    if (bitrate <= 0 || ackBitrate <= 0)
        throw cRuntimeError("bitrate and ackBitrate must be positive");
    if (mediumBusyFraction < 0 || mediumBusyFraction >= 1)
        throw cRuntimeError("mediumBusyFraction must be in [0, 1); "
                            "1 would mean the medium is never available");
    if (cwMin < 0 || cwMax < cwMin)
        throw cRuntimeError("need 0 <= cwMin <= cwMax");

    difs = sifs + 2 * slotTime;

    linkDelaySignal = registerSignal("linkDelay");
    queueBytesSignal = registerSignal("queueBytes");
    packetDroppedSignal = registerSignal("packetDropped");

    serviceEnd = new cMessage("serviceEnd");
}

simtime_t WifiLink::cycleTime(long bytes, int cw)
{
    simtime_t backoff = intuniform(0, cw) * slotTime;
    simtime_t tData = phyHeaderTime + SimTime((macOverhead + bytes) * 8 / bitrate);
    simtime_t tAck = phyHeaderTime + SimTime(ackBytes * 8 / ackBitrate);
    simtime_t cycle = difs + backoff + tData + sifs + tAck;
    // Deferral while the medium is held by stations outside this model.
    return cycle / (1.0 - mediumBusyFraction);
}

simtime_t WifiLink::serviceTime(long bytes, bool& dropped)
{
    dropped = false;
    simtime_t total = SIMTIME_ZERO;
    long remaining = std::max(1L, bytes);
    while (remaining > 0) {
        long frag = std::min(remaining, (long)maxMsduPayload);
        int cw = cwMin;
        int attempt = 0;
        while (true) {
            total += cycleTime(frag, cw);
            if (uniform(0, 1) >= frameErrorRate)
                break;                       // ACKed
            if (++attempt > retryLimit) {
                dropped = true;              // MSDU discarded by the MAC
                return total;
            }
            cw = std::min(2 * cw + 1, cwMax);
        }
        remaining -= frag;
    }
    return total;
}

void WifiLink::startServiceIfIdle()
{
    if (inService != nullptr || queue.isEmpty())
        return;
    inService = queue.pop();
    queueBytes -= inService->getByteLength();
    emit(queueBytesSignal, queueBytes);

    bool dropped = false;
    simtime_t t = serviceTime(inService->getByteLength(), dropped);
    if (dropped) {
        numDropped++;
        numRetryDrops++;
        emit(packetDroppedSignal, numDropped);
        delete inService;
        inService = nullptr;
        // The air time was still spent on the failed attempts, so the next
        // packet starts after it rather than immediately.
        if (!queue.isEmpty()) {
            scheduleAt(simTime() + t, serviceEnd);
            return;
        }
        return;
    }
    scheduleAt(simTime() + t, serviceEnd);
}

void WifiLink::handleMessage(cMessage *msg)
{
    if (msg == serviceEnd) {
        if (inService != nullptr) {
            emit(linkDelaySignal, simTime() - inService->getCreationTime());
            send(inService, "out");
            inService = nullptr;
        }
        startServiceIfIdle();
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
    if (!serviceEnd->isScheduled())
        startServiceIfIdle();
}

void WifiLink::finish()
{
    recordScalar("packetsDropped", numDropped);
    recordScalar("packetsDroppedRetryLimit", numRetryDrops);
}

} // namespace paperrebuild

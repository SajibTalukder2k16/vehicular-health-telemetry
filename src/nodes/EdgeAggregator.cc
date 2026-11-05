#include <omnetpp.h>

using namespace omnetpp;

namespace paperrebuild {

class EdgeAggregator : public cSimpleModule
{
  protected:
    long bufferCapacity = 0;
    cPacketQueue queue;
    long queueBytes = 0;
    cPacket *inService = nullptr;
    cMessage *serviceEnd = nullptr;
    cGate *targetGate = nullptr;
    long numDropped = 0;
    long numForwarded = 0;

    simsignal_t edgeDelaySignal;
    simsignal_t queueBytesSignal;
    simsignal_t packetDroppedSignal;

    virtual void initialize() override
    {
        bufferCapacity = par("bufferCapacity").intValue();
        edgeDelaySignal = registerSignal("edgeDelay");
        queueBytesSignal = registerSignal("queueBytes");
        packetDroppedSignal = registerSignal("packetDropped");
        serviceEnd = new cMessage("serviceEnd");

        const char *targetPath = par("targetModule");
        if (*targetPath) {
            cModule *target = getModuleByPath(targetPath);
            if (!target)
                throw cRuntimeError("targetModule '%s' not found", targetPath);
            targetGate = target->gate("edgeIn");
        }
        else if (!gate("out")->isConnected())
            throw cRuntimeError("either connect the 'out' gate or set targetModule");
    }

    void startService(cPacket *pkt)
    {
        inService = pkt;
        scheduleAt(simTime() + par("processingTime").doubleValue(), serviceEnd);
    }

    void forward(cPacket *pkt)
    {
        emit(edgeDelaySignal, simTime() - pkt->getArrivalTime());
        numForwarded++;
        if (targetGate)
            sendDirect(pkt, targetGate);
        else
            send(pkt, "out");
    }

    virtual void handleMessage(cMessage *msg) override
    {
        if (msg == serviceEnd) {
            forward(inService);
            inService = nullptr;
            if (!queue.isEmpty()) {
                cPacket *next = queue.pop();
                queueBytes -= next->getByteLength();
                emit(queueBytesSignal, queueBytes);
                startService(next);
            }
            return;
        }
        cPacket *pkt = check_and_cast<cPacket *>(msg);
        if (inService == nullptr) {
            startService(pkt);
        }
        else if (queueBytes + pkt->getByteLength() > bufferCapacity) {
            numDropped++;
            emit(packetDroppedSignal, numDropped);
            delete pkt;
        }
        else {
            queueBytes += pkt->getByteLength();
            queue.insert(pkt);
            emit(queueBytesSignal, queueBytes);
        }
    }

    virtual void finish() override
    {
        recordScalar("packetsForwarded", numForwarded);
        recordScalar("packetsDropped", numDropped);
    }

    ~EdgeAggregator()
    {
        cancelAndDelete(serviceEnd);
        delete inService;
    }
};

Define_Module(EdgeAggregator);

} // namespace paperrebuild

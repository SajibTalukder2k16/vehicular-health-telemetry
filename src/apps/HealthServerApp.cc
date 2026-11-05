#include "inet/applications/base/ApplicationBase.h"
#include "inet/common/packet/Packet.h"
#include "inet/common/socket/SocketTag_m.h"
#include "inet/networklayer/common/L3Address.h"
#include "inet/networklayer/common/L3AddressTag_m.h"
#include "inet/transportlayer/common/L4PortTag_m.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"

#include "../common/HealthPayload_m.h"

using namespace omnetpp;
using namespace inet;

namespace paperrebuild {

class HealthServerApp : public ApplicationBase, public UdpSocket::ICallback
{
  protected:
    static const int NUM_TYPES = 4;  // vitals, obd, camera, alarm
    UdpSocket socket;
    long numReceived[NUM_TYPES] = {0};
    long deadlineMisses[NUM_TYPES] = {0};
    simtime_t deadlines[NUM_TYPES];
    simsignal_t e2eDelaySignal;
    simsignal_t perTypeSignal[NUM_TYPES];

    // ---- feedback to the gateway ----
    // Cumulative counters plus the freshest sensing time held per stream.
    // This is all the gateway is permitted to know; it never sees radio queue
    // depth or the server's true AoI.
    simtime_t feedbackInterval;
    int feedbackLength = 0;
    cMessage *feedbackTimer = nullptr;
    L3Address gatewayAddr;
    int gatewayPort = -1;
    uint64_t bytesReceived = 0;
    uint64_t packetsReceived = 0;
    simtime_t freshestVitals;
    simtime_t freshestCamera;
    long numFeedbackSent = 0;
    simsignal_t feedbackSentSignal;

    virtual void initialize(int stage) override
    {
        ApplicationBase::initialize(stage);
        if (stage == INITSTAGE_LOCAL) {
            e2eDelaySignal = registerSignal("e2eDelay");
            perTypeSignal[0] = registerSignal("e2eDelayVitals");
            perTypeSignal[1] = registerSignal("e2eDelayObd");
            perTypeSignal[2] = registerSignal("e2eDelayCamera");
            perTypeSignal[3] = registerSignal("e2eDelayAlarm");
            deadlines[0] = par("vitalsDeadline");
            deadlines[1] = par("vitalsDeadline");
            deadlines[2] = par("vitalsDeadline");
            deadlines[3] = par("alarmDeadline");
            feedbackInterval = par("feedbackInterval");
            feedbackLength = par("feedbackLength").intValue();
            feedbackSentSignal = registerSignal("feedbackSent");
            if (feedbackInterval > SIMTIME_ZERO)
                feedbackTimer = new cMessage("feedbackTimer");
        }
    }

    virtual void handleStartOperation(LifecycleOperation *operation) override
    {
        socket.setOutputGate(gate("socketOut"));
        socket.setCallback(this);
        socket.bind(par("localPort").intValue());
    }

    virtual void handleStopOperation(LifecycleOperation *operation) override { socket.close(); }
    virtual void handleCrashOperation(LifecycleOperation *operation) override { socket.destroy(); }

    virtual void handleMessageWhenUp(cMessage *msg) override
    {
        if (msg == feedbackTimer) {
            sendFeedback();
            scheduleAt(simTime() + feedbackInterval, feedbackTimer);
            return;
        }
        socket.processMessage(msg);
    }

    void sendFeedback()
    {
        if (gatewayPort < 0 || gatewayAddr.isUnspecified())
            return;                            // nothing has reported in yet
        auto fb = makeShared<GatewayFeedback>();
        fb->setChunkLength(B(feedbackLength));
        fb->setBytesReceived(bytesReceived);
        fb->setPacketsReceived(packetsReceived);
        fb->setFreshestVitals(freshestVitals);
        fb->setFreshestCamera(freshestCamera);
        fb->setGeneratedAt(simTime());
        auto *pkt = new Packet("GatewayFeedback");
        pkt->insertAtBack(fb);
        socket.sendTo(pkt, gatewayAddr, gatewayPort);
        numFeedbackSent++;
        emit(feedbackSentSignal, numFeedbackSent);
    }

    virtual void socketDataArrived(UdpSocket *sock, Packet *packet) override
    {
        auto payload = packet->peekAtFront<HealthPayload>();
        simtime_t delay = simTime() - payload->getSensorCreationTime();
        int type = payload->getSourceType();
        // remember where to send feedback, and keep the cumulative counters
        auto tag = packet->findTag<L3AddressInd>();
        if (tag)
            gatewayAddr = tag->getSrcAddress();
        auto pt = packet->findTag<L4PortInd>();
        if (pt)
            gatewayPort = pt->getSrcPort();
        bytesReceived += payload->getChunkLength().get<B>();
        packetsReceived++;
        if (type == 0 && payload->getSensorCreationTime() > freshestVitals)
            freshestVitals = payload->getSensorCreationTime();
        if (type == 2 && payload->getSensorCreationTime() > freshestCamera)
            freshestCamera = payload->getSensorCreationTime();
        if (feedbackTimer && !feedbackTimer->isScheduled())
            scheduleAt(simTime() + feedbackInterval, feedbackTimer);
        emit(e2eDelaySignal, delay);
        if (type >= 0 && type < NUM_TYPES) {
            emit(perTypeSignal[type], delay);
            numReceived[type]++;
            if (delay > deadlines[type])
                deadlineMisses[type]++;
        }
        delete packet;
    }

    virtual void socketErrorArrived(UdpSocket *sock, Indication *indication) override { delete indication; }
    virtual void socketClosed(UdpSocket *sock) override {}

    ~HealthServerApp() { cancelAndDelete(feedbackTimer); }

    virtual void finish() override
    {
        recordScalar("feedbackSent", numFeedbackSent);
        static const char *names[NUM_TYPES] = {"vitals", "obd", "camera", "alarm"};
        long total = 0;
        for (int i = 0; i < NUM_TYPES; i++) {
            total += numReceived[i];
            recordScalar((std::string("received_") + names[i]).c_str(), numReceived[i]);
            recordScalar((std::string("deadlineMisses_") + names[i]).c_str(), deadlineMisses[i]);
        }
        recordScalar("totalPacketsReceived", total);
        ApplicationBase::finish();
    }
};

Define_Module(HealthServerApp);

} // namespace paperrebuild

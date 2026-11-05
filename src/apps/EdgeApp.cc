#include "inet/applications/base/ApplicationBase.h"
#include "inet/common/Simsignals.h"
#include "inet/common/packet/Packet.h"
#include "inet/networklayer/common/L3AddressResolver.h"
#include "inet/transportlayer/contract/udp/UdpSocket.h"

#include "../common/HealthPayload_m.h"
#include "../common/SensorData_m.h"

using namespace omnetpp;
using namespace inet;

namespace paperrebuild {

// sourceType codes (SensorData.msg): 0=wearable vitals, 1=OBD, 2=camera, 3=alarm
static const int SRC_VITALS = 0;
static const int SRC_OBD    = 1;
static const int SRC_CAMERA = 2;
static const int SRC_ALARM  = 3;

class EdgeApp : public ApplicationBase, public UdpSocket::ICallback
{
  protected:
    // POLICY_NONE..POLICY_DROPPACE are open loop: they never look at feedback.
    // POLICY_PRIO..POLICY_CTRL are closed loop and form the baseline ladder.
    //
    // POLICY_AIMD_SELF is the ablation of POLICY_AIMD: identical in every
    // respect except that it backs off on the age of the newest CAMERA sample
    // the server holds -- the throttled stream's own freshness -- rather than
    // on vitals. It exists to answer the obvious reviewer question, "why must
    // the signal come from the other stream?", with a measurement instead of
    // an argument. See docs/RELATED_WORK.md.
    enum Policy { POLICY_NONE, POLICY_DROP, POLICY_PACE, POLICY_DROPPACE,
                  POLICY_PRIO, POLICY_ADAPTIVE, POLICY_CTRL, POLICY_AIMD,
                  POLICY_AIMD_SELF };

    UdpSocket socket;
    L3Address destAddress;
    int destPort = -1;
    bool running = false;
    long numSent = 0;
    long numDroppedNotRunning = 0;

    Policy policy = POLICY_NONE;

    // ---- open-loop camera shaping (drop / pace / dropPace) ----
    double cameraRate = 0;              // bits per second
    long cameraBurst = 0;               // bytes
    long cameraQueueCapacity = 0;       // bytes
    simtime_t cameraMaxAge;
    double tokens = 0;                  // bytes currently available
    simtime_t lastTokenUpdate;
    cPacketQueue pending;               // camera frames awaiting service
    long pendingBytes = 0;
    cMessage *paceTimer = nullptr;

    // ---- closed-loop state (prio / adaptive / ctrl) ----
    long maxInFlight = 0;
    simtime_t horizon;
    double rateEwmaAlpha = 0.2;
    double critReserveFactor = 1.5;
    long critQueueCapacity = 0;
    long cameraHeadroom = 0;            // window bytes kept free for critical
    double probeRate = 0;               // bytes/s floor so the estimator can see capacity
    double rateSafety = 0.9;
    double dynRate = 0;                 // bytes/s, the adapted bucket rate
    simtime_t freshnessTarget;
    double probeIncrement = 0;          // bytes/s added per report while safe
    double backoffFactor = 0.7;
    long numBackoffs = 0;
    long numProbes = 0;
    double maxObservedAge = 0;
    double rateSum = 0;                 // bytes/s summed over adaptations
    long rateUpdates = 0;               // so the mean adapted rate is reportable
    cPacketQueue critQueue;             // vitals + OBD, newest-only
    long critBytes = 0;
    uint64_t bytesSent = 0;             // cumulative application bytes handed to UDP
    uint64_t bytesAcked = 0;            // cumulative bytes the server has confirmed
    double estRate = 0;                 // bytes/s, EWMA from successive reports
    double critRate = 0;                // bytes/s of critical traffic, EWMA
    simtime_t lastCritArrival;
    uint64_t lastFbBytes = 0;
    simtime_t lastFbTime;
    bool haveFb = false;

    long numAdmitted = 0;
    long numGateDropped = 0;
    long numStaleDropped = 0;
    long numCritSuperseded = 0;

    simsignal_t cameraAdmittedSignal;
    simsignal_t cameraGateDroppedSignal;
    simsignal_t cameraPendingBytesSignal;
    simsignal_t cameraGateDelaySignal;
    simsignal_t inFlightBytesSignal;
    simsignal_t estThroughputSignal;
    simsignal_t bucketRateSignal;

    bool closedLoop() const { return policy >= POLICY_PRIO; }

    // Which closed-loop policies discard camera frames that have gone stale in
    // the pending queue. Named rather than enumerated at the use site: when
    // aimdSelf was added as the cross-stream ablation it was left out of an
    // inline (CTRL || AIMD) test, which silently gave it a SECOND difference
    // from aimd -- it admitted stale frames the control arm would have dropped,
    // so its camera timeliness was penalised by more than the signal source.
    // The ablation's single-variable claim depends on this staying in one place.
    bool dropsStaleCamera() const
    {
        return policy == POLICY_CTRL || policy == POLICY_AIMD
               || policy == POLICY_AIMD_SELF;
    }

    virtual void initialize(int stage) override
    {
        ApplicationBase::initialize(stage);
        if (stage == INITSTAGE_LOCAL) {
            destPort = par("destPort");
            const char *p = par("admissionPolicy");
            if (!strcmp(p, "none")) policy = POLICY_NONE;
            else if (!strcmp(p, "drop")) policy = POLICY_DROP;
            else if (!strcmp(p, "pace")) policy = POLICY_PACE;
            else if (!strcmp(p, "dropPace")) policy = POLICY_DROPPACE;
            else if (!strcmp(p, "prio")) policy = POLICY_PRIO;
            else if (!strcmp(p, "adaptive")) policy = POLICY_ADAPTIVE;
            else if (!strcmp(p, "ctrl")) policy = POLICY_CTRL;
            else if (!strcmp(p, "aimd")) policy = POLICY_AIMD;
            else if (!strcmp(p, "aimdSelf")) policy = POLICY_AIMD_SELF;
            else throw cRuntimeError("unknown admissionPolicy '%s'", p);
            cameraRate = par("cameraRate").doubleValue();
            cameraBurst = par("cameraBurst").intValue();
            cameraQueueCapacity = par("cameraQueueCapacity").intValue();
            cameraMaxAge = par("cameraMaxAge").doubleValue();
            maxInFlight = par("maxInFlight").intValue();
            horizon = par("horizon").doubleValue();
            rateEwmaAlpha = par("rateEwmaAlpha");
            critReserveFactor = par("critReserveFactor");
            critQueueCapacity = par("critQueueCapacity").intValue();
            cameraHeadroom = par("cameraHeadroom").intValue();
            probeRate = par("probeRate").doubleValue() / 8.0;   // bits -> bytes
            rateSafety = par("rateSafety");
            freshnessTarget = par("freshnessTarget").doubleValue();
            probeIncrement = par("probeIncrement").doubleValue() / 8.0;
            backoffFactor = par("backoffFactor");
            dynRate = cameraRate / 8.0;    // start at the ceiling, adapt down
            tokens = cameraBurst;
            lastTokenUpdate = simTime();
            paceTimer = new cMessage("paceTimer");
            cameraAdmittedSignal = registerSignal("cameraAdmitted");
            cameraGateDroppedSignal = registerSignal("cameraGateDropped");
            cameraPendingBytesSignal = registerSignal("cameraPendingBytes");
            cameraGateDelaySignal = registerSignal("cameraGateDelay");
            inFlightBytesSignal = registerSignal("inFlightBytes");
            estThroughputSignal = registerSignal("estThroughput");
            bucketRateSignal = registerSignal("bucketRate");
        }
    }

    virtual void handleStartOperation(LifecycleOperation *operation) override
    {
        socket.setOutputGate(gate("socketOut"));
        socket.setCallback(this);
        socket.bind(par("localPort").intValue());
        destAddress = L3AddressResolver().resolve(par("destAddress"));
        running = true;
    }

    virtual void handleStopOperation(LifecycleOperation *operation) override
    {
        running = false;
        socket.close();
    }

    virtual void handleCrashOperation(LifecycleOperation *operation) override
    {
        running = false;
        socket.destroy();
    }

    // Bytes per second the camera bucket is currently filling at. The
    // open-loop policies use the configured rate; the closed-loop ones use
    // the rate they have adapted to.
    double bucketRate() const
    {
        if (policy == POLICY_ADAPTIVE || policy == POLICY_CTRL
            || policy == POLICY_AIMD || policy == POLICY_AIMD_SELF)
            return dynRate;
        return cameraRate / 8.0;
    }

    void refillTokens()
    {
        simtime_t now = simTime();
        double dt = (now - lastTokenUpdate).dbl();
        if (dt > 0) {
            tokens = std::min((double)cameraBurst, tokens + dt * bucketRate());
            lastTokenUpdate = now;
        }
    }

    // Adapt the bucket rate to what feedback says is getting through, less
    // what the critical streams need, with a safety factor. Clamped below by
    // the probe floor so the estimator keeps seeing real capacity rather than
    // the consequence of its own decisions, and above by cameraRate.
    // Additive-increase / multiplicative-decrease on the camera rate, driven
    // by the age of the newest vitals the server has confirmed. Probing up is
    // what lets the rate discover capacity that a throughput estimate fed by
    // its own throttling never can.
    void adaptRateAimd(const Ptr<const GatewayFeedback>& fb)
    {
        // POLICY_AIMD watches a stream it does not throttle, so the signal is
        // exogenous to the decision. POLICY_AIMD_SELF watches the stream it
        // does throttle, which makes the signal partly a consequence of the
        // policy's own last action -- the same circularity that sank the
        // throughput estimator (docs/PILOT_CONDITIONS.md). Whether that is
        // fatal here is the question the ablation measures, so nothing else
        // differs between the two.
        simtime_t freshest = policy == POLICY_AIMD_SELF ? fb->getFreshestCamera()
                                                        : fb->getFreshestVitals();
        simtime_t observedAge = simTime() - freshest;
        if (observedAge.dbl() > maxObservedAge)
            maxObservedAge = observedAge.dbl();
        double ceil = cameraRate / 8.0;
        if (observedAge > freshnessTarget) {
            dynRate *= backoffFactor;                 // evidence of harm
            numBackoffs++;
        }
        else {
            dynRate += probeIncrement;                // probe for headroom
            numProbes++;
        }
        dynRate = std::min(ceil, std::max(probeRate, dynRate));
        rateSum += dynRate;                           // for the mean, below
        rateUpdates++;
        emit(bucketRateSignal, dynRate * 8.0);
    }

    void adaptRate()
    {
        double avail = estRate - critRate * (policy == POLICY_CTRL ? critReserveFactor : 1.0);
        double target = rateSafety * avail;
        double floor = probeRate;
        double ceil = cameraRate / 8.0;
        dynRate = std::min(ceil, std::max(floor, target));
    }

    long inFlight() const
    {
        // Unacknowledged bytes. This OVERSTATES what is still queued: some of
        // it may already have been delivered with the report still in transit,
        // and some may have been lost and will never be acknowledged. The
        // policies treat it as an upper bound rather than a measurement.
        return bytesSent > bytesAcked ? (long)(bytesSent - bytesAcked) : 0;
    }

    void sendToCloud(SensorData *sd)
    {
        auto payload = makeShared<HealthPayload>();
        long len = std::max((int64_t)1, sd->getByteLength());
        payload->setChunkLength(B(len));
        payload->setSensorCreationTime(sd->getCreationTime());
        payload->setSourceType(sd->getSourceType());
        payload->setSequenceNumber(sd->getSequenceNumber());
        payload->setEdgeDelay(simTime() - sd->getCreationTime());
        auto *pkt = new Packet(sd->getName());
        pkt->insertAtBack(payload);
        delete sd;
        emit(packetSentSignal, pkt);
        socket.sendTo(pkt, destAddress, destPort);
        numSent++;
        bytesSent += len;
        if (closedLoop())
            emit(inFlightBytesSignal, inFlight());
    }

    // ---------------------------------------------------------------- open loop
    void drainPending()
    {
        refillTokens();
        while (!pending.isEmpty()) {
            auto *head = check_and_cast<SensorData *>(pending.front());
            if (policy == POLICY_DROPPACE
                && simTime() - head->getArrivalTime() > cameraMaxAge) {
                pending.pop();
                pendingBytes -= head->getByteLength();
                numStaleDropped++;
                numGateDropped++;
                emit(cameraGateDroppedSignal, numGateDropped);
                emit(cameraPendingBytesSignal, pendingBytes);
                delete head;
                continue;
            }
            long need = head->getByteLength();
            if (tokens < need)
                break;
            pending.pop();
            pendingBytes -= need;
            tokens -= need;
            emit(cameraPendingBytesSignal, pendingBytes);
            emit(cameraGateDelaySignal, simTime() - head->getArrivalTime());
            numAdmitted++;
            emit(cameraAdmittedSignal, numAdmitted);
            sendToCloud(head);
        }
        if (!pending.isEmpty() && !paceTimer->isScheduled()) {
            auto *head = check_and_cast<SensorData *>(pending.front());
            double deficit = head->getByteLength() - tokens;
            if (deficit < 0) deficit = 0;
            simtime_t wait = deficit * 8.0 / cameraRate;
            if (policy == POLICY_DROPPACE) {
                simtime_t expiry = head->getArrivalTime() + cameraMaxAge - simTime();
                if (expiry < wait)
                    wait = std::max(SimTime(0), expiry);
            }
            scheduleAt(simTime() + std::max(wait, SimTime(1, SIMTIME_US)), paceTimer);
        }
    }

    void handleCameraOpenLoop(SensorData *sd)
    {
        long len = sd->getByteLength();
        refillTokens();
        if (policy == POLICY_DROP) {
            if (tokens >= len) {
                tokens -= len;
                numAdmitted++;
                emit(cameraAdmittedSignal, numAdmitted);
                emit(cameraGateDelaySignal, SIMTIME_ZERO);
                sendToCloud(sd);
            }
            else {
                numGateDropped++;
                emit(cameraGateDroppedSignal, numGateDropped);
                delete sd;
            }
            return;
        }
        if (pending.isEmpty() && tokens >= len) {
            tokens -= len;
            numAdmitted++;
            emit(cameraAdmittedSignal, numAdmitted);
            emit(cameraGateDelaySignal, SIMTIME_ZERO);
            sendToCloud(sd);
            return;
        }
        if (pendingBytes + len > cameraQueueCapacity) {
            numGateDropped++;
            emit(cameraGateDroppedSignal, numGateDropped);
            delete sd;
            return;
        }
        pendingBytes += len;
        pending.insert(sd);
        emit(cameraPendingBytesSignal, pendingBytes);
        drainPending();
    }

    // -------------------------------------------------------------- closed loop
    // Bytes of critical traffic the gateway should keep room for over the next
    // horizon: what is already queued, plus what the observed arrival rate
    // suggests will turn up, with a safety factor. Only ctrl applies this.
    double criticalReserve() const
    {
        return critReserveFactor * (critBytes + critRate * horizon.dbl());
    }

    void enqueueCritical(SensorData *sd)
    {
        // Newest-only replacement, applied ONLY to periodic state updates that
        // genuinely supersede their predecessors (vitals, OBD). A queued sample
        // of the same stream is discarded in favour of the newer one. Alarms
        // are never treated this way -- each is a distinct event.
        int type = sd->getSourceType();
        for (int i = 0; i < critQueue.getLength(); i++) {
            auto *q = check_and_cast<SensorData *>(critQueue.get(i));
            if (q->getSourceType() == type) {
                critQueue.remove(q);
                critBytes -= q->getByteLength();
                numCritSuperseded++;
                delete q;
                break;
            }
        }
        if (critBytes + sd->getByteLength() > critQueueCapacity) {
            numGateDropped++;
            emit(cameraGateDroppedSignal, numGateDropped);
            delete sd;
            return;
        }
        critBytes += sd->getByteLength();
        critQueue.insert(sd);
    }

    void drainClosedLoop()
    {
        // 1. critical state updates go out as soon as they arrive. The
        //    newest-only queue only bites if something upstream applies
        //    backpressure; with rate control there is none, so in practice
        //    this drains immediately and supersession is rare. That is itself
        //    a finding: newest-only replacement is not the useful lever here.
        while (!critQueue.isEmpty()) {
            auto *head = check_and_cast<SensorData *>(critQueue.pop());
            critBytes -= head->getByteLength();
            sendToCloud(head);
        }
        // 2. camera through the token bucket at the current adapted rate
        refillTokens();
        double budget = tokens;
        while (!pending.isEmpty()) {
            auto *head = check_and_cast<SensorData *>(pending.front());
            if (dropsStaleCamera()
                && simTime() - head->getArrivalTime() > cameraMaxAge) {
                pending.pop();
                pendingBytes -= head->getByteLength();
                numStaleDropped++;
                numGateDropped++;
                emit(cameraGateDroppedSignal, numGateDropped);
                emit(cameraPendingBytesSignal, pendingBytes);
                delete head;
                continue;
            }
            long need = head->getByteLength();
            if (budget < need)
                break;
            pending.pop();
            pendingBytes -= need;
            budget -= need;
            tokens -= need;
            emit(cameraPendingBytesSignal, pendingBytes);
            emit(cameraGateDelaySignal, simTime() - head->getArrivalTime());
            numAdmitted++;
            emit(cameraAdmittedSignal, numAdmitted);
            sendToCloud(head);
        }
        if (!pending.isEmpty() && !paceTimer->isScheduled()) {
            auto *head = check_and_cast<SensorData *>(pending.front());
            double deficit = head->getByteLength() - tokens;
            if (deficit < 0) deficit = 0;
            double r = bucketRate();
            simtime_t wait = r > 0 ? deficit / r : horizon.dbl();
            scheduleAt(simTime() + std::max(wait, SimTime(1, SIMTIME_MS)), paceTimer);
        }
    }

    void handleClosedLoop(SensorData *sd)
    {
        int type = sd->getSourceType();
        if (type == SRC_ALARM) {
            sendToCloud(sd);                  // distinct events, never delayed
            return;
        }
        if (type == SRC_VITALS || type == SRC_OBD) {
            double dt = (simTime() - lastCritArrival).dbl();
            if (dt > 0 && lastCritArrival > SIMTIME_ZERO) {
                double inst = sd->getByteLength() / dt;
                critRate = critRate == 0 ? inst
                                         : rateEwmaAlpha * inst + (1 - rateEwmaAlpha) * critRate;
            }
            lastCritArrival = simTime();
            enqueueCritical(sd);
            drainClosedLoop();
            return;
        }
        // camera
        if (pendingBytes + sd->getByteLength() > cameraQueueCapacity) {
            numGateDropped++;
            emit(cameraGateDroppedSignal, numGateDropped);
            delete sd;
            return;
        }
        pendingBytes += sd->getByteLength();
        pending.insert(sd);
        emit(cameraPendingBytesSignal, pendingBytes);
        drainClosedLoop();
    }

    void onFeedback(const Ptr<const GatewayFeedback>& fb)
    {
        bytesAcked = fb->getBytesReceived();
        simtime_t gen = fb->getGeneratedAt();
        if (haveFb && gen > lastFbTime) {
            double dt = (gen - lastFbTime).dbl();
            double dbytes = (double)fb->getBytesReceived() - (double)lastFbBytes;
            if (dt > 0 && dbytes >= 0) {
                double inst = dbytes / dt;
                estRate = estRate == 0 ? inst
                                       : rateEwmaAlpha * inst + (1 - rateEwmaAlpha) * estRate;
                emit(estThroughputSignal, estRate * 8.0);
            }
        }
        lastFbBytes = fb->getBytesReceived();
        lastFbTime = gen;
        haveFb = true;
        if (policy == POLICY_ADAPTIVE || policy == POLICY_CTRL)
            adaptRate();
        else if (policy == POLICY_AIMD || policy == POLICY_AIMD_SELF)
            adaptRateAimd(fb);
        emit(inFlightBytesSignal, inFlight());
        drainClosedLoop();
    }

    virtual void handleMessageWhenUp(cMessage *msg) override
    {
        if (msg == paceTimer) {
            if (closedLoop())
                drainClosedLoop();
            else
                drainPending();
            return;
        }
        if (msg->arrivedOn("edgeIn")) {
            auto *sd = check_and_cast<SensorData *>(msg);
            if (!running || destAddress.isUnspecified()) {
                numDroppedNotRunning++;
                delete sd;
                return;
            }
            if (policy == POLICY_NONE) {
                sendToCloud(sd);
                return;
            }
            if (closedLoop()) {
                handleClosedLoop(sd);
                return;
            }
            if (sd->getSourceType() != SRC_CAMERA) {
                sendToCloud(sd);
                return;
            }
            handleCameraOpenLoop(sd);
            return;
        }
        socket.processMessage(msg);
    }

    virtual void socketDataArrived(UdpSocket *sock, Packet *packet) override
    {
        auto fb = packet->peekAtFront<GatewayFeedback>(b(-1), Chunk::PF_ALLOW_NULLPTR);
        if (fb != nullptr)
            onFeedback(fb);
        delete packet;
    }

    virtual void socketErrorArrived(UdpSocket *sock, Indication *indication) override { delete indication; }
    virtual void socketClosed(UdpSocket *sock) override {}

    virtual void finish() override
    {
        recordScalar("packetsSentToCloud", numSent);
        recordScalar("packetsDroppedAppDown", numDroppedNotRunning);
        recordScalar("cameraAdmitted", numAdmitted);
        recordScalar("cameraGateDropped", numGateDropped);
        recordScalar("cameraStaleDropped", numStaleDropped);
        recordScalar("criticalSuperseded", numCritSuperseded);
        recordScalar("cameraPendingAtEnd", pending.getLength());
        recordScalar("criticalPendingAtEnd", critQueue.getLength());
        recordScalar("bytesSent", (double)bytesSent);
        recordScalar("bytesAcked", (double)bytesAcked);
        recordScalar("finalBucketRateBps", bucketRate() * 8.0);
        recordScalar("aimdBackoffs", numBackoffs);
        recordScalar("aimdProbes", numProbes);
        // The age of whichever stream drives the controller: vitals under
        // aimd, camera under aimdSelf. The name is kept for continuity with
        // the exporter and earlier result sets.
        recordScalar("maxObservedVitalsAge", maxObservedAge);
        recordScalar("meanBucketRateBps", rateUpdates ? rateSum * 8.0 / rateUpdates : 0.0);
        ApplicationBase::finish();
    }

    ~EdgeApp()
    {
        cancelAndDelete(paceTimer);
        while (!pending.isEmpty())
            delete pending.pop();
        while (!critQueue.isEmpty())
            delete critQueue.pop();
    }
};

Define_Module(EdgeApp);

} // namespace paperrebuild

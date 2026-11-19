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

// sourceType codes (SensorData.msg): 0=wearable vitals, 1=OBD, 2=camera,
// 3=alarm, 4=evidence (synthesized here at escalation, not by a SensorSource)
static const int SRC_VITALS   = 0;
static const int SRC_OBD      = 1;
static const int SRC_CAMERA   = 2;
static const int SRC_ALARM    = 3;
static const int SRC_EVIDENCE = 4;

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

    // ---- the derived architecture + the escalation ----
    bool cameraTerminatesAtEdge = false;
    long evidenceBytes = 0;             // 0 disables evidence entirely
    long evidenceChunkBytes = 1400;
    long numCameraTerminated = 0;       // counted, never forwarded
    long numEvidenceEmitted = 0;        // chunks enqueued
    long numEvidenceDropped = 0;        // chunks the evidence buffer refused
    // Evidence chunks discarded for STALENESS, which is a different failure
    // from a buffer refusal and must not be pooled with it. Added 2026-11-12
    // after `evidenceChunksDropped` was found reading 0 through runs that were
    // discarding ~173 evidence chunks each: the discard sites below never
    // tested getSourceType(), so the loss landed only in `cameraStaleDropped`
    // -- a counter whose name says "camera" while the camera, under
    // `cameraTerminatesAtEdge=true`, never enters this queue at all.
    // Misattributed, not invisible. See docs/PHASE2_RESULT.md section 4.
    long numEvidenceStaleDropped = 0;
    long numEscalations = 0;
    long evidenceSeq = 0;

    simsignal_t cameraAdmittedSignal;
    simsignal_t cameraGateDroppedSignal;
    simsignal_t cameraPendingBytesSignal;
    simsignal_t cameraGateDelaySignal;
    simsignal_t inFlightBytesSignal;
    simsignal_t estThroughputSignal;
    simsignal_t bucketRateSignal;
    simsignal_t evidenceEmittedSignal;
    simsignal_t evidenceQueueDelaySignal;

    bool closedLoop() const { return policy >= POLICY_PRIO; }

    // The class the gate defers. Kept in ONE place for the same reason
    // dropsStaleCamera() is: the deferrable class changed when the
    // architecture was derived (camera used to cross the WAN, now evidence
    // does), and an inline type test would have had to change in four
    // places with nothing to catch a missed one.
    //
    // Under the derived architecture the deferrable class is EVIDENCE. In the
    // legacy configuration -- cameraTerminatesAtEdge=false, which every result
    // set before 2026-11-06 used -- it is CAMERA, exactly as before, so those
    // runs reproduce unchanged.
    bool isDeferrable(int type) const
    {
        if (type == SRC_EVIDENCE)
            return true;
        return type == SRC_CAMERA && !cameraTerminatesAtEdge;
    }

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
            cameraTerminatesAtEdge = par("cameraTerminatesAtEdge");
            evidenceBytes = par("evidenceBytes").intValue();
            evidenceChunkBytes = par("evidenceChunkBytes").intValue();
            if (evidenceChunkBytes < 1)
                throw cRuntimeError("evidenceChunkBytes must be >= 1B");
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
            evidenceEmittedSignal = registerSignal("evidenceEmitted");
            evidenceQueueDelaySignal = registerSignal("evidenceQueueDelay");
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

    // The gate's own contribution to delay, attributed to the right class.
    // Evidence and camera share the queue but answer different questions:
    // camera gate delay was a sensing-freshness cost, evidence gate delay is
    // a dispatch cost, and pooling them would make RQ2 unanswerable.
    void emitGateDelay(SensorData *sd)
    {
        simtime_t d = simTime() - sd->getArrivalTime();
        if (sd->getSourceType() == SRC_EVIDENCE)
            emit(evidenceQueueDelaySignal, d);
        else
            emit(cameraGateDelaySignal, d);
    }

    // ------------------------------------------------------------- escalation
    // An escalation is an ALERT plus the EVIDENCE the server verifies it with.
    // The alert leaves immediately and ungated, as alarms always have. The
    // evidence is chunked and handed to the deferrable path, so it competes
    // for the same uplink at the same instant -- which is the conflict RQ2
    // measures, not an artifact of this implementation.
    void escalate(SensorData *alarm)
    {
        long seq = alarm->getSequenceNumber();
        numEscalations++;
        sendToCloud(alarm);                 // consumes alarm; alert first
        if (evidenceBytes <= 0)
            return;                         // alarm-only: the earlier corpus
        long remaining = evidenceBytes;
        while (remaining > 0) {
            long len = std::min(remaining, evidenceChunkBytes);
            remaining -= len;
            // Created now, at the edge, because the edge is what detected the
            // event and produced the evidence. End-to-end delay for this class
            // is therefore measured from the detection instant, which is the
            // quantity that matters for dispatch.
            auto *ev = new SensorData("evidence");
            ev->setSourceType(SRC_EVIDENCE);
            ev->setSequenceNumber(seq * 1000000L + (evidenceSeq++ % 1000000L));
            ev->setByteLength(len);
            numEvidenceEmitted++;
            emit(evidenceEmittedSignal, numEvidenceEmitted);
            handleDeferrable(ev);
        }
    }

    // One entry point for the deferrable class, whichever policy is in force.
    void handleDeferrable(SensorData *sd)
    {
        if (policy == POLICY_NONE) {
            // No gate at all: evidence goes out the instant it is produced.
            // This is the baseline the managed policies are measured against,
            // and the arm in which the conflict should be worst.
            sendToCloud(sd);
            return;
        }
        if (closedLoop()) {
            enqueueDeferrableClosedLoop(sd);
            return;
        }
        handleCameraOpenLoop(sd);
    }

    // ---------------------------------------------------------------- open loop
    void drainPending()
    {
        refillTokens();
        while (!pending.isEmpty()) {
            auto *head = check_and_cast<SensorData *>(pending.front());
            // getCreationTime(), NOT getArrivalTime(). Evidence is built with
            // `new` inside escalate() and handed on by function call, never
            // SENT, so its arrival time is never stamped and reads 0 -- which
            // turned this test into `simTime() > cameraMaxAge` and discarded
            // EVERY pending chunk once the clock passed maxAge. That is what
            // produced C4.2's "dropPace delivers 45-47%". Creation time is set
            // by cMessage's constructor for both classes, and for a camera
            // frame it is also the better question: how old is this
            // OBSERVATION, not when did it reach the gate. Fixed 2026-11-12.
            if (policy == POLICY_DROPPACE
                && simTime() - head->getCreationTime() > cameraMaxAge) {
                pending.pop();
                pendingBytes -= head->getByteLength();
                numStaleDropped++;
                if (head->getSourceType() == SRC_EVIDENCE)
                    numEvidenceStaleDropped++;
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
            emitGateDelay(head);
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
                emitGateDelay(sd);
                sendToCloud(sd);
            }
            else {
                numGateDropped++;
                if (sd->getSourceType() == SRC_EVIDENCE) numEvidenceDropped++;
                emit(cameraGateDroppedSignal, numGateDropped);
                delete sd;
            }
            return;
        }
        if (pending.isEmpty() && tokens >= len) {
            tokens -= len;
            numAdmitted++;
            emit(cameraAdmittedSignal, numAdmitted);
            emitGateDelay(sd);
            sendToCloud(sd);
            return;
        }
        if (pendingBytes + len > cameraQueueCapacity) {
            numGateDropped++;
            if (sd->getSourceType() == SRC_EVIDENCE) numEvidenceDropped++;
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
            if (dropsStaleCamera()      // see the note in drainPending()
                && simTime() - head->getCreationTime() > cameraMaxAge) {
                pending.pop();
                pendingBytes -= head->getByteLength();
                numStaleDropped++;
                if (head->getSourceType() == SRC_EVIDENCE)
                    numEvidenceStaleDropped++;
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
            emitGateDelay(head);
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

    // The deferrable class under a closed-loop policy. Factored out of
    // handleClosedLoop so escalation evidence reaches exactly the same queue
    // by the same rules -- the gate is re-aimed at a new class, not rewritten
    // for it, which is what lets the measured rules (docs/PLAN_2026-11.md
    // §8.1 C4.1, C4.2) carry over instead of needing re-establishing.
    void enqueueDeferrableClosedLoop(SensorData *sd)
    {
        if (pendingBytes + sd->getByteLength() > cameraQueueCapacity) {
            numGateDropped++;
            if (sd->getSourceType() == SRC_EVIDENCE) numEvidenceDropped++;
            emit(cameraGateDroppedSignal, numGateDropped);
            delete sd;
            return;
        }
        pendingBytes += sd->getByteLength();
        pending.insert(sd);
        emit(cameraPendingBytesSignal, pendingBytes);
        drainClosedLoop();
    }

    void handleClosedLoop(SensorData *sd)
    {
        int type = sd->getSourceType();
        if (type == SRC_ALARM) {
            escalate(sd);                     // alert now, evidence behind it
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
        enqueueDeferrableClosedLoop(sd);       // camera (legacy) or evidence
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
            int type = sd->getSourceType();
            // The derived architecture: PRV-grade frames cost ~25.5 Mb/s and
            // the uplink benchmark is 3 Mb/s, so the inference is local and
            // raw frames never cross the WAN. Count and discard here -- the
            // sensor-link hop they already traversed is where their cost is
            // paid, and BleLink/WifiLink measure that.
            if (type == SRC_CAMERA && cameraTerminatesAtEdge) {
                numCameraTerminated++;
                delete sd;
                return;
            }
            // Escalation is two-part under every policy, including 'none':
            // the alert must not wait behind its own evidence.
            if (type == SRC_ALARM && evidenceBytes > 0) {
                escalate(sd);
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
            if (!isDeferrable(type)) {
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
        // Escalation accounting. cameraTerminatedAtEdge is recorded even when
        // zero so a result set states which architecture produced it rather
        // than leaving that to be inferred from the ini.
        recordScalar("cameraTerminatedAtEdge", numCameraTerminated);
        recordScalar("escalations", numEscalations);
        recordScalar("evidenceChunksEmitted", numEvidenceEmitted);
        recordScalar("evidenceChunksDropped", numEvidenceDropped);
        recordScalar("evidenceChunksStaleDropped", numEvidenceStaleDropped);
        // The two together are the evidence the server will never see. Scoring
        // a deferral policy on dispatch latency alone reads a faster decision
        // made on less evidence as an improvement -- see C4.2.
        recordScalar("evidenceChunksLost",
                     numEvidenceDropped + numEvidenceStaleDropped);
        recordScalar("evidenceBytesConfigured", (double)evidenceBytes);
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

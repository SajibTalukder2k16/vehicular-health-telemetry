package paperrebuild.simulations.corridorA;

import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.networklayer.ipv4.RoutingTableRecorder;
import inet.node.ethernet.Eth10G;
import inet.node.inet.Router;
import inet.node.inet.StandardHost;
import simu5g.common.binder.Binder;
import simu5g.common.carrierAggregation.CarrierAggregation;
import simu5g.nodes.PgwStandard;
import simu5g.nodes.LteUe;
import simu5g.nodes.eNodeB;
import simu5g.world.radio.LteChannelControl;
import paperrebuild.nodes.SensorRig;

// Family A controlled factorial: one instrumented vehicle drives a straight
// corridor past a chain of numEnb eNodeBs at equal inter-site distance.
// Speed, ISD, propagation scenario, background load, payload, and edge type
// are ini-level factors; everything else is emergent.
network CorridorNet
{
    parameters:
        int numEnb = default(4);
        bool x2Mesh = default(false);  // true: X2 between all site pairs (real layouts)
        @display("bgb=26000,600");
    submodules:
        channelControl: LteChannelControl {
            @display("p=100,50;is=s");
        }
        routingRecorder: RoutingTableRecorder {
            @display("p=100,120;is=s");
        }
        configurator: Ipv4NetworkConfigurator {
            @display("p=100,190;is=s");
        }
        binder: Binder {
            @display("p=100,260;is=s");
        }
        carrierAggregation: CarrierAggregation {
            @display("p=100,330;is=s");
        }
        server: StandardHost {
            @display("p=300,50;i=device/server");
        }
        router: Router {
            @display("p=450,50;i=device/smallrouter");
        }
        pgw: PgwStandard {
            @display("p=600,50;is=l");
        }
        eNodeB[numEnb]: eNodeB {
            @display("p=1000,250,row,2000;is=vl");
        }
        ue: LteUe {
            @display("p=200,400");
        }
        rig: SensorRig {
            @display("p=200,500");
        }
    connections:
        server.pppg++ <--> Eth10G <--> router.pppg++;
        router.pppg++ <--> Eth10G <--> pgw.filterGate;
        for i=0..numEnb-1 {
            pgw.pppg++ <--> Eth10G <--> eNodeB[i].ppp;
        }
        for i=0..numEnb-2, if !x2Mesh {
            eNodeB[i].x2++ <--> Eth10G <--> eNodeB[i+1].x2++;
        }
        for i=0..numEnb-2, for j=i+1..numEnb-1, if x2Mesh {
            eNodeB[i].x2++ <--> Eth10G <--> eNodeB[j].x2++;
        }
}

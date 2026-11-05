package paperrebuild.simulations.vehicle;

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

// One instrumented vehicle driving a corridor served by two LTE eNodeBs
// with X2 handover. Sensor data flows rig -> EdgeApp (in the UE) -> LTE
// uplink -> PGW -> cloud server. Vehicle motion comes from a SUMO trace.
network HealthVehicleNet
{
    parameters:
        @display("bgb=10000,600");
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
        eNodeB1: eNodeB {
            @display("p=2500,250;is=vl");
        }
        eNodeB2: eNodeB {
            @display("p=7500,250;is=vl");
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
        pgw.pppg++ <--> Eth10G <--> eNodeB1.ppp;
        pgw.pppg++ <--> Eth10G <--> eNodeB2.ppp;
        eNodeB1.x2++ <--> Eth10G <--> eNodeB2.x2++;
}

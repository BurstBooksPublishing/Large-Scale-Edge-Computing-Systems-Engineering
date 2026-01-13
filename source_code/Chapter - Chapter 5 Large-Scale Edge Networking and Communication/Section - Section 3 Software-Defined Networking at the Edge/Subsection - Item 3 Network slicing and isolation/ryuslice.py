from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

class SliceIsolation(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # map slice labels to meter ids and rates (bps)
        self.slice_cfg = {'control': (1, 5_000_000)}  # (meter_id, rate)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, MAIN_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        # install meters for each configured slice
        for slice_label, (meter_id, rate_bps) in self.slice_cfg.items():
            band = parser.OFPMeterBandDrop(rate=int(rate_bps/8), burst_size=0)
            meter_mod = parser.OFPMeterMod(datapath=datapath,
                                           command=ofp.OFPMC_ADD,
                                           flags=ofp.OFPMF_KBPS,
                                           meter_id=meter_id,
                                           bands=[band])
            datapath.send_msg(meter_mod)

            # flow: match on DSCP value assigned per slice (example: 0x2 for control)
            dscp_val = 0x02
            match = parser.OFPMatch(ip_dscp=dscp_val)
            actions = [
                parser.OFPActionMeter(meter_id),
                parser.OFPActionOutput(ofp.OFPP_NORMAL)
            ]
            inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
            mod = parser.OFPFlowMod(datapath=datapath, priority=100,
                                    match=match, instructions=inst)
            datapath.send_msg(mod)
# Run with: ryu-manager --verbose slice_isolation.py
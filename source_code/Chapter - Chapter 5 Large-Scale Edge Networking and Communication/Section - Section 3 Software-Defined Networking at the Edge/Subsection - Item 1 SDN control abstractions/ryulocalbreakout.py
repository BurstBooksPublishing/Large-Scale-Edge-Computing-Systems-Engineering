# Minimal production-ready Ryu app: install/remove flows via REST.
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3
from ryu.app.wsgi import WSGIApplication, ControllerBase, route
import json, logging

LOG = logging.getLogger('ryu.app.local_breakout')

class LocalBreakoutController(ControllerBase):
    def __init__(self, req, link, data, **config):
        super(LocalBreakoutController, self).__init__(req, link, data, **config)
        self.app = data['app']

    @route('local_breakout', '/intent', methods=['POST'])
    def add_intent(self, req, **kwargs):
        body = req.json if req.body else {}
        try:
            dp_id = int(body['dp_id'])
            ip_prefix = body['ip_prefix']            # e.g., "10.1.0.0/24"
            out_port = int(body['out_port'])
        except (KeyError, ValueError):
            return ('Bad Request', 400)
        self.app.install_local_breakout(dp_id, ip_prefix, out_port)
        return ('OK', 200)

class LocalBreakoutApp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(LocalBreakoutApp, self).__init__(*args, **kwargs)
        wsgi = kwargs['wsgi']
        wsgi.register(LocalBreakoutController, {'app': self})
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)

    def _monitor(self):
        while True:
            hub.sleep(10)  # periodic tasks, health checks

    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def _state_change_handler(self, ev):
        dp = ev.datapath
        self.datapaths[dp.id] = dp

    def install_local_breakout(self, dp_id, ip_prefix, out_port, priority=100):
        dp = self.datapaths.get(dp_id)
        if not dp:
            LOG.error('Datapath %s not connected', dp_id)
            return
        ofp = dp.ofproto; parser = dp.ofproto_parser
        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=ip_prefix)
        actions = [parser.OFPActionOutput(out_port)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=priority,
                                match=match, instructions=inst, idle_timeout=300)
        try:
            dp.send_msg(mod)
            LOG.info('Installed breakout on %s -> %s', dp_id, ip_prefix)
        except Exception as e:
            LOG.exception('Flow install failed: %s', e)
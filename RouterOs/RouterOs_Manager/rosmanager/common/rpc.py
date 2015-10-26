# yes

__author__ = 'Hardy.Zheng'


__all__ = [
    'init',
    'cleanup',
    'set_defaults',
    'RequestContextSerializer',
    'get_client',
    'get_server',
    'get_notifier',
]


from oslo_config import cfg
import oslo_messaging as messaging
from osprofiler import profiler


CONF = cfg.CONF
TRANSPORT = None
NOTIFIER = None


def init(conf):
    global TRANSPORT, NOTIFIER
    set_defaults(conf.oslo_messaging_rabbit.control_exchange)
    TRANSPORT = messaging.get_transport(conf,
                                        allowed_remote_exmods=[],
                                        aliases={})
    print TRANSPORT
    NOTIFIER = messaging.Notifier(TRANSPORT, serializer=None)


def cleanup():
    global TRANSPORT, NOTIFIER
    assert TRANSPORT is not None
    assert NOTIFIER is not None
    TRANSPORT.cleanup()
    TRANSPORT = NOTIFIER = None


def set_defaults(control_exchange):
    messaging.set_transport_defaults(control_exchange)


class RequestContextSerializer(messaging.Serializer):

    def __init__(self, base):
        self._base = base

    def serialize_entity(self, context, entity):
        if not self._base:
            return entity
        return self._base.serialize_entity(context, entity)

    def deserialize_entity(self, context, entity):
        if not self._base:
            return entity
        return self._base.deserialize_entity(context, entity)

    def serialize_context(self, context):
        _context = context.to_dict()
        prof = profiler.get()
        if prof:
            trace_info = {
                "hmac_key": prof.hmac_key,
                "base_id": prof.get_base_id(),
                "parent_id": prof.get_id()
            }
            _context.update({"trace_info": trace_info})
        return _context


def get_transport_url(url_str=None):
    return messaging.TransportURL.parse(CONF, url_str, {})


def get_client(target, version_cap=None, serializer=None):
    assert TRANSPORT is not None
    # serializer = RequestContextSerializer(serializer)
    serializer = messaging.JsonPayloadSerializer()
    return messaging.RPCClient(TRANSPORT,
                               target,
                               version_cap=version_cap,
                               serializer=serializer)


def get_server(target, endpoints, serializer=None):
    assert TRANSPORT is not None

    # Thread module is not monkeypatched if remote debugging is enabled.
    # Using eventlet executor without monkepatching thread module will
    # lead to unpredictable results.
    executor = "blocking"

    serializer = messaging.JsonPayloadSerializer()
    return messaging.get_rpc_server(TRANSPORT,
                                    target,
                                    endpoints,
                                    executor=executor,
                                    serializer=serializer)


def get_notifier(service=None, host=None, publisher_id=None):
    assert NOTIFIER is not None
    if not publisher_id:
        publisher_id = "%s.%s" % (service, host or CONF.host)
    return NOTIFIER.prepare(publisher_id=publisher_id)


def get_target(topic, version):
    if not version:
        version = '1.0'
    if not topic:
        topic = 'firewall'
    print topic, version
    return messaging.Target(exchange=CONF.oslo_messaging_rabbit.control_exchange,
                            topic=topic,
                            version=version)

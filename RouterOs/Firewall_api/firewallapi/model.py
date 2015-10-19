# yes

__author__ = 'yu.zhou'
__email__ = 'yu.zhou@yun-idc.com'


import inspect
import logging
import wsme
import six
import datetime
from __builtin__ import int
from wsme import types as wtypes


LOG = logging.getLogger(__name__)
operation_kind = wtypes.Enum(str, 'lt', 'le', 'eq', 'ne', 'ge', 'gt')


class _Base(object):

    def __init__(self, **kwds):
        self.fields = list(kwds)
        for k, v in kwds.iteritems():
            setattr(self, k, v)

    @classmethod
    def from_model(cls, m):
        return cls(**(m.as_dict()))

    def as_dict(self):
        d = {}
        for f in self.fields:
            v = getattr(self, f)
            if isinstance(v, _Base):
                v = v.as_dict()
            elif isinstance(v, list) and v and isinstance(v[0], _Base):
                v = [sub.as_dict() for sub in v]
            d[f] = v
        return d

    def as_dict_from_keys(self, keys):
        return dict((k, getattr(self, k))
                    for k in keys
                    if hasattr(self, k) and
                    getattr(self, k) != wsme.Unset)

    @classmethod
    def get_field_names(cls):
        fields = inspect.getargspec(cls.__init__)[0]
        return set(fields) - set(["self"])


class Query(_Base):
    """Query filter."""

    # The data types supported by the query.
    _supported_types = ['integer', 'float', 'string']

    # Functions to convert the data field to the correct type.
    _type_converters = {'integer': int,
                        'float': float,
                        'string': six.text_type}

    _op = None  # provide a default

    def get_op(self):
        return self._op or 'eq'

    def set_op(self, value):
        self._op = value

    field = wtypes.text
    "The name of the field to test"

    # op = wsme.wsattr(operation_kind, default='eq')
    # this ^ doesn't seem to work.
    op = wsme.wsproperty(operation_kind, get_op, set_op)
    "The comparison operator. Defaults to 'eq'."

    value = wtypes.text
    "The value to compare against the stored data"

    type = wtypes.text
    "The data type of value to compare against the stored data"

    def __repr__(self):
        # for logging calls
        return '<Query %r %s %r %s>' % (self.field,
                                        self.op,
                                        self.value,
                                        self.type)

    def as_dict(self):
        return self.as_dict_from_keys(['field', 'op', 'type', 'value'])


class Hardware_Info(_Base):

    cpu = int
    ram = int
    disk = [int]

    @classmethod
    def from_db_model(cls, m):
        return cls(cpu=int(m.cpu),
                   ram=int(m.ram),
                   disk=[dk.size for dk in m.disk])


class Vmip_v4(_Base):
    ip = wtypes.text
    mask = wtypes.text
    gateway = wtypes.text
    dns = wtypes.text

    @classmethod
    def from_db_model(cls, vmip_v4):
        if vmip_v4:
            return cls(ip=vmip_v4.ip,
                       mask=vmip_v4.mask,
                       gateway=vmip_v4.gateway,
                       dns=vmip_v4.dns)
        else:
            return cls()


class Vmip_v6(_Base):
    ip = wtypes.text
    mac = wtypes.text
    mask = wtypes.text
    gateway = wtypes.text
    dns = wtypes.text

    @classmethod
    def from_db_model(cls, vmip_v6):
        return cls()


class Net_Info(_Base):

    pipe_id = wtypes.text
    nic_id = wtypes.text
    mac = wtypes.text
    ip_v4 = Vmip_v4
    ip_v6 = Vmip_v6
    network_connect = wtypes.text

    @classmethod
    def from_db_model(cls, m):
        return cls(pipe_id=m.subinterface_id,
                   nic_id=m.nic_id,
                   mac=m.mac,
                   ip_v4=Vmip_v4.from_db_model(
                       m.vm_ipv4[0] if m.vm_ipv4 else None),
                   ip_v6=Vmip_v6.from_db_model(
                       m.vm_ipv6[0] if m.vm_ipv6 else None),
                   network_connect=m.network_connect)


class Vspc_Info(_Base):

    ip = wtypes.text
    port = int

    @classmethod
    def from_db_model(cls, vspc_m):
        if vspc_m:
            return cls(ip=vspc_m.vspc_server_ip,
                       port=int(vspc_m.port))
        else:
            return cls(ip='',
                       port=-1)


class Os_Info(_Base):

    os_type = wtypes.text
    os_version = wtypes.text
    os_bit = int
    hostname = wtypes.text
    vspc = Vspc_Info
    username = wtypes.text
    password = wtypes.text

    @classmethod
    def from_db_model(cls, m, vspc_info):
        return cls(os_type=m.os_type,
                   os_version=m.os_version,
                   os_bit=int(m.os_bit),
                   hostname=m.hostname,
                   username=m.username,
                   password=m.password,
                   vspc=Vspc_Info.from_db_model(vspc_info))


class Niclist(_Base):
    pipe_id = wtypes.text
    nic_id = wtypes.text

    @classmethod
    def from_db_model(cls, niclist):
        return cls(pipe_id=niclist["pipe_id"],
                   nic_id=niclist["nic_id"])


class Vm(_Base):
    vm_id = wtypes.text
    name = wtypes.text
    processing = int
    customer_id = wtypes.text
    customer_name = wtypes.text
    app_id = wtypes.text
    template_id = wtypes.text
    ram = int
    cpu = int
    nets = [Net_Info]
    disks = [int]
    status = wtypes.text
    hostname = wtypes.text
    password = wtypes.text
    nic_list = [Niclist]

    # vm hardware_info about
    # hardware_info:{cpu:$val,mem:$val,disk:$val,extend_disk:$val}
    hardware_info = Hardware_Info
    # vm net_info about net_info:{ip:$val}
    net_info = [Net_Info]
    # vm os_info about os_info:{os_type:$val,os_version:$val,
    os_info = Os_Info

    @classmethod
    def from_db_model(cls, m, serial_m):
        return cls(name=m.vm_name,
                   vm_id=m.vm_id,
                   status=m.status,
                   processing=m.processing if m.processing else 0,
                   template_id=m.template_id,
                   hardware_info=Hardware_Info.from_db_model(m.flavor_info[0]),
                   net_info=[
                       Net_Info.from_db_model(net) for net in m.vm_network_info],
                   os_info=Os_Info.from_db_model(m.vm_os_info[0], serial_m))

    @classmethod
    def from_model(cls, vm_id, niclist):
        return cls(vm_id=vm_id,
                   nic_list=[Niclist.from_db_model(nic) for nic in niclist])


class Vspc(_Base):

    vSPCServer_id = wtypes.text
    vcserver_name = wtypes.text
    cluster_name = wtypes.text
    vSPCServer_ip = wtypes.text
    is_enabled = wsme.wsattr(bool, default=True)
    instances_name = [wtypes.text]

    @classmethod
    def from_db_model(cls, vspc, cluster, instances):
        return cls(vSPCServer_id=vspc.vspc_id,
                   vcserver_name=cluster.pod.site.site_name if cluster else '',
                   cluster_name=cluster.cluster_name if cluster else '',
                   vSPCServer_ip=vspc.vspc_server_ip,
                   is_enabled=True if vspc.is_enable == 1 else False,
                   instances_name=[instance.vm_name for instance in instances])

    @classmethod
    def from_model(cls, vSPCServer_id):
        return cls(vSPCServer_id=vSPCServer_id)


class Template(_Base):
    template_id = wtypes.text
    name = wtypes.text
    os_type = wtypes.text
    os_version = wtypes.text
    os_bit = int
    cpu = int
    ram = int
    disk = int
    username = wtypes.text
    password = wtypes.text
    customer_id = wtypes.text
    template_type = wtypes.text
    vmware_tool = wsme.wsattr(bool)

    @classmethod
    def from_db_model(cls, m):
        return cls(template_id=m.template_id,
                   name=m.template_name,
                   os_type=m.os_type,
                   os_version=m.os_version,
                   os_bit=m.os_bit,
                   cpu=m.cpu,
                   ram=m.ram,
                   disk=m.disk,
                   username=m.username,
                   password=m.password,
                   template_type=m.template_type,
                   vmware_tool=True if m.vmware_tool else False,
                   customer_id=m.customer_id)

    @classmethod
    def from_model(cls, template_id):
        return cls(template_id=template_id)


class Action(_Base):
    action_id = wtypes.text
    vm_id = wtypes.text
    app_id = wtypes.text
    action = wtypes.text
    action_time = datetime.datetime
    status = wtypes.text
    nic_id = wtypes.text

    @classmethod
    def from_model(cls, action_id):
        return cls(action_id=action_id)

    @classmethod
    def from_db_model(cls, m):
        return cls(action_id=m.action_id,
                   vm_id=m.vm_id,
                   app_id=m.app_id,
                   action=m.action,
                   action_time=m.trigger_time,
                   status=m.status,
                   nic_id=m.nic_id)


class Zone(_Base):
    zone_id = wtypes.text
    zone_name = wtypes.text

    @classmethod
    def from_db_model(cls, m):
        return cls(zone_id=m.zone_id,
                   zone_name=m.zone_name)


class Site(_Base):
    site_id = wtypes.text
    name = wtypes.text
    site_code = wtypes.text
    zone = Zone

    @classmethod
    def from_db_model(cls, m):
        return cls(site_id=m.site_id,
                   name=m.site_name,
                   site_code=m.site_code,
                   zone=Zone.from_db_model(m.zone))


class App(_Base):
    customer_id = wtypes.text
    site_id = wtypes.text
    app_type = wtypes.text
    app_id = wtypes.text
    zone_id = wtypes.text

    @classmethod
    def from_model(cls, app_id):
        return cls(app_id=app_id)

    @classmethod
    def from_db_model(cls, m):
        return cls(zone_id=m.zone_id,
                   site_id=m.site_id,
                   app_id=m.app_id,
                   customer_id=m.customer_id)


class Nic(_Base):
    nic_id = wtypes.text
    vm_id = wtypes.text
    pipe_id = wtypes.text
    app_id = wtypes.text
    status = wtypes.text
    network_connect = wtypes.text

    @classmethod
    def from_model(cls, nic_id):
        return cls(nic_id=nic_id)

    @classmethod
    def from_db_model(cls, m):
        return cls(nic_id=m.nic_id,
                   vm_id=m.vm_id,
                   pipe_id=m.subinterface_id,
                   app_id=m.vm.app_id,
                   status=m.status,
                   network_connect=m.network_connect)


class Ip_V4(_Base):
    network_num = wtypes.text

    @classmethod
    def from_db_model(cls, v4):
        return cls(network_num=v4.network_num)


class Ip_V6(_Base):
    network_num = wtypes.text

    @classmethod
    def from_db_model(cls, v6):
        return cls(network_num=v6.network_num)


class Sub_Net(_Base):
    ip_v4 = [Ip_V4]
    ip_v6 = [Ip_V6]

    @classmethod
    def from_db_model(cls, v4s, v6s):
        return cls(ip_v4=[Ip_V4.from_db_model(v4) for v4 in v4s],
                   ip_v6=[Ip_V6.from_db_model(v6) for v6 in v6s])


class Pipe(_Base):
    pipe_id = wtypes.text
    app_id = wtypes.text
    pipe_type = wtypes.text
    qos = int
    status = wtypes.text
    sub_net = [Sub_Net]

    @classmethod
    def from_model(cls, pipe_id):
        return cls(pipe_id=pipe_id)

    @classmethod
    def from_db_model(cls, m):
        return cls(pipe_id=m.subinterface_id,
                   app_id=m.app_id,
                   pipe_type=m.vlan_type,
                   qos=m.qos,
                   status=m.status,
                   sub_net=[Sub_Net.from_db_model(m.network_ipv4, m.network_ipv6)])


class Subinterface_net(_Base):
    op_type = wtypes.text
    network_num = wtypes.text


# used for add or update interface
class Subinterface(Pipe):
    sub_net = Subinterface_net

    @classmethod
    def from_model(cls, pipe_id):
        return cls(pipe_id=pipe_id)


class Gic(_Base):
    gic_id = wtypes.text
    customer_id = wtypes.text
    app_list = [wtypes.text]
    qos = int

    @classmethod
    def from_model(cls, gic_id):
        return cls(gic_id=gic_id)

    @classmethod
    def from_db_model(cls, gic, gicextensions):
        return cls(gic_id=gic.gic_id,
                   qos=gic.qos,
                   customer_id=gic.customer_id,
                   app_list=[gicextension.app_id for gicextension in gicextensions
                             if gicextension.status == 'ok'])


class Gicextension(_Base):
    gicextension_id = wtypes.text
    gic_id = wtypes.text
    pipe_id = wtypes.text
    app_id = wtypes.text
    status = wtypes.text

    @classmethod
    def from_db_model(cls, gicextension):
        return cls(status=gicextension.status)

    @classmethod
    def from_model(cls, gicextension_id):
        return cls(gicextension_id=gicextension_id)

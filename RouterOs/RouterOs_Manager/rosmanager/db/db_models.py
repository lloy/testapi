
import six
import uuid
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relation
from oslo_utils import timeutils


__author__ = 'hardy.Zheng'


class _Base(object):
    """Base class for _BaseModels."""
    __table_args__ = {'mysql_charset': "utf8"}
    __table_initialized__ = False

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __getitem__(self, key):
        return getattr(self, key)

    def update(self, values):
        """Make the model object behave like a dict."""
        for k, v in six.iteritems(values):
            setattr(self, k, v)

Base = declarative_base(cls=_Base)


class Zone(Base):
    __tablename__ = 'zone'

    zone_id = Column(String(64), primary_key=True)
    zone_name = Column(String(40), nullable=False)

    def __init__(self, name):
        self.zone_id = str(uuid.uuid4())
        self.zone_name = name


class Site(Base):
    __tablename__ = 'site'

    site_id = Column(String(64), primary_key=True)
    site_name = Column(String(40), nullable=False)
    create_time = Column(DateTime, nullable=True)
    vcenter_ip = Column(String(24), nullable=False)
    vcenter_port = Column(Integer, nullable=False)
    vcenter_username = Column(String(40), nullable=False)
    vcenter_password = Column(String(64), nullable=False)
    zone_id = Column(String(64), ForeignKey('zone.zone_id'))
    zone = relation("Zone", backref='site', lazy='select')

    def __init__(self, name, ip, port, username, password):
        self.site_id = str(uuid.uuid4())
        self.site_name = name
        self.create_time = timeutils.utcnow()
        self.vcenter_ip = ip
        self.vcenter_port = port
        self.vcenter_username = username
        self.vcenter_password = password


class Pod(Base):
    __tablename__ = 'pod'

    pod_id = Column(String(64), primary_key=True)
    pod_name = Column(String(40), nullable=False)
    create_time = Column(DateTime, nullable=True)
    total_cpu = Column(Integer, nullable=False)
    total_ram = Column(Integer, nullable=False)
    used_cpu = Column(Integer, nullable=False)
    used_ram = Column(Integer, nullable=False)
    site_id = Column(String(64), ForeignKey('site.site_id'))
    site = relation("Site", backref='pod', lazy='select')

    def __init__(self, pod_name, tcpu, tram, ucpu, uram):
        self.pod_id = str(uuid.uuid4())
        self.pod_name = pod_name
        self.create_time = timeutils.utcnow()
        self.total_cpu = tcpu
        self.total_ram = tram
        self.used_cpu = ucpu
        self.used_ram = uram


class Cluster(Base):
    __tablename__ = 'cluster'

    cluster_id = Column(String(64), primary_key=True)
    cluster_name = Column(String(40), nullable=False)
    total_cpu = Column(Integer, nullable=False)
    total_ram = Column(Integer, nullable=False)
    used_cpu = Column(Integer, nullable=False)
    used_ram = Column(Integer, nullable=False)
    pod_id = Column(String(64), ForeignKey('pod.pod_id'))
    pod = relation("Pod", backref='cluster', lazy='select')

    def __init__(self, name, tcpu, tram, ucpu, uram):
        self.cluster_id = str(uuid.uuid4())
        self.cluster_name = name
        self.total_cpu = tcpu
        self.total_ram = tram
        self.used_cpu = ucpu
        self.used_ram = uram


class DataStore(Base):
    __tablename__ = 'datastore'

    datastore_id = Column(String(64), primary_key=True)
    datastore_name = Column(String(40), nullable=False)
    cluster_id = Column(String(64), ForeignKey('cluster.cluster_id'))
    cluster = relation("Cluster", backref='datastore', lazy='select')

    def __init__(self, name):
        self.datastore_id = str(uuid.uuid4())
        self.datastore_name = name


class Templates(Base):
    __tablename__ = 'template'

    template_id = Column(String(64), primary_key=True)
    template_name = Column(String(40), nullable=False)
    template_type = Column(String(64), nullable=False)
    os_type = Column(String(16), nullable=False)
    os_version = Column(String(16), nullable=False)
    os_bit = Column(Integer, nullable=False)
    cpu = Column(Integer, nullable=False)
    ram = Column(Integer, nullable=False)
    disk = Column(Integer, nullable=False)
    username = Column(String(40), nullable=False)
    password = Column(String(64), nullable=False)
    customer_id = Column(String(64), nullable=True)
    vmware_tool = Column(Integer, nullable=True)

    def __init__(self,
                 template_id,
                 template_name,
                 template_type,
                 os_type,
                 os_version,
                 os_bit,
                 cpu,
                 ram,
                 disk,
                 username,
                 password,
                 customer_id,
                 vmware_tool):
        self.template_id = template_id
        self.template_name = template_name
        self.template_type = template_type
        self.os_type = os_type
        self.os_bit = os_bit
        self.os_version = os_version
        self.cpu = cpu
        self.ram = ram
        self.disk = disk
        self.username = username
        self.password = password
        self.customer_id = customer_id
        self.vmware_tool = vmware_tool


class Route(Base):
    __tablename__ = 'route'

    route_id = Column(String(64), primary_key=True)
    route_name = Column(String(40), nullable=False)
    producer = Column(String(64), nullable=True)
    product_serial = Column(String(64), nullable=True)
    username = Column(String(40), nullable=False)
    password = Column(String(64), nullable=False)
    ip = Column(String(24), nullable=False)
    port = Column(Integer, nullable=False)
    create_time = Column(DateTime, nullable=True)
    site_id = Column(String(64), ForeignKey('site.site_id'))
    site = relation("Site", backref='route', lazy='select')

    def __init__(self,
                 name,
                 producer,
                 product_serial,
                 username,
                 password,
                 ip,
                 port,
                 site_id):
        self.route_id = str(uuid.uuid4())
        self.route_name = name
        self.producer = producer
        self.product_serial = product_serial
        self.username = username
        self.password = password
        self.ip = ip
        self.port = port
        self.create_time = timeutils.utcnow()
        self.site_id = site_id


class Interface(Base):
    __tablename__ = 'interface'

    interface_id = Column(String(64), primary_key=True)
    interface_name = Column(String(64), nullable=True)
    pod_id = Column(String(64), nullable=True)
    route_id = Column(String(64), ForeignKey('route.route_id'))
    route = relation("Route", backref='interface', lazy='select')

    def __init__(self, interface_name, pod_id):
        self.interface_id = str(uuid.uuid4())
        self.interface_name = interface_name
        self.pod_id = pod_id


class Subinterface(Base):
    __tablename__ = 'subinterface'

    subinterface_id = Column(String(64), primary_key=True)
    subinterface_name = Column(String(64), nullable=False)
    vlan_id = Column(Integer, nullable=False)
    vlan_type = Column(String(16), nullable=True)
    portgroup_name = Column(String(40), nullable=False)
    oid = Column(String(255), nullable=True)
    alloc_time = Column(DateTime, nullable=True)
    update_time = Column(DateTime, nullable=True)
    qos = Column(Integer)
    app_id = Column(String(64), nullable=True)
    gic_id = Column(String(64), nullable=True)
    status = Column(String(24), nullable=True)
    interface_id = Column(String(64), ForeignKey('interface.interface_id'))
    interface = relation("Interface", backref='subinterface', lazy='select')

    def __init__(self, id, name, vlan_id, portgroup_name):
        self.subinterface_id = id
        self.subinterface_name = name
        self.vlan_id = vlan_id
        self.portgroup_name = portgroup_name


class Network_Ipv4(Base):
    __tablename__ = 'network_ipv4'

    id = Column(Integer, primary_key=True)
    network_num = Column(String(32), nullable=False)
    network_address = Column(String(24), nullable=False)
    # "adding|deleting|ok"
    step = Column(String(24), nullable=False)
    # primary and secondary network flag in Switch
    level = Column(String(24), nullable=False)
    subinterface_id = Column(String(64), ForeignKey('subinterface.subinterface_id'))
    subinterface = relation("Subinterface", backref='network_ipv4', lazy='select')

    def __init__(self, network_num, network_address, level, step):
        self.network_num = network_num
        self.network_address = network_address
        self.level = level
        self.step = step


class Network_Ipv6(Base):
    __tablename__ = 'network_ipv6'

    id = Column(Integer, primary_key=True)
    network_num = Column(String(32), nullable=True)
    network_address = Column(String(24), nullable=True)
    # "adding|deleting|ok"
    step = Column(String(24), nullable=False)
    subinterface_id = Column(String(64), ForeignKey('subinterface.subinterface_id'))
    subinterface = relation("Subinterface", backref='network_ipv6', lazy='select')


class Gic(Base):
    __tablename__ = 'gic'

    gic_id = Column(String(64), primary_key=True)
    group_name = Column(String(40), nullable=False)
    core_name = Column(String(40), nullable=False)
    edge_name = Column(String(40), nullable=False)
    evi_id = Column(Integer, nullable=False)
    edge_sid = Column(Integer, nullable=False)
    alloc_time = Column(DateTime, nullable=True)
    qos = Column(Integer, nullable=True)
    status = Column(String(16), nullable=True)
    customer_id = Column(String(64), nullable=True)

    def __init__(self, group_name, core_name, edge_name, evi_id, edge_sid):
        self.gic_id = str(uuid.uuid4())
        self.group_name = group_name
        self.core_name = core_name
        self.edge_name = edge_name
        self.evi_id = evi_id
        self.edge_sid = edge_sid


class GicExtension(Base):
    __tablename__ = 'gicextension'

    gicextension_id = Column(String(64), primary_key=True)
    app_id = Column(String(64), nullable=False)
    gic_id = Column(String(64), nullable=False)
    subinterface_id = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    starttime = Column(DateTime, nullable=True)

    def __init__(self, gicextension_id, app_id, gic_id, subinterface_id, status):
        self.gicextension_id = gicextension_id
        self.app_id = app_id
        self.gic_id = gic_id
        self.subinterface_id = subinterface_id
        self.status = status
        self.starttime = timeutils.utcnow()


class App(Base):
    __tablename__ = 'app'

    app_id = Column(String(64), primary_key=True)
    customer_id = Column(String(64), nullable=False)
    zone_id = Column(String(64), nullable=False)
    site_id = Column(String(64), nullable=False)
    app_type = Column(String(64), nullable=True)
    create_time = Column(DateTime, nullable=True)
    pod_id = Column(String(64), ForeignKey('pod.pod_id'))
    pod = relation("Pod", backref='app', lazy='select')

    def __init__(self, app_id, customer_id, zone_id, site_id, pod_id, app_type):
        self.app_id = app_id
        self.customer_id = customer_id
        self.zone_id = zone_id
        self.site_id = site_id
        self.pod_id = pod_id
        self.app_type = app_type
        self.create_time = timeutils.utcnow()


class Vm(Base):
    __tablename__ = 'vm'

    vm_id = Column(String(64), primary_key=True)
    vm_name = Column(String(64), nullable=False)
    processing = Column(Integer, nullable=True)
    template_id = Column(String(64), nullable=False)
    customer_id = Column(String(64), nullable=False)
    site_name = Column(String(40), nullable=False)
    pod_name = Column(String(40), nullable=False)
    cluster_name = Column(String(40), nullable=False)
    datastore_name = Column(String(40), nullable=False)
    status = Column(String(16), nullable=False)
    create_time = Column(DateTime, nullable=False)
    update_time = Column(DateTime, nullable=True)
    configure_step = Column(String(40), nullable=False)
    app_id = Column(String(64), ForeignKey('app.app_id'))
    app = relation("App", backref='vm', lazy='select')

    def __init__(self,
                 vm_id,
                 vm_name,
                 temp_id,
                 customer_id,
                 site_name,
                 pod_name,
                 cluster_name,
                 datastore_name,
                 status,
                 configure_step,
                 app_id):
        self.vm_id = vm_id
        self.vm_name = vm_name
        self.template_id = temp_id
        self.customer_id = customer_id
        self.site_name = site_name
        self.pod_name = pod_name
        self.cluster_name = cluster_name
        self.datastore_name = datastore_name
        self.status = status
        self.configure_step = configure_step
        self.app_id = app_id
        self.create_time = timeutils.utcnow()


class Flavor_Info(Base):
    __tablename__ = 'flavor_info'

    flavor_id = Column(String(64), primary_key=True)
    cpu = Column(Integer, nullable=False)
    ram = Column(Integer, nullable=False)
    vm_id = Column(String(64), ForeignKey('vm.vm_id'))
    vm = relation("Vm", backref='flavor_info', lazy='select')

    def __init__(self, cpu, ram):
        self.flavor_id = str(uuid.uuid4())
        self.cpu = cpu
        self.ram = ram


class Disk(Base):
    __tablename__ = 'disk'

    id = Column(Integer, primary_key=True)
    size = Column(Integer, nullable=False)
    is_load = Column(Integer, nullable=False)
    flavor_id = Column(String(64), ForeignKey('flavor_info.flavor_id'))
    flavor_info = relation("Flavor_Info", backref='disk', lazy='select')

    def __init__(self, size, is_load):
        self.size = size
        self.is_load = is_load


class Vm_Network_Info(Base):
    __tablename__ = 'vm_network_info'

    nic_id = Column(String(64), primary_key=True)
    subinterface_id = Column(String(64), nullable=False)
    network_connect = Column(String(12), nullable=False)
    mac = Column(String(24), nullable=True)
    status = Column(String(12), nullable=True)
    vm_id = Column(String(64), ForeignKey('vm.vm_id'))
    vm = relation("Vm", backref='vm_network_info', lazy='select')

    def __init__(self, nic_id, subinterface_id, status, network_connect, vm_id):
        self.nic_id = nic_id
        self.subinterface_id = subinterface_id
        self.status = status
        self.network_connect = network_connect
        self.vm_id = vm_id


class Vm_Ipv4(Base):
    __tablename__ = 'vm_ipv4'

    id = Column(Integer, primary_key=True)
    ip = Column(String(24), nullable=False)
    mask = Column(String(24), nullable=False)
    gateway = Column(String(24), nullable=False)
    dns = Column(String(24), nullable=False)
    nic_id = Column(String(64), ForeignKey('vm_network_info.nic_id'))
    nic = relation("Vm_Network_Info", backref='vm_ipv4', lazy='select')

    def __init__(self, ip, mask, gateway, dns):
        self.ip = ip
        self.mask = mask
        self.gateway = gateway
        self.dns = dns


class Vm_Ipv6(Base):
    __tablename__ = 'vm_ipv6'

    id = Column(Integer, primary_key=True)
    ip = Column(String(24), nullable=True)
    nic_id = Column(String(64), ForeignKey('vm_network_info.nic_id'))
    nic = relation("Vm_Network_Info", backref='vm_ipv6', lazy='select')

    def __init__(self, ip):
        self.ip = ip


class Vm_Os_Info(Base):
    __tablename__ = 'vm_os_info'

    vm_os_id = Column(String(64), primary_key=True)
    hostname = Column(String(64), nullable=True)
    os_type = Column(String(64), nullable=False)
    os_version = Column(String(64), nullable=False)
    os_bit = Column(Integer, nullable=False)
    username = Column(String(64), nullable=False)
    password = Column(String(64), nullable=False)
    vm_id = Column(String(64), ForeignKey('vm.vm_id'))
    vm = relation("Vm", backref='vm_os_info', lazy='select')

    def __init__(self, hostname, os_type, os_version, os_bit, username, password):
        self.vm_os_id = str(uuid.uuid4())
        self.hostname = hostname
        self.os_type = os_type
        self.os_version = os_version
        self.os_bit = os_bit
        self.username = username
        self.password = password


class Action(Base):
    __tablename__ = 'action'

    action_id = Column(String(64), primary_key=True)
    app_id = Column(String(64), nullable=False)
    vm_id = Column(String(64), nullable=False)
    nic_id = Column(String(64), nullable=True)
    action = Column(String(16), nullable=False)
    trigger_time = Column(DateTime, nullable=False)
    status = Column(String(16), nullable=False)

    def __init__(self, action_id, app_id, vm_id, nic_id, action, status):
        self.action_id = action_id
        self.app_id = app_id
        self.vm_id = vm_id
        self.nic_id = nic_id
        self.action = action
        self.status = status
        self.trigger_time = timeutils.utcnow()


class Vspc_Info(Base):
    __tablename__ = 'vspc_info'

    vspc_id = Column(String(64), primary_key=True)
    site_id = Column(String(64), nullable=False)
    pod_id = Column(String(64), nullable=False)
    cluster_id = Column(String(64), nullable=False)
    vspc_server_ip = Column(String(24), nullable=False)
    is_enable = Column(Integer, nullable=False)

    def __init__(self, site_id, pod_id, cluster_id, ip, is_enable):
        self.vspc_id = str(uuid.uuid4())
        self.site_id = site_id
        self.pod_id = pod_id
        self.cluster_id = cluster_id
        self.vspc_server_ip = ip
        self.is_enable = is_enable


class Serial_Connection(Base):
    __tablename__ = 'serial_connection'

    connection_id = Column(String(64), primary_key=True)
    site_id = Column(String(64), nullable=False)
    pod_id = Column(String(64), nullable=False)
    cluster_id = Column(String(64), nullable=False)
    vm_name = Column(String(64), nullable=False)
    vspc_server_ip = Column(String(24), nullable=False)
    port = Column(Integer, nullable=False)
    is_connected = Column(Integer, nullable=False)
    vspc_id = Column(String(64), ForeignKey('vspc_info.vspc_id'))
    vspc = relation("Vspc_Info", backref='serial_connection')

    def __init__(self,
                 conn_id,
                 site_id,
                 pod_id,
                 cluster_id,
                 vm_name,
                 ip,
                 port,
                 is_connected,
                 vspc_id):
        self.connection_id = conn_id
        self.site_id = site_id
        self.pod_id = pod_id
        self.cluster_id = cluster_id
        self.vm_name = vm_name
        self.vspc_server_ip = ip
        self.port = port
        self.is_connected = is_connected
        self.vspc_id = vspc_id

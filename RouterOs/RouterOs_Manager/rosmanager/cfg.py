from oslo_config import cfg

__author__ = 'Hardy.zheng'


# MYSQL
mysql_group = cfg.OptGroup(
    name='mysql', title='MySQL engine',
    help="Oslo engine group designed for MySQL datastore")
mysql_opts = [
    cfg.StrOpt('engine',
               default='mysql+mysqldb://admin:123456@localhost/automatic_product?charset=utf8',
               help='Default mysql engine url.'),
    ]


# RABBITMQ
rabbit_group = cfg.OptGroup(
    name='oslo_messaging_rabbit', title='rabbitmq',
    help='rabbitmq options group designed for firewall api')
rabbit_opts = [
    cfg.StrOpt('topic', default='firewall', help='amqp route key'),
    cfg.StrOpt('control_exchange', default='gic', help='amqp control exchange key')
]

# ROUTEROS
router_group = cfg.OptGroup(
    name='routeros', title='router os',
    help='routeros options group designed for routeos manager')
router_opts = [
    cfg.StrOpt('host', default='0.0.0.0', help='routeos ip address'),
    cfg.StrOpt('username', default='admin', help='routeos username'),
    cfg.StrOpt('password', default='admin', help='routeos password')
]


common_opts = [
    cfg.StrOpt('site_name', default='beijing', help='routeos manager sitename'),
    cfg.IntOpt('report_interval', default=30,
               help='The interval (in seconds) which periodic tasks are run.'),
    cfg.StrOpt('host', default='0.0.0.0', help='manager address'),
    cfg.StrOpt('taskmanager_manager', help='Router Os Manager'),
]

CONF = cfg.CONF

# group register
CONF.register_group(mysql_group)
CONF.register_group(rabbit_group)
CONF.register_group(router_group)

# section register
CONF.register_opts(mysql_opts, group=mysql_group)
CONF.register_opts(rabbit_opts, group=rabbit_group)
CONF.register_opts(router_opts, group=router_group)
CONF.register_opts(common_opts)


def parse_args(argv, default_config_files=None):
    from rosmanager import __version__
    cfg.CONF(argv,
             project='rosmanager',
             version=__version__)

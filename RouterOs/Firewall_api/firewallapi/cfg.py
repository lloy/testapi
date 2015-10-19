#!/usr/bin/env python
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

# LOG
log_group = cfg.OptGroup(
    name='log', title='Log Option',
    help='Log options group designed for firewall api')
log_opts = [
    cfg.StrOpt('handler', default='rotating', help='default log handler'),
    cfg.StrOpt('path', default='/var/log/firewallapi/firewallapi.log', help='default log path'),
    cfg.IntOpt('max_size', default=10, help='default log max size, unit is MB'),
    cfg.IntOpt('back_count', default=5, help='default log back count'),
    cfg.StrOpt('level', default='0', help='default log level')
    ]

# RABBITMQ
rabbit_group = cfg.OptGroup(
    name='oslo_messaging_rabbit', title='rabbitmq',
    help='rabbitmq options group designed for firewall api')
rabbit_opts = [
    cfg.StrOpt('topic', default='firewall', help='amqp route key'),
    cfg.StrOpt('control_exchange', default='gic', help='amqp control exchange key')
]

common_opts = [
    cfg.StrOpt('host', default='0.0.0.0', help='default api server address'),
    cfg.IntOpt('port', default=5026, help='default api server port'),
    cfg.StrOpt('paste_config',
               default='/etc/firewallapi/api_paste.ini',
               help='default api server address'),
]

CONF = cfg.CONF

# group register
CONF.register_group(mysql_group)
CONF.register_group(log_group)
CONF.register_group(rabbit_group)

# section register
CONF.register_opts(mysql_opts, group=mysql_group)
CONF.register_opts(log_opts, group=log_group)
CONF.register_opts(rabbit_opts, group=rabbit_group)
CONF.register_opts(common_opts)


def parse_args(argv, default_config_files=None):
    from firewallapi import __version__
    cfg.CONF(argv,
             project='firewallapi',
             version=__version__)

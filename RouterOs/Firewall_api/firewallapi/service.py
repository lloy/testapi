#!/usr/bin/env python
#
# Author: hardy.Zheng <wei.zheng@yun-idc.com>
#

# from firewallapi.log import Logger
# from firewallapi import log
from firewallapi import rpc
from oslo_log import log
from firewallapi import cfg


def prepare_service(argv):
    # import gettext
    # gettext.install('firewallapi', unicode=1)
    conf = cfg.CONF
    log.register_options(conf)
    # log_levels = (cfg.CONF.default_log_levels + ['firewallapi=DEBUG'])
    # log.set_defaults(default_log_levels=log_levels)
    cfg.parse_args(argv)
    print '****** paste_config', conf.paste_config
    print '***** log_config_append', conf.log_config_append
    print conf.log_file
    print conf.log_dir
    print 'conf.watch-log-file', conf.watch_log_file
    print 'conf.debug', conf.debug

    log.setup(conf, 'firewallapi')
    rpc.init(conf)
    print 'kumbo version: %s' % conf.oslo_messaging_rabbit.kombu_ssl_version
    print 'control_exchange: %s' % conf.control_exchange

# yes

__author__ = 'Hardy.zheng'


from oslo_log import log as logging
import oslo_messaging as messaging
from oslo_service import periodic_task

import rosmanager
from rosmanager import cfg
from rosmanager.common.context import RouterOsContext

LOG = logging.getLogger(__name__)
CONF = cfg.CONF
rpc_version = rosmanager.__version__


class Manager(periodic_task.PeriodicTasks):

    target = messaging.Target(version=rpc_version)

    def __init__(self):
        # super(Manager, self).__init__(CONF)
        self.admin_context = RouterOsContext()
        LOG.info('Manager init ok')

    def test(self, ctx, **kwargs):
        print '*' * 10, 'test'
        print ctx
        print kwargs
        print '*' * 10, 'test'
        return kwargs

    def add(self, ctx, **kwargs):
        LOG.info('********* add: ')
        LOG.info('**** ctx : %s' % ctx)
        LOG.info('**** kwargs : %s' % kwargs)
        return kwargs

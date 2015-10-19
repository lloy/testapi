# yes

__author__ = 'hardy.Zheng'
__email__ = 'wei.zheng@yun-idc.com'


from pecan import hooks
from firewallapi.common.session import Connection
from firewallapi import __version__
from firewallapi import rpc


class APIHook(hooks.PecanHook):

    def __init__(self):
        raise NotImplementedError('API Not Implemented')

    def before(self, state):
        raise NotImplementedError('API Not Implemented')


class DBHook(hooks.PecanHook):

    def __init__(self, engine_url):
        self.db_connection = Connection(engine_url)

    def before(self, state):
        state.request.db_connection = self.db_connection


class MessageHook(hooks.PecanHook):

    def __init__(self, conf):
        target = rpc.get_target(conf.oslo_messaging_rabbit.topic, __version__)
        self.client = rpc.get_client(target)

    def before(self, state):
        state.request.client = self.client

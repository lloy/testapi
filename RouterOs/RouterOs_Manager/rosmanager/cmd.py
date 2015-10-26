__author__ = 'Hardy.zheng'

program = 'rosmanager'


def startup(conf, topic):

    from oslo_service import service as os_service
    from rosmanager import service as ros_service
    from rosmanager import __version__
    service = ros_service.RpcService(binary=program,
                                     manager=conf.taskmanager_manager,
                                     topic=topic,
                                     rpc_api_version=__version__)
    launcher = os_service.launch(conf, service)
    launcher.wait()


def main(argv):
    from rosmanager import cfg
    from oslo_log import log as logging

    conf = cfg.CONF
    logging.register_options(conf)
    cfg.parse_args(argv)

    # initialize
    logging.setup(conf, program)

    from rosmanager.common import rpc
    rpc.init(conf)
    print conf.control_exchange

    # from rosmanager import db
    # db.configure_db(conf)

    # start router os manager
    startup(conf, conf.oslo_messaging_rabbit.topic)

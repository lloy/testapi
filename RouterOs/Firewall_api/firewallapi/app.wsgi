# -*- mode: python -*-
#
#
# Author: Hardy.zheng <wei.zheng@yun-idc>
#
#
"""Use this file for deploying the API under mod_wsgi.

See http://pecan.readthedocs.org/en/latest/deployment.html for details.
"""
#from firewallapi import service
from firewallapi import app

## Initialize the oslo configuration library and logging
#service.prepare_service([])
application = app.load_app()

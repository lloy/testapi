#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

"""Command line tool for creating meter for cds.
"""
from firewallapi import app
from firewallapi import service


def api(argv):
    service.prepare_service(argv)
    app.build_server()

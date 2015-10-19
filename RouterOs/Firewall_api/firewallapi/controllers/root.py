#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: Hardy.zheng <wei.zheng@yun-idc>
#

import pecan

from firewallapi.controllers.vm import VmController


class RootController(object):

    vm = VmController()

    @pecan.expose(generic=True, template='index.html')
    def index(self):
        return dict()

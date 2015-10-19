#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author: Hardy.zheng <wei.zheng@yun-idc>
#

import logging
# import traceback
import wsmeext.pecan as wsme_pecan
from pecan import rest
from pecan import request
from firewallapi.model import Vm
from firewallapi import exc


LOG = logging.getLogger('firewallapi')


class VmController(rest.RestController):

    @wsme_pecan.wsexpose([Vm])
    def get_all(self, q=None):

        LOG.debug('call list meter interface')
        LOG.info('call list meter interface')
        print '*********** list meter'
        vms = []
        ctxt = {'ceo': 'laoqusb'}
        kwargs = {'sb': 'cds', 'eg': 'gic'}

        request.client.cast(ctxt, 'add', **kwargs)
        return vms
        # try:
            # db_vms = request.db_connection.list_vm_meter()
            # if not db_vms:
                # return vms
            # for vm in db_vms:
                # if vm.status == 'deleted':
                    # continue
                # vms.append(Vm.from_db_model(vm))
            # return vms
        # except Exception, e:
            # LOG.error('list meter error : %s' % str(e))
            # raise exc.ApiBaseError('other error', "00201")

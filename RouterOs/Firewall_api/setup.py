#!/usr/bin/env python
# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
#
# Author: Hardy.zheng <lenocooool@gmail.com>

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# THIS FILE IS MANAGED BY THE GLOBAL REQUIREMENTS REPO - DO NOT EDIT


from setuptools import setup, find_packages

# In python < 2.7.4, a lazy loading of package `pbr` will break
# setuptools if some other modules registered functions in `atexit`.
# solution from: http://bugs.python.org/issue15881#msg170215

setup(
    name='firewallapi',
    version='1.0',
    description='firewallapi',
    author='hardy.Zheng',
    author_email='lenocooool@gmail.com',
    install_requires=[
        'lxml>=2.3',
        'pecan>=0.4.5',
        'oslo.config>=1.11.0',
        'oslo.messaging>=1.8.0',
        'oslo.log>=1.1.0',
        'wsme>=0.6',
        'six>=1.7.0',
        'pastedeploy>=1.5.0',
        'paste>=1.7',
        'werkzeug>=0.7',
        'babel>=0.8',
        'simplejson>=3.0',
        'webob>=1.2.3',
        'six>=1.7.0',
        'jsonschema>=2.0.0,<3.0.0',
        'jsonpath-rw>=1.2.0,<2.0',
        'anyjson>=0.3.3',
        'sqlalchemy>=0.7'],

    packages=find_packages(),
    namespace_packages=['firewallapi'],
    scripts=['firewall-api'],
    data_files=[('/etc/init.d', ['etc/init.d/firewallapi']),
                ('/etc/firewallapi', ['etc/firewall_api.cfg', 'etc/api_paste.ini']),
                ('/var/log/firewallapi', [])
                ],
    include_package_data=True
    )

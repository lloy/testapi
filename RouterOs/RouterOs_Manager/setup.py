from setuptools import setup, find_packages

__author__ = 'Hardy.zheng'
__version = '1.0'

setup(
    name='RouterOsManager',
    version=__version,
    description='routeros manager ',
    author='hardy.Zheng',
    author_email='wei.zheng@yun-idc.com',
    install_requires=[
        'eventlet>=0.13.0',
        'six>=1.7.0',
        'oslo.config>=1.11.0',
        'oslo.messaging>=1.8.0',
        'oslo.log>=1.5',
        'oslo.context>=0.7',
        'oslo.utils>=2.5',
        'oslo.service>=0.10.0',
        'netaddr>=0.5.0',
        'stevedore>=0.14',
        'anyjson>=0.3.3'],
    packages=find_packages(),
    scripts=['routeros-manager'],
    data_files=[('/etc/init.d', ['etc/init.d/routeros_manager']),
                ('/etc/rosmanager/', ['etc/routeros_manager.cfg']),
                ('/var/log/rosmanager', [])],
    namespace_packages=['rosmanager'],
    include_package_data=True,
    )

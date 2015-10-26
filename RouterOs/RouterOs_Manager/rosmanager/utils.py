import os
import datetime
from stevedore import driver
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


__author__ = 'Hardy.zheng'
USE_LAZY = False


def fixpath(p):
    return os.path.abspath(os.path.expanduser(p))


def utcnow():
    """Overridable version of utils.utcnow."""
    return datetime.datetime.utcnow()


def now():
    return datetime.datetime.now().replace(second=0, microsecond=0)


def delta_seconds(before, after):
    """Return the difference between two timing objects.

    Compute the difference in seconds between two date, time, or
    datetime objects (as a float, to microsecond resolution).
    """
    delta = after - before
    return total_seconds(delta)


def total_seconds(delta):
    """Return the total seconds of datetime.timedelta object.

    Compute total seconds of datetime.timedelta, datetime.timedelta
    doesn't have method total_seconds in Python2.6, calculate it manually.
    """
    try:
        return delta.total_seconds()
    except AttributeError:
        return ((delta.days * 24 * 3600) + delta.seconds +
                float(delta.microseconds) / (10 ** 6))


def get_manager(namespace, name, load=True, args=()):
    return driver.DriverManager(
        namespace=namespace,
        name=name,
        invoke_on_load=load,
        invoke_args=args)

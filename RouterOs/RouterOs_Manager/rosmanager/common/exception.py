
__author__ = 'Hardy.zheng'
import six


class NotAllocInstance(Exception):
    pass


class EsxiNotConnect(Exception):
    pass


class NoExistSite(Exception):
    pass


class BadAggregate(Exception):
    pass


class NotAllocIp(Exception):
    pass


class TaskNotFound(Exception):
    pass


class BaseError(Exception):

    def __init__(self, message, errno='0000-000-00'):
        self.msg = message
        self.code = errno
        super(BaseError, self).__init__(self.msg, self.code)


class VspcException(BaseError):

    """
    errno = 0000-001-00
    """

    def __init__(self, message, errno='00-01-00'):
        super(VspcException, self).__init__(message, errno)


class NoSupportChanged(VspcException):
    pass


class ErrorKwargs(VspcException):
    pass


class NotAllocVlan(VspcException):
    pass


class NotAllowUpdate(VspcException):
    pass


class VlanIdAlreadyExist(VspcException):
    pass


class UnknownVlanId(VspcException):
    pass


class NotAllowDelete(VspcException):
    pass


class NotFoundValue(VspcException):
    pass


class NotFoundKey(VspcException):
    pass


class InvalidGic(VspcException):
    pass


class VlanTypeError(VspcException):
    pass


class NotSetPoller(VspcException):
    pass


class SetPollerError(VspcException):
    pass


class NotRunMethod(VspcException):
    pass


class ConfigureException(VspcException):
    pass


class NotSection(VspcException):
    pass


class NotActionSection(VspcException):
    pass


class NotPipeSection(VspcException):
    pass


class NotGicSection(VspcException):
    pass


class DbParameterError(VspcException):
    pass


class NotSetIp(VspcException):
    pass


class LoginError(VspcException):
    pass


class MultipleKeys(VspcException):
    pass


class MultipleResultsFound(VspcException):
    pass


class NoResultFound(VspcException):
    pass


class DBError(Exception):
    """Wraps an implementation specific exception."""
    def __init__(self, inner_exception=None):
        self.inner_exception = inner_exception
        super(DBError, self).__init__(six.text_type(inner_exception))


class DBDuplicateEntry(DBError):
    """Wraps an implementation specific exception."""
    def __init__(self, columns=[], inner_exception=None):
        self.columns = columns
        super(DBDuplicateEntry, self).__init__(inner_exception)


class DBDeadlock(DBError):
    def __init__(self, inner_exception=None):
        super(DBDeadlock, self).__init__(inner_exception)


class DBInvalidUnicodeParameter(Exception):
    message = "Invalid Parameter: Unicode is not supported by the current database."


class DbMigrationError(DBError):
    """Wraps migration specific exception."""
    def __init__(self, message=None):
        super(DbMigrationError, self).__init__(message)


class DBConnectionError(DBError):
    """Wraps connection specific exception."""
    pass


class NotFoundConfigureFile(VspcException):
    """
    errno = 0000-001-01
    """
    def __init__(self, message):
        errno = '0000-001-01'
        super(NotFoundConfigureFile, self).__init__(message, errno)

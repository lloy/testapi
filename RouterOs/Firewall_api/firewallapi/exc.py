# yes

__author__ = 'Hardy.zheng'
__email__ = 'wei.zheng@yun-idc.com'


import pecan
import simplejson as json
import six


class ClientSideError(RuntimeError):
    def __init__(self, msg=None, status_code=400):
        self.msg = msg
        self.code = status_code
        super(ClientSideError, self).__init__(self.faultstring)

    @property
    def faultstring(self):
        if self.msg is None:
            return str(self)
        elif isinstance(self.msg, six.text_type):
            return self.msg
        else:
            return six.u(self.msg)


class ApiBaseError(ClientSideError):

    def __init__(self, error, faultcode=00000, status_code=400):
        self.faultcode = faultcode
        kw = dict(msg=unicode(error), faultcode=faultcode)
        self.error = json.dumps(kw)
        pecan.response.translatable_error = error
        super(ApiBaseError, self).__init__(self.error, status_code)


class ExistError(ApiBaseError):
    def __init__(self, error, faultcode):
        super(ExistError, self).__init__(error, faultcode, status_code=404)


class NotFound(ApiBaseError):
    def __init__(self, error, faultcode):
        super(NotFound, self).__init__(error, faultcode, status_code=404)


class ParameterError(ApiBaseError):
    def __init__(self, error, faultcode):
        super(ParameterError, self).__init__(error, faultcode, status_code=400)


class NotSupportType(ApiBaseError):
    def __init__(self, error, faultcode):
        super(NotSupportType, self).__init__(error, faultcode, status_code=501)


class ApiNotAllocVlan(ApiBaseError):
    def __init__(self, error, faultcode):
        super(ApiNotAllocVlan, self).__init__(error, faultcode, status_code=405)


class ApiNotAllowUpdate(ApiBaseError):
    def __init__(self, error, faultcode):
        super(ApiNotAllowUpdate, self).__init__(error, faultcode, status_code=405)


class ApiNotAllowDelete(ApiBaseError):
    def __init__(self, error, faultcode):
        super(ApiNotAllowDelete, self).__init__(error, faultcode, status_code=405)


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


class ErrorKwargs(Exception):
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
    """
    errno = 0000-001-02
    """
    pass


class SetPollerError(Exception):
    pass


class NotRunMethod(BaseError):
    """
    errno = 0000-003-01
    """
    pass


class TaskNotFound(Exception):
    pass


class DbParameterError(VspcException):
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


class NoResultFound(DBError):
    pass


class AgentException(Exception):

    def __init__(self, message, errno='0000-000-00'):
        self.msg = message
        self.code = errno
        super(AgentException, self).__init__(self.msg, self.code)


class ConfigureException(AgentException):
    """
    errno = 0000-001-01
    """
    def __init__(self, message, errno='0000-001-00'):
        super(ConfigureException, self).__init__(message, errno)


class NotFoundConfigureFile(ConfigureException):
    """
    errno = 0000-001-01
    """
    def __init__(self, message):
        errno = '0000-001-01'
        super(NotFoundConfigureFile, self).__init__(message, errno)

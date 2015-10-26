from oslo_context import context


__author__ = 'Hardy.Zheng'


class RouterOsContext(context.RequestContext):
    """
    Stores information about the security context under which the user
    accesses the system, as well as additional request information.
    """
    def __init__(self, **kwargs):
        self.timeout = kwargs.pop('timeout', None)
        super(RouterOsContext, self).__init__(**kwargs)

    def to_dict(self):
        parent_dict = super(RouterOsContext, self).to_dict()
        parent_dict.pop('auth_token')
        parent_dict.pop('tenant')
        parent_dict.pop('user')
        parent_dict.pop('resource_uuid')
        return parent_dict

    @classmethod
    def from_dict(cls, values):
        return cls(**values)

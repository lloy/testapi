
"""
    Session Handling for SQLAlchemy backend.
    Recommended ways to use sessions within this framework:
"""

__author__ = 'hardy.Zheng'

import uuid
import functools
import logging
import re
import random
import time
import six
import sqlalchemy.orm

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import exc as sqla_exc
from sqlalchemy import or_
from sqlalchemy.sql.expression import literal_column
from sqlalchemy.orm import joinedload_all
from sqlalchemy.orm import subqueryload_all
from firewallapi.common.utils import utcnow
from firewallapi.common import db_models as models
from firewallapi import exc


LOG = logging.getLogger(__name__)

_DUP_KEY_RE_DB = {
    "mysql": (re.compile(r"^.*\(1062,.*'([^\']+)'\"\)$"),),
}


def _raise_if_duplicate_entry_error(integrity_error, engine_name):
    """Raise exception if two entries are duplicated.

    In this function will be raised DBDuplicateEntry exception if integrity
    error wrap unique constraint violation.
    """

    def get_columns_from_uniq_cons_or_name(columns):
        # note(vsergeyev): UniqueConstraint name convention: "uniq_t0c10c2"
        #                  where `t` it is table name and columns `c1`, `c2`
        #                  are in UniqueConstraint.
        uniqbase = "uniq_"
        if not columns.startswith(uniqbase):
            if engine_name == "postgresql":
                return [columns[columns.index("_") + 1:columns.rindex("_")]]
            return [columns]
        return columns[len(uniqbase):].split("0")[1:]

    if engine_name not in ("mysql"):
        return

    # FIXME(johannes): The usage of the .message attribute has been
    # deprecated since Python 2.6. However, the exceptions raised by
    # SQLAlchemy can differ when using unicode() and accessing .message.
    # An audit across all three supported engines will be necessary to
    # ensure there are no regressions.
    for pattern in _DUP_KEY_RE_DB[engine_name]:
        match = pattern.match(integrity_error.message)
        if match:
            break
    else:
        return

    # NOTE(mriedem): The ibm_db_sa integrity error message doesn't provide the
    # columns so we have to omit that from the DBDuplicateEntry error.
    columns = ''
    columns = match.group(1)
    columns = get_columns_from_uniq_cons_or_name(columns)
    raise exc.DBDuplicateEntry(columns, integrity_error)


# NOTE(comstud): In current versions of DB backends, Deadlock violation
# messages follow the structure:
#
# (OperationalError) (1213, 'Deadlock found when trying to get lock; try '
#                     'restarting transaction') <query_str> <query_args>
_DEADLOCK_RE_DB = {
    "mysql": re.compile(r"^.*\(1213, 'Deadlock.*")
}


def _raise_if_deadlock_error(operational_error, engine_name):
    """Raise exception on deadlock condition.

    Raise DBDeadlock exception if OperationalError contains a Deadlock
    condition.
    """
    re = _DEADLOCK_RE_DB.get(engine_name)
    if re is None:
        return
    # FIXME(johannes): The usage of the .message attribute has been
    # deprecated since Python 2.6. However, the exceptions raised by
    # SQLAlchemy can differ when using unicode() and accessing .message.
    # An audit across all three supported engines will be necessary to
    # ensure there are no regressions.
    m = re.match(operational_error.message)
    if not m:
        return
    raise exc.DBDeadlock(operational_error)


def _wrap_db_error(f):
    @functools.wraps(f)
    def _wrap(self, *args, **kwargs):
        try:
            assert issubclass(
                self.__class__, sqlalchemy.orm.session.Session
            ), ('_wrap_db_error() can only be applied to methods of '
                'subclasses of sqlalchemy.orm.session.Session.')

            return f(self, *args, **kwargs)
        except UnicodeEncodeError:
            raise exc.DBInvalidUnicodeParameter()
        except sqla_exc.OperationalError as e:
            _raise_if_db_connection_lost(e, self.bind)
            _raise_if_deadlock_error(e, self.bind.dialect.name)
            # NOTE(comstud): A lot of code is checking for OperationalError
            # so let's not wrap it for now.
            raise
        # note(boris-42): We should catch unique constraint violation and
        # wrap it by our own DBDuplicateEntry exception. Unique constraint
        # violation is wrapped by IntegrityError.
        except sqla_exc.IntegrityError as e:
            # note(boris-42): SqlAlchemy doesn't unify errors from different
            # DBs so we must do this. Also in some tables (for example
            # instance_types) there are more than one unique constraint. This
            # means we should get names of columns, which values violate
            # unique constraint, from error message.
            _raise_if_duplicate_entry_error(e, self.bind.dialect.name)
            raise exc.DBError(e)
        except Exception as e:
            # LOG.exception(_LE('DB exception wrapped.'))
            raise exc.DBError(e)
    return _wrap


def _synchronous_switch_listener(dbapi_conn, connection_rec):
    """Switch sqlite connections to non-synchronous mode."""
    dbapi_conn.execute("PRAGMA synchronous = OFF")


def _add_regexp_listener(dbapi_con, con_record):
    """Add REGEXP function to sqlite connections."""

    def regexp(expr, item):
        reg = re.compile(expr)
        return reg.search(six.text_type(item)) is not None
    dbapi_con.create_function('regexp', 2, regexp)


def _thread_yield(dbapi_con, con_record):
    """Ensure other greenthreads get a chance to be executed.

    If we use eventlet.monkey_patch(), eventlet.greenthread.sleep(0) will
    execute instead of time.sleep(0).
    Force a context switch. With common database backends (eg MySQLdb and
    sqlite), there is no implicit yield caused by network I/O since they are
    implemented by C libraries that eventlet cannot monkey patch.
    """
    time.sleep(0)


def _ping_listener(engine, dbapi_conn, connection_rec, connection_proxy):
    """Ensures that MySQL connections are alive.
    """
    cursor = dbapi_conn.cursor()
    try:
        ping_sql = 'select 1'
        cursor.execute(ping_sql)
    except Exception as ex:
        if engine.dialect.is_disconnect(ex, dbapi_conn, cursor):
            msg = 'Database server has gone away: %s' % ex
            # LOG.warning(msg)
            print msg

            # if the database server has gone away, all connections in the pool
            # have become invalid and we can safely close all of them here,
            # rather than waste time on checking of every single connection
            engine.dispose()

            # this will be handled by SQLAlchemy and will force it to create
            # a new connection and retry the original action
            raise sqla_exc.DisconnectionError(msg)
        else:
            raise


def _set_session_sql_mode(dbapi_con, connection_rec, sql_mode=None):
    """Set the sql_mode session variable.

    MySQL supports several server modes. The default is None, but sessions
    may choose to enable server modes like TRADITIONAL, ANSI,
    several STRICT_* modes and others.

    Note: passing in '' (empty string) for sql_mode clears
    the SQL mode for the session, overriding a potentially set
    server default.
    """

    cursor = dbapi_con.cursor()
    cursor.execute("SET SESSION sql_mode = %s", [sql_mode])


def _mysql_get_effective_sql_mode(engine):
    """Returns the effective SQL mode for connections from the engine pool.

    Returns ``None`` if the mode isn't available, otherwise returns the mode.

    """
    # Get the real effective SQL mode. Even when unset by
    # our own config, the server may still be operating in a specific
    # SQL mode as set by the server configuration.
    # Also note that the checkout listener will be called on execute to
    # set the mode if it's registered.
    row = engine.execute("SHOW VARIABLES LIKE 'sql_mode'").fetchone()
    if row is None:
        return
    return row[1]


def _mysql_check_effective_sql_mode(engine):
    """Logs a message based on the effective SQL mode for MySQL connections."""
    realmode = _mysql_get_effective_sql_mode(engine)

    if realmode is None:
        # LOG.warning(_LW('Unable to detect effective SQL mode'))
        print 'Unable to detect effective SQL mode'
        return

    # LOG.debug('MySQL server mode set to %s', realmode)
    print 'MySQL server mode set to %s' % realmode

    # 'TRADITIONAL' mode enables several other modes, so
    # we need a substring match here
    if not ('TRADITIONAL' in realmode.upper() or
            'STRICT_ALL_TABLES' in realmode.upper()):
        print "MySQL SQL mode is %s" % realmode
        # LOG.warning("MySQL SQL mode is %s" % realmode)


def _mysql_set_mode_callback(engine, sql_mode):
    if sql_mode is not None:
        mode_callback = functools.partial(_set_session_sql_mode,
                                          sql_mode=sql_mode)
        sqlalchemy.event.listen(engine, 'connect', mode_callback)
    _mysql_check_effective_sql_mode(engine)


def _is_db_connection_error(args):
    """Return True if error in connecting to db."""
    # NOTE(adam_g): This is currently MySQL specific and needs to be extended
    #               to support Postgres and others.
    # For the db2, the error code is -30081 since the db2 is still not ready
    conn_err_codes = ('2002', '2003', '2006', '2013', '-30081')
    for err_code in conn_err_codes:
        if args.find(err_code) != -1:
            return True
    return False


def _raise_if_db_connection_lost(error, engine):
    # NOTE(vsergeyev): Function is_disconnect(e, connection, cursor)
    #                  requires connection and cursor in incoming parameters,
    #                  but we have no possibility to create connection if DB
    #                  is not available, so in such case reconnect fails.
    #                  But is_disconnect() ignores these parameters, so it
    #                  makes sense to pass to function None as placeholder
    #                  instead of connection and cursor.
    if engine.dialect.is_disconnect(error, None, None):
        raise exc.DBConnectionError(error)


def create_engine(sql_connection, sqlite_fk=False, mysql_sql_mode=None,
                  idle_timeout=3600,
                  connection_debug=0, max_pool_size=None, max_overflow=None,
                  pool_timeout=None, sqlite_synchronous=True,
                  connection_trace=False, max_retries=10, retry_interval=10):
    """Return a new SQLAlchemy engine."""

    engine_args = {
        "pool_recycle": idle_timeout,
        'encoding': 'utf8',
        'convert_unicode': True,
    }

    logger = logging.getLogger('sqlalchemy.engine')

    # Map SQL debug level to Python log level
    if connection_debug >= 100:
        logger.setLevel(logging.DEBUG)
    elif connection_debug >= 50:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    if max_pool_size is not None:
        engine_args['pool_size'] = max_pool_size
    if max_overflow is not None:
        engine_args['max_overflow'] = max_overflow
    if pool_timeout is not None:
        engine_args['pool_timeout'] = pool_timeout

    engine = sqlalchemy.create_engine(sql_connection, **engine_args)

    sqlalchemy.event.listen(engine, 'checkin', _thread_yield)

    if engine.name in ('mysql'):
        ping_callback = functools.partial(_ping_listener, engine)
        sqlalchemy.event.listen(engine, 'checkout', ping_callback)
        # if engine.name == 'mysql':
        if mysql_sql_mode:
            _mysql_set_mode_callback(engine, mysql_sql_mode)

    try:
        engine.connect()
    except sqla_exc.OperationalError as e:
        if not _is_db_connection_error(e.args[0]):
            raise

        remaining = max_retries
        if remaining == -1:
            remaining = 'infinite'
        while True:
            msg = "SQL connection failed. %s attempts left."
            print msg % remaining
            # LOG.warning(msg % remaining)
            if remaining != 'infinite':
                remaining -= 1
            time.sleep(retry_interval)
            try:
                engine.connect()
                break
            except sqla_exc.OperationalError as e:
                if (remaining != 'infinite' and remaining == 0) or \
                        not _is_db_connection_error(e.args[0]):
                    raise
    return engine


class Query(sqlalchemy.orm.query.Query):
    """Subclass of sqlalchemy.query with soft_delete() method."""
    def soft_delete(self, synchronize_session='evaluate'):
        return self.update({'deleted': literal_column('id'),
                            'updated_at': literal_column('updated_at'),
                            'deleted_at': utcnow()},
                           synchronize_session=synchronize_session)


class Session(sqlalchemy.orm.session.Session):
    """Custom Session class to avoid SqlAlchemy Session monkey patching."""
    @_wrap_db_error
    def query(self, *args, **kwargs):
        return super(Session, self).query(*args, **kwargs)

    @_wrap_db_error
    def flush(self, *args, **kwargs):
        return super(Session, self).flush(*args, **kwargs)

    @_wrap_db_error
    def execute(self, *args, **kwargs):
        return super(Session, self).execute(*args, **kwargs)


def get_maker(engine, autocommit=False, expire_on_commit=False):
    """Return a SQLAlchemy sessionmaker using the given engine."""
    # return sqlalchemy.orm.sessionmaker(bind=engine, autocommit=True)
    return sqlalchemy.orm.sessionmaker(bind=engine,
                                       class_=Session,
                                       # autocommit=autocommit,
                                       expire_on_commit=expire_on_commit,
                                       query_cls=Query)


class EngineFacade(object):
    """A helper class for removing of global engine instances from ceilometer.db.

    As a library, ceilometer.db can't decide where to store/when to create engine
    and sessionmaker instances, so this must be left for a target application.

    On the other hand, in order to simplify the adoption of ceilometer.db changes,
    we'll provide a helper class, which creates engine and sessionmaker
    on its instantiation and provides get_engine()/get_session() methods
    that are compatible with corresponding utility functions that currently
    exist in target projects, e.g. in Nova.

    engine/sessionmaker instances will still be global (and they are meant to
    be global), but they will be stored in the app context, rather that in the
    ceilometer.db context.

    Note: using of this helper is completely optional and you are encouraged to
    integrate engine/sessionmaker instances into your apps any way you like
    (e.g. one might want to bind a session to a request context). Two important
    things to remember:

    1. An Engine instance is effectively a pool of DB connections, so it's
       meant to be shared (and it's thread-safe).
    2. A Session instance is not meant to be shared and represents a DB
       transactional context (i.e. it's not thread-safe). sessionmaker is
       a factory of sessions.

    """

    def __init__(self, sql_connection,
                 sqlite_fk=False, autocommit=False,
                 expire_on_commit=False, **kwargs):
        """Initialize engine and sessionmaker instances.

        :param sqlite_fk: enable foreign keys in SQLite
        :type sqlite_fk: bool

        :param autocommit: use autocommit mode for created Session instances
        :type autocommit: bool

        :param expire_on_commit: expire session objects on commit
        :type expire_on_commit: bool

        Keyword arguments:

        :keyword mysql_sql_mode: the SQL mode to be used for MySQL sessions.
                                 (defaults to TRADITIONAL)
        :keyword idle_timeout: timeout before idle sql connections are reaped
                               (defaults to 3600)
        :keyword connection_debug: verbosity of SQL debugging information.
                                   0=None, 100=Everything (defaults to 0)
        :keyword max_pool_size: maximum number of SQL connections to keep open
                                in a pool (defaults to SQLAlchemy settings)
        :keyword max_overflow: if set, use this value for max_overflow with
                               sqlalchemy (defaults to SQLAlchemy settings)
        :keyword pool_timeout: if set, use this value for pool_timeout with
                               sqlalchemy (defaults to SQLAlchemy settings)
        :keyword sqlite_synchronous: if True, SQLite uses synchronous mode
                                     (defaults to True)
        :keyword connection_trace: add python stack traces to SQL as comment
                                   strings (defaults to False)
        :keyword max_retries: maximum db connection retries during startup.
                              (setting -1 implies an infinite retry count)
                              (defaults to 10)
        :keyword retry_interval: interval between retries of opening a sql
                                 connection (defaults to 10)

        """

        super(EngineFacade, self).__init__()

        self._engine = create_engine(
            sql_connection=sql_connection,
            sqlite_fk=sqlite_fk,
            mysql_sql_mode=kwargs.get('mysql_sql_mode', 'TRADITIONAL'),
            idle_timeout=kwargs.get('idle_timeout', 3600),
            connection_debug=kwargs.get('connection_debug', 0),
            max_pool_size=kwargs.get('max_pool_size'),
            max_overflow=kwargs.get('max_overflow'),
            pool_timeout=kwargs.get('pool_timeout'),
            sqlite_synchronous=kwargs.get('sqlite_synchronous', True),
            connection_trace=kwargs.get('connection_trace', False),
            max_retries=kwargs.get('max_retries', 10),
            retry_interval=kwargs.get('retry_interval', 10))
        self._session_maker = get_maker(
            engine=self._engine,
            autocommit=autocommit,
            expire_on_commit=expire_on_commit)

    def get_engine(self):
        """Get the engine instance (note, that it's shared)."""

        return self._engine

    def get_session(self, **kwargs):
        """Get a Session instance.

        If passed, keyword arguments values override the ones used when the
        sessionmaker instance was created.

        :keyword autocommit: use autocommit mode for created Session instances
        :type autocommit: bool

        :keyword expire_on_commit: expire session objects on commit
        :type expire_on_commit: bool

        """

        for arg in kwargs:
            if arg not in ('autocommit', 'expire_on_commit'):
                del kwargs[arg]

        return self._session_maker()

    @classmethod
    def from_config(cls, connection_string=None,
                    sqlite_fk=False, autocommit=True, expire_on_commit=False):

        """
        :param connection_string: SQLAlchemy connection string
        :type connection_string: string

        :param conf: oslo.config config instance
        :type conf: oslo.config.cfg.ConfigOpts

        :param sqlite_fk: enable foreign keys in SQLite
        :type sqlite_fk: bool

        :param autocommit: use autocommit mode for created Session instances
        :type autocommit: bool

        :param expire_on_commit: expire session objects on commit
        :type expire_on_commit: bool

        """
        config_options = {
            'mysql_sql_mode': 'TRADITIONAL',
            'idle_timeout': 3600,
            'connection_debug': 0,
            'max_pool_size': 32,
            'max_overflow': 100,
            'pool_timeout': None,
            'sqlite_synchronous': True,
            'connection_trace': False,
            'max_retries': 10,
            'retry_interval': 10
        }

        return cls(sql_connection=connection_string,
                   sqlite_fk=sqlite_fk,
                   autocommit=autocommit,
                   expire_on_commit=expire_on_commit,
                   **config_options)


class Connection(EngineFacade):
    def __init__(self, engine_url):
        self.engine = EngineFacade.from_config(engine_url)

    def list_zone(self):
        """
        return list object, include zone and site as follow:
            models = list_zone()
            for m in models:
                print m.zone.zone_id
                print m.zone.zone_name
                print m.site.site_id
                print m.site.site_name
        """
        try:
            session = self.engine.get_session()
            return session.query(models.Site).options(joinedload_all(models.Site.zone)).all()
        except:
            return []

    def get_site(self, name):
        """
        return site object
        """
        try:
            site = None
            session = self.engine.get_session()
            site = session.query(models.Site).\
                options(joinedload_all('*')).\
                filter(models.Site.site_name == name).one()
            return site
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_pod(self, **kwargs):
        _support = ('site_id',)
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Pod).options(joinedload_all(models.Pod.site)).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs('kwargs error in list_pod')
            return session.query(models.Pod).options(joinedload_all(models.Pod.site)).\
                filter(models.Pod.site_id == kwargs['site_id']).all()
        except:
            raise
        finally:
            session.close()

    def list_cluster(self, **kwargs):
        _support = ('pod_id',)
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Cluster).options(joinedload_all('*')).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs('kwargs error in list_cluster')
            return session.query(models.Cluster).\
                options(joinedload_all('*')).\
                filter(models.Cluster.pod_id == kwargs['pod_id']).\
                all()
        except:
            raise
        finally:
            session.close()

    def get_cluster(self, **kwargs):
        try:
            _support = ('cluster_id', 'cluster_name')
            cluster = None
            session = self.engine.get_session()
            if _support[0] in kwargs:
                cluster = session.query(models.Cluster).\
                    options(joinedload_all('*')).\
                    filter(models.Cluster.cluster_id == kwargs['cluster_id']).\
                    one()
            if _support[1] in kwargs:
                cluster = session.query(models.Cluster).\
                    options(joinedload_all('*')).\
                    filter(models.Cluster.cluster_name == kwargs['cluster_name']).\
                    one()
            return cluster
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_datastore(self, **kwargs):
        _support = ('cluster_id',)
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.DataStore).options(joinedload_all('*')).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs('kwargs error in list_datastore')
            return session.query(models.DataStore).\
                options(joinedload_all('*')).\
                filter(models.DataStore.cluster_id == kwargs['cluster_id']).\
                all()
        except:
            raise
        finally:
            session.close()

    def list_app(self, **kwargs):
        _support = ('customer_id',)
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.App).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs("kwargs error in list_app")
            return session.query(models.App).\
                filter(models.App.customer_id == kwargs['customer_id']).\
                all()
        except:
            raise
        finally:
            pass

    def get_app(self, app_id):
        try:
            app = None
            session = self.engine.get_session()
            app = session.query(models.App).\
                options(joinedload_all('*')).\
                filter(models.App.app_id == app_id).one()
            return app
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_clusters_from_app(self, app_id):
        try:
            session = self.engine.get_session()
            app = session.query(models.App).\
                filter(models.App.app_id == app_id).one()
            clusters = session.query(models.Cluster).\
                options(joinedload_all(models.Cluster.pod)).\
                filter(models.Cluster.pod_id == app.pod_id).all()
            return clusters
        except NoResultFound:
            raise exc.NoResultFound('not found app')
        finally:
            session.close()

    def get_site_from_app(self, app_id):
        try:
            session = self.engine.get_session()
            app = session.query(models.App).\
                filter(models.App.app_id == app_id).one()
            pod = session.query(models.Pod).\
                filter(models.Pod.pod_id == app.pod_id).one()
            return pod.site
        except NoResultFound:
            return None
        finally:
            pass

    def add_app(self, **kwargs):
        if not kwargs:
            raise exc.ErrorKwargs('kwargs parameters is null')
        try:
            app = models.App(kwargs['app_id'],
                             kwargs['customer_id'],
                             kwargs['zone_id'],
                             kwargs['site_id'],
                             kwargs['pod_id'],
                             kwargs['app_type'],
                             kwargs['status'])
            session = self.engine.get_session()
            session.add(app)
            session.commit()
        except Exception, e:
            raise exc.DBError('add_app error message: %s' % str(e))

    def delete_app(self, app_id):
        try:
            session = self.engine.get_session()
            kwargs = {'status': 'delete'}
            q = session.query(models.App).filter(models.App.app_id == app_id)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found app')
        except Exception, e:
            raise exc.DBError('delete_app error message: %s' % str(e))

    def list_nicing_from_site(self, site_name):
        nics = []
        try:
            session = self.engine.get_session()
            vm_network_infos = session.query(models.Vm_Network_Info).\
                options(joinedload_all('*')).\
                filter(or_(models.Vm_Network_Info.status == 'adding',
                           models.Vm_Network_Info.status == 'deleting')).all()
            for vm_network_info in vm_network_infos:
                if vm_network_info.vm.site_name == site_name:
                    nics.append(vm_network_info)
            return nics
        except:
            raise
        finally:
            session.close()

    def list_nic(self, **kwargs):
        nics = []
        _support = ('app_id', )
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Vm_Network_Info).\
                    options(joinedload_all(models.Vm_Network_Info.vm)).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs("kwargs error in list nic")
            vms = session.query(models.Vm).\
                filter(models.Vm.app_id == kwargs['app_id']).\
                all()
            for vm in vms:
                for nic in vm.vm_network_info:
                    nics.append(nic)
            return nics
        except:
            raise
        finally:
            session.close()

    def get_nic(self, nic_id):
        try:
            nic = None
            session = self.engine.get_session()
            nic = session.query(models.Vm_Network_Info).\
                options(joinedload_all(models.Vm_Network_Info.vm)).\
                filter(models.Vm_Network_Info.nic_id == nic_id).\
                one()
            return nic
        except NoResultFound:
            return None
        finally:
            session.close()

    def add_nic(self, **kwargs):
        try:
            message = 'not found vm'
            session = self.engine.get_session()
            vm = session.query(models.Vm).\
                filter(models.Vm.vm_id == kwargs['vm_id']).one()
            message = 'not found subinterface'
            subinterface = session.query(models.Subinterface).\
                filter(models.Subinterface.subinterface_id == kwargs['subinterface_id']).\
                one()
            if not subinterface.app_id or vm.app_id != subinterface.app_id:
                raise exc.UnknownVlanId('unknown vlan id')
            for network in vm.vm_network_info:
                if subinterface.subinterface_id == network.subinterface_id:
                    raise exc.VlanIdAlreadyExist('have already vlan in vm')
            nic = models.Vm_Network_Info(kwargs['nic_id'],
                                         kwargs['subinterface_id'],
                                         kwargs['status'],
                                         kwargs['network_connect'],
                                         kwargs['vm_id'])
            session.add(nic)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound(message)

    def update_nic(self, nic_id, **kwargs):
        # _support = ('status', 'network_connect')
        try:
            # if _support[0] not in kwargs:
            #    raise exc.ErrorKwargs('kwargs error in update nic')
            session = self.engine.get_session()
            nic = session.query(models.Vm_Network_Info).\
                filter(models.Vm_Network_Info.nic_id == nic_id).\
                one()
            if kwargs.get('status', None):
                nic.status = kwargs['status']
            if kwargs.get('mac', None):
                nic.mac = kwargs['mac']
            if kwargs.get("network_connect", None):
                nic.network_connect = kwargs['network_connect']
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found nic')

    def delete_nic(self, nic_id):
        try:
            session = self.engine.get_session()
            q = session.query(models.Vm_Network_Info).\
                filter(models.Vm_Network_Info.nic_id == nic_id)
            q.one()
            q.delete()
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found nic')

    def get_subinterface(self, subinterface_id):
        try:
            subinterface = None
            session = self.engine.get_session()
            subinterface = session.query(models.Subinterface).\
                options(joinedload_all('*')).\
                filter(models.Subinterface.subinterface_id == subinterface_id).one()
            if not subinterface.app_id or not subinterface.vlan_type:
                return None
            return subinterface
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_subinterface_from_route(self, route_id, **kwargs):
        _support = ('status',)
        try:
            session = self.engine.get_session()
            if not kwargs:
                return exc.NotFoundKey('not found kwargs')
            if _support[0] not in kwargs:
                raise exc.NotFoundKey("not support %s in subinterface" % _support[0])
            subinterfaces = session.query(models.Subinterface).\
                options(joinedload_all('*')).\
                filter(models.Subinterface.status == kwargs['status']).all()
            return [subinterface for subinterface in subinterfaces
                    if subinterface.interface.route_id == route_id]
        except:
            raise
        finally:
            session.close()

    def list_subinterface(self, **kwargs):
        _support = ('app_id',)
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Subinterface).\
                    options(subqueryload_all('*')).\
                    filter(models.Subinterface.app_id.isnot(None)).all()
            if _support[0] not in kwargs:
                raise exc.NotFoundKey("not support %s in subinterface" % _support[0])
            return session.query(models.Subinterface).\
                options(joinedload_all('*')).\
                filter(models.Subinterface.app_id == kwargs['app_id']).all()
        except:
            raise
        finally:
            session.close()

    def alloc_vlan(self, **kwargs):
        """
            kw = {'app_id': xx,
                  'qos': 10,
                  'vlan_type': 'public',
                  'status': 'processing',
                  'sub_net': {
                                'network_num': '172.2.3.0/24',
                                'network_address': '172.2.3.1/24',
                                'level': 'primary',
                                'step': 'processing'
                             }
                }
        """

        def _get_free_subinterface(interface):
            while True:
                subinterface = random.choice(interface.subinterface)
                if not subinterface.app_id:
                    return subinterface

        try:
            sub_net = {}
            if 'sub_net' in kwargs:
                sub_net = kwargs.pop('sub_net')
            session = self.engine.get_session()
            app = session.query(models.App).filter(models.App.app_id == kwargs['app_id']).one()
            interface = session.query(models.Interface).\
                filter(models.Interface.pod_id == app.pod_id).first()
            subinterface = _get_free_subinterface(interface)
            if not subinterface:
                raise exc.NotAllocVlan('not alloc vlan')
            subinterface.app_id = kwargs['app_id']
            subinterface.vlan_type = kwargs['vlan_type']
            subinterface.qos = kwargs['qos']
            subinterface.status = kwargs['status']
            subinterface.alloc_time = utcnow()
            if sub_net:
                ipv4 = models.Network_Ipv4(sub_net['network_num'],
                                           sub_net['network_address'],
                                           sub_net['level'],
                                           sub_net['step'])
                ipv4.subinterface = subinterface
            session.commit()
            return subinterface.subinterface_id
        except NoResultFound:
            raise exc.NoResultFound('not found app')

    def free_vlan(self, subinterface_id):
        try:
            kwargs = {'vlan_type': None,
                      'alloc_time': None,
                      'qos': None,
                      'app_id': None,
                      'gic_id': None,
                      'status': None}
            session = self.engine.get_session()
            session.query(models.Network_Ipv4).\
                filter(models.Network_Ipv4.subinterface_id == subinterface_id).delete()
            session.query(models.Network_Ipv6).\
                filter(models.Network_Ipv6.subinterface_id == subinterface_id).delete()
            q = session.query(models.Subinterface).\
                filter(models.Subinterface.subinterface_id == subinterface_id)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found subinterface')

    def update_vlan(self, subinterface_id, **kwargs):
        """
        add:
            kw = {'qos': 15,
                  'status': 'ok'
                  'sub_net': {'network_num': '172.3.2.1/24',
                              'network_address': '172.3.2.1',
                              'op_type': 'add',
                              'level': 'secondary'}
        delete:
            kw = {'qos': 20,
                  'sub_net': {'network_num': '172.3.2.1/24',
                              'op_type': 'delete'}

         subinterface status is ornot 'ok' that it is not do control
        """
        try:
            sub_net = kwargs.get('sub_net', None)
            session = self.engine.get_session()
            subinterface = session.query(models.Subinterface).\
                filter(models.Subinterface.subinterface_id == subinterface_id).one()
            if subinterface.status != 'ok':
                raise exc.NotAllowUpdate('pipe status is not ok')
            if kwargs.get('qos', None):
                subinterface.qos = kwargs['qos']
            if kwargs.get('status', None):
                subinterface.status = kwargs['status']
            if not sub_net:
                session.commit()
                return True
            op_type = sub_net.pop('op_type')
            if op_type == 'add':
                ipv4 = models.Network_Ipv4(sub_net['network_num'],
                                           sub_net['network_address'],
                                           sub_net['level'],
                                           'adding')
                ipv4.subinterface = subinterface
            if op_type == 'delete':
                kw = {'step': 'deleting'}
                session.query(models.Network_Ipv4).\
                    filter(models.Network_Ipv4.network_num == sub_net['network_num']).\
                    update(kw)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found subinterface')

    def update_network_ipv4(self, id, **kwargs):
        try:
            session = self.engine.get_session()
            session.query(models.Network_Ipv4).\
                filter(models.Network_Ipv4.id == id).update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found subinterface network_ipv4')

    def delete_network_ipv4(self, id):
        try:
            session = self.engine.get_session()
            session.query(models.Network_Ipv4).\
                filter(models.Network_Ipv4.id == id).delete()
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found subinterface network_ipv4')

    def deleting_vlan(self, subinterface_id):
        try:
            session = self.engine.get_session()
            subinterface = session.query(models.Subinterface).\
                filter(models.Subinterface.subinterface_id == subinterface_id).one()
            if not subinterface.app_id or not subinterface.vlan_type:
                raise exc.NoResultFound('not found subinterface')
            if subinterface.status != 'ok':
                raise exc.NotAllowDelete('pipe status is not ok')
            subinterface.status = 'deleting'
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found subinterface')

    def delete_vlan_ipv4(self, ipv4_id):
        try:
            session = self.engine.get_session()
            q = session.query(models.Network_Ipv4).filter(models.Network_Ipv4.id == ipv4_id)
            q.one()
            q.delete()
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found ipv4')

    def update_vlan_netlevel(self, subinterface_id):
        """
            update subinterface network ipv4 level, if not found that level eq 'primary', then
            first network ipv4 level is reseted primary, if have 'primary', then do nothing
        """
        try:
            session = self.engine.get_session()
            ipv4s = session.query(models.Network_Ipv4).\
                filter(models.Network_Ipv4.subinterface_id == subinterface_id).all()
            if not ipv4s:
                return
            for ipv4 in ipv4s:
                if ipv4.level == 'primary':
                    return
            ipv4s[0].level = 'primary'
            session.commit()
        except Exception, e:
            raise exc.DBError(str(e))

    def alloc_gic(self, **kwargs):
        try:
            session = self.engine.get_session()
            gic = session.query(models.Gic).filter(models.Gic.customer_id.is_(None)).first()
            gic.alloc_time = utcnow()
            gic.qos = kwargs['qos']
            gic.customer_id = kwargs['customer_id']
            session.commit()
            return gic.gic_id
        except Exception, e:
            raise exc.DBError(str(e))

    def get_gic(self, gic_id):
        try:
            gic = None
            session = self.engine.get_session()
            gic = session.query(models.Gic).\
                options(joinedload_all('*')).\
                filter(models.Gic.gic_id == gic_id).one()
            return gic
        except NoResultFound:
            return None
        finally:
            session.close()

    def free_gic(self, gic_id):
        try:
            kwargs = {'alloc_time': None, 'qos': None, 'customer_id': None}
            session = self.engine.get_session()
            q = session.query(models.Gic).\
                filter(models.Gic.gic_id == gic_id)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found gic')

    def update_gic(self, gic_id, **kwargs):
        try:
            session = self.engine.get_session()
            q = session.query(models.Gic).\
                filter(models.Gic.gic_id == gic_id)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found gic')

    def join_app_gic(self, **kwargs):
        message = 'not found app'
        try:
            session = self.engine.get_session()
            session.query(models.App).\
                filter(models.App.app_id == kwargs['app_id']).one()

            message = 'not found gic'
            gic = session.query(models.Gic).\
                filter(models.Gic.gic_id == kwargs['gic_id']).one()
            if not gic.customer_id:
                raise exc.InvalidGic('invalid gic')

            message = 'not found subinterface'
            q = session.query(models.Subinterface).\
                filter(models.Subinterface.subinterface_id == kwargs['subinterface_id'])
            subinterface = q.one()
            if subinterface.vlan_type != 'gic':
                raise exc.VlanTypeError('subinterface vlan type is not gic')
            subinterface.gic_id = kwargs['gic_id']
            gic_ex = models.GicExtension(kwargs['gicextension_id'],
                                         kwargs['app_id'],
                                         kwargs['gic_id'],
                                         kwargs['subinterface_id'],
                                         kwargs['status'])
            session.add(gic_ex)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound(message)

    def get_gicextension(self, gicextension_id):
        try:
            gicextension = None
            session = self.engine.get_session()
            gicextension = session.query(models.GicExtension).\
                options(joinedload_all('*')).\
                filter(models.GicExtension.gicextension_id == gicextension_id).one()
            return gicextension
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_gicextension_from_route(self, route_id, **kwargs):
        """
            input args:
                route_id: route id
                kwargs = {"status": "deleting|adding"}
            output [
                {
                    _id: gicextension_id,
                    sub_name: subinterface_name01,
                    edge_name: edge_name01,
                    group_name: group_name01,
                },
                {
                    _id: gicextension_id,
                    sub_name: subinterface_name01,
                    edge_name: edge_name01,
                    group_name: group_name01,
                },
            ]
        """
        try:
            local_gicextensions = []
            session = self.engine.get_session()
            gicextensions = session.query(models.GicExtension).\
                options(joinedload_all('*')).\
                filter(models.GicExtension.status == kwargs['status']).all()
            for gicextension in gicextensions:
                map_table = {}
                subinterface = self.get_subinterface(gicextension.subinterface_id)
                if subinterface and subinterface.interface.route_id == route_id:
                    map_table = {'_id': gicextension.gicextension_id,
                                 'sub_name': subinterface.subinterface_name}
                gic = self.get_gic(gicextension.gic_id)
                if gic:
                    map_table['edge_name'] = gic.edge_name
                    map_table['group_name'] = gic.group_name
                    local_gicextensions.append(map_table)
            return local_gicextensions
        except:
            raise
        finally:
            session.close()

    def list_updating_gic_from_route(self, route_id):
        """
            input args: route_id
            output:
                [
                    {'gic_id': gic_id,
                     'subinterfaces': [subinterface1, subinterface2]},
                    {'gic_id': gic_id,
                     'subinterfaces': [subinterface1, subinterface2]},
                ]
        """
        output = []
        try:
            session = self.engine.get_session()
            gics = session.query(models.Gic).\
                options(joinedload_all('*')).\
                filter(models.Gic.status == 'updating').all()
            for gic in gics:
                local_gic = {}
                subinterfaces = session.query(models.Subinterface).\
                    options(joinedload_all('*')).\
                    filter(models.Subinterface.gic_id == gic.gic_id).all()
                local_subinterfaces = []
                if not subinterfaces:
                    continue
                for subinterface in subinterfaces:
                    if subinterface.interface.route_id != route_id:
                        continue
                    if subinterface.status != "ok":
                        LOG.warning('gic qos was updated when it is subinterface status is not ok')
                        continue
                    local_subinterfaces.append(subinterface)
                local_gic = {'gic_id': gic.gic_id,
                             'subinterfaces': local_subinterfaces}
                output.append(local_gic)
            return output
        except:
            raise
        finally:
            session.close()

    def list_gic_app(self, **kwargs):
        _support = ('gic_id', 'status')
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.GicExtension).\
                    options(joinedload_all('*')).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs('not found gic_id in kwargs of list_gic_app')
            if _support[0] in kwargs:
                return session.query(models.GicExtension).\
                    options(joinedload_all('*')).\
                    filter(models.GicExtension.gic_id == kwargs['gic_id']).all()
            if _support[1] in kwargs:
                return session.query(models.GicExtension).\
                    options(joinedload_all('*')).\
                    filter(models.GicExtension.status == kwargs['status']).all()
        except:
            raise
        finally:
            session.close()

    def update_gicextension(self, gicextension_id, **kwargs):
        try:
            session = self.engine.get_session()
            q = session.query(models.GicExtension).\
                filter(models.GicExtension.gicextension_id == gicextension_id)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found gicid in gicextension')

    def deleting_gicextension(self, gicextension_id):
        try:
            message = 'not found gicid in gicextension'
            session = self.engine.get_session()
            gicextension = session.query(models.GicExtension).\
                filter(models.GicExtension.gicextension_id == gicextension_id).one()
            if gicextension.status != 'ok':
                raise exc.NotAllowDelete('not allow delete app from gic')
            message = 'not found type of gic subinterface in gic'
            gicextension.status = 'deleting'
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound(message)

    def delete_gicextension(self, gicextension_id):
        try:
            session = self.engine.get_session()
            q = session.query(models.GicExtension).\
                filter(models.GicExtension.gicextension_id == gicextension_id)
            q.one()
            q.delete()
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found gicextension_id')

    def get_action(self, action_id):
        try:
            action = None
            session = self.engine.get_session()
            action = session.query(models.Action).\
                options(joinedload_all('*')).\
                filter(models.Action.action_id == action_id).one()
            return action
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_vm_from_action(self, site_name, **kwargs):
        """
            output: return type is dict that it's key is 'action' object,
                    it's value is 'vm' object,
            for example:
                    return {action: vm}
        """
        vms = {}
        try:
            session = self.engine.get_session()
            actions = session.query(models.Action).\
                options(joinedload_all('*')).\
                filter(models.Action.action == kwargs['action']).\
                filter(models.Action.status == kwargs["status"]).all()
            for action in actions:
                vm = session.query(models.Vm).\
                    options(joinedload_all('*')).\
                    filter(models.Vm.vm_id == action.vm_id).one()
                if vm.site_name == site_name:
                    vms[action] = vm
            return vms
        except:
            raise
        finally:
            session.close()

    def list_action(self, **kwargs):
        _support = ('action', 'status', 'app_id', 'vm_id')
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Action).\
                    options(joinedload_all('*')).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs('kwargs error in list_action')
            if _support[0] in kwargs:
                return session.query(models.Action).\
                    options(joinedload_all('*')).\
                    filter(models.Action.action == kwargs['action']).all()
            if _support[1] in kwargs:
                return session.query(models.Action).\
                    options(joinedload_all('*')).\
                    filter(models.Action.status == kwargs['status']).all()
            if _support[2] in kwargs:
                return session.query(models.Action).\
                    options(joinedload_all('*')).\
                    filter(models.Action.app_id == kwargs['app_id']).all()
            if _support[3] in kwargs:
                return session.query(models.Action).\
                    options(joinedload_all('*')).\
                    filter(models.Action.vm_id == kwargs['vm_id']).\
                    filter(models.Action.status == 'processing').all()
        except:
            raise
        finally:
            session.close()

    def add_action(self, **kwargs):
        try:
            action = models.Action(kwargs['action_id'],
                                   kwargs['app_id'],
                                   kwargs['vm_id'],
                                   kwargs['nic_id'],
                                   kwargs['action'],
                                   kwargs['status'])
            session = self.engine.get_session()
            session.add(action)
            session.commit()
        except Exception, e:
            raise exc.DBError(str(e))

    def update_action(self, action_id, **kwargs):
        try:
            session = self.engine.get_session()
            q = session.query(models.Action).filter(models.Action.action_id == action_id)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found action')

    def get_template(self, template_id):
        try:
            template = None
            session = self.engine.get_session()
            template = session.query(models.Templates).\
                options(joinedload_all('*')).\
                filter(models.Templates.template_id == template_id).one()
            return template
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_template(self, **kwargs):
        _support = ('customer_id',)
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Templates).\
                    options(joinedload_all('*')).all()
            if kwargs.keys[0] not in _support:
                raise exc.ErrorKwargs('not found customer_id in Templates')
            if _support[0] in kwargs:
                return session.query(models.Templates).\
                    options(joinedload_all('*')).\
                    filter(models.Templates.customer_id == kwargs['customer_id']).all()
        except:
            raise
        finally:
            session.close()

    def add_template(self, **kwargs):
        try:
            template = models.Templates(kwargs['template_id'],
                                        kwargs['template_name'],
                                        kwargs['template_type'],
                                        kwargs['os_type'],
                                        kwargs['os_version'],
                                        kwargs['os_bit'],
                                        kwargs['cpu'],
                                        kwargs['ram'],
                                        kwargs['disk'],
                                        kwargs['username'],
                                        kwargs['password'],
                                        kwargs['customer_id'],
                                        kwargs['vmware_tool'])
            session = self.engine.get_session()
            session.add(template)
            session.commit()
        except Exception, e:
            raise exc.DBError(str(e))

    def get_vspc(self, vspc_id):
        try:
            vspc = None
            session = self.engine.get_session()
            vspc = session.query(models.Vspc_Info).\
                options(joinedload_all('*')).\
                filter(models.Vspc_Info.vspc_id == vspc_id).one()
            return vspc
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_vspc(self, **kwargs):
        _support = ('site_id', 'cluster_id')

        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Vspc_Info).\
                    options(joinedload_all('*')).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs('not found site_id or cluster_id in list_vspc kwargs')
            if _support[0] in kwargs:
                return session.query(models.Vspc_Info).\
                    options(joinedload_all('*')).\
                    filter(models.Vspc_Info.site_id == kwargs['site_id']).all()
            if _support[1] in kwargs:
                return session.query(models.Vspc_Info).\
                    options(joinedload_all('*')).\
                    filter(models.Vspc_Info.cluster_id == kwargs['cluster_id']).one()
        except NoResultFound:
            return []
        except Exception:
            raise
        finally:
            session.close()

    def add_vspc(self, **kwargs):
        try:
            vspc = models.Vspc_Info(kwargs['site_id'],
                                    kwargs['pod_id'],
                                    kwargs['cluster_id'],
                                    kwargs['vspc_server_ip'],
                                    kwargs['is_enable'])
            session = self.engine.get_session()
            session.add(vspc)
            session.commit()
            return vspc.vspc_id
        except Exception, e:
            raise exc.DBError(str(e))

    def update_vspc(self, vspc_id, **kwargs):
        try:
            session = self.engine.get_session()
            q = session.query(models.Vspc_Info).\
                filter(models.Vspc_Info.vspc_id == vspc_id)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found vspc')

    def list_vm_from_serial(self, **kwargs):
        _support = ('vm_name', 'vspc_id', 'site_id', 'cluster_id')

        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Serial_Connection).\
                    options(joinedload_all('*')).all()
            if kwargs.keys()[0] not in _support:
                raise exc.ErrorKwargs('kwargs isnot support in list of Serial_Connection')
            if _support[0] in kwargs:
                return session.query(models.Serial_Connection).\
                    options(joinedload_all('*')).\
                    filter(models.Serial_Connection.vm_name == kwargs['vm_name']).all()
            if _support[1] in kwargs:
                return session.query(models.Serial_Connection).\
                    options(joinedload_all('*')).\
                    filter(models.Serial_Connection.vspc_id == kwargs['vspc_id']).all()
            if _support[2] in kwargs:
                return session.query(models.Serial_Connection).\
                    options(joinedload_all('*')).\
                    filter(models.Serial_Connection.site_id == kwargs['site_id']).all()
            if _support[3] in kwargs:
                return session.query(models.Serial_Connection).\
                    options(joinedload_all('*')).\
                    filter(models.Serial_Connection.cluster_id == kwargs['cluster_id']).all()
        except:
            raise
        finally:
            session.close()

    def add_vm_serial_info(self, **kwargs):
        try:
            vm_serial = models.Serial_Connection(kwargs['connection_id'],
                                                 kwargs['site_id'],
                                                 kwargs['pod_id'],
                                                 kwargs['cluster_id'],
                                                 kwargs['vm_name'],
                                                 kwargs['vspc_server_ip'],
                                                 kwargs['port'],
                                                 kwargs['is_connected'])
            session = self.engine.get_session()
            session.add(vm_serial)
            session.commit()
        except Exception, e:
            raise exc.DBError(str(e))

    def delete_vm_serial(self, vm_name):
        LOG.debug('db Instance delete name :%s' % vm_name)
        try:
            session = self.engine.get_session()
            q = session.query(models.Serial_Connection).\
                filter(models.Serial_Connection.vm_name == vm_name)
            q.one()
            q.delete()
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found vm')

    def update_vm_serial(self, vm_name, **kwargs):
        try:
            session = self.engine.get_session()
            q = session.query(models.Serial_Connection).\
                filter(models.Serial_Connection.vm_name == vm_name)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found vm')

    def get_vm(self, vm_id):
        try:
            vm = None
            session = self.engine.get_session()
            vm = session.query(models.Vm).\
                options(subqueryload_all('*')).\
                filter(models.Vm.vm_id == vm_id).one()
            return vm
        except NoResultFound:
            return None
        finally:
            session.close()

    def list_vm_from_site(self, site_name, **kwargs):
        """
        only support as follow:
            kwargs = {'status': xx, 'configure_step': xxx}
            kwargs = {'status': xx}
            kwargs = {'configure_step': xxx}
        """
        try:
            session = self.engine.get_session()
            if len(kwargs) == 2:
                return session.query(models.Vm).\
                    options(joinedload_all('*')).\
                    filter(models.Vm.site_name == site_name).\
                    filter(models.Vm.status == kwargs['status']).\
                    filter(models.Vm.configure_step == kwargs['configure_step']).all()
            if kwargs.get('status', None):
                return session.query(models.Vm).\
                    options(joinedload_all('*')).\
                    filter(models.Vm.site_name == site_name).\
                    filter(models.Vm.status == kwargs['status']).all()
            if kwargs.get('configure_step', None):
                return session.query(models.Vm).\
                    options(joinedload_all('*')).\
                    filter(models.Vm.site_name == site_name).\
                    filter(models.Vm.configure_step == kwargs['configure_step']).all()
        except:
            raise
        finally:
            session.close()

    def list_vming_from_site(self, site_name):
        try:
            session = self.engine.get_session()
            return session.query(models.Vm).\
                options(joinedload_all('*')).\
                filter(models.Vm.site_name == site_name).\
                filter(or_(models.Vm.configure_step == 'end',
                           models.Vm.configure_step == 'deleted')).all()
        except:
            return []
        finally:
            session.close()

    def list_vm(self, **kwargs):
        _support = ('site_id',
                    'status',
                    'app_id')
        try:
            session = self.engine.get_session()
            if not kwargs:
                return session.query(models.Vm).\
                    options(subqueryload_all('*')).\
                    all()
            for key in kwargs.keys():
                if key not in _support:
                    LOG.debug('xxxxxxx debbug')
                    raise exc.ErrorKwargs('kwargs is not support in list of Vm')
            if kwargs.get('app_id', None):
                return session.query(models.Vm).\
                    options(subqueryload_all('*')).\
                    filter(models.Vm.app_id == kwargs['app_id']).all()
            LOG.debug('********')
            if kwargs.get('site_id', None) and kwargs.get('status', None):
                site = session.query(models.Site).\
                    filter(models.Site.site_id == kwargs['site_id']).one()
                return session.query(models.Vm).\
                    options(subqueryload_all('*')).\
                    filter(models.Vm.site_name == site.site_name).\
                    filter(models.Vm.status == kwargs['status']).all()
        finally:
            session.close()

    def add_vm(self, **kwargs):
        """
            kwargs = {'vm_id': '',
                      'vm_name': '',
                      ...,
                      'os_info': {'hostname': 'xxx', 'os_type': 'centos', ...},
                      'flavor_info': {'cpu': 8,
                                      'ram': 16,
                                      'disks':[
                                            {'size': 100, 'is_load': 0},
                                            {'size': 500, 'is_load': 0}
                                        ]
                        },
                      'network_info':[
                                        {'subinterface_id': 'xxx',
                                          'status': None,
                                          'mac': xxxx
                                          ...,
                                          'ipv4': {'ip': 'xx', 'mask': 'xxx', ...},
                                          'ipv6': {'ip': 'xxx', ...}
                                         },
                                         {'subinterface_id': 'xxx',
                                          'status': None,
                                          'mac': xxxx
                                          ...,
                                          'ipv4': {'ip': 'xx', 'mask': 'xxx', ...},
                                          'ipv6': {'ip': 'xxx', ...}
                                         }
                                    ]
            }

        """
        def _net_iterator(vmid, net_infos):
            nets = []
            for net in net_infos:
                net_info = models.Vm_Network_Info(str(uuid.uuid4()),
                                                  net['subinterface_id'],
                                                  net['status'],
                                                  net['network_connect'],
                                                  vmid)
                ipv4 = net.pop('ipv4')
                ipv6 = net.pop('ipv6')
                if ipv4:
                    net_info.vm_ipv4 = [models.Vm_Ipv4(ipv4['ip'],
                                                       ipv4['mask'],
                                                       ipv4['gateway'],
                                                       ipv4['dns'])]
                if ipv6:
                    net_info.vm_ipv6 = [models.Vm_Ipv6(ipv6['ip'])]
                nets.append(net_info)
            return nets

        LOG.debug('Db Instance add name :%s' % kwargs['vm_name'])
        os_info = kwargs.pop('os_info')
        flavor_info = kwargs.pop('flavor_info')
        network_info = kwargs.pop('network_info')
        vm = models.Vm(kwargs['vm_id'],
                       kwargs['vm_name'],
                       kwargs['template_id'],
                       kwargs['customer_id'],
                       kwargs['site_name'],
                       kwargs['pod_name'],
                       kwargs['cluster_name'],
                       kwargs['datastore_name'],
                       kwargs['status'],
                       kwargs['configure_step'],
                       kwargs['app_id'])
        vm.vm_os_info = [models.Vm_Os_Info(os_info['hostname'],
                                           os_info['os_type'],
                                           os_info['os_version'],
                                           os_info['os_bit'],
                                           os_info['username'],
                                           os_info['password'])]
        flavor1 = models.Flavor_Info(flavor_info['cpu'],
                                     flavor_info['ram'])
        flavor1.disk = [models.Disk(disk['size'],
                                    disk['is_load'])
                        for disk in flavor_info['disks']]
        vm.flavor_info = [flavor1]
        vm.vm_network_info = _net_iterator(kwargs['vm_id'], network_info)
        session = self.engine.get_session()
        session.add(vm)
        session.commit()
        return [dict(pipe_id=net.subinterface_id, nic_id=net.nic_id)
                for net in vm.vm_network_info]

    def wrap_update_vm(self, vm_id, **kwargs):
        """
            if ram not changed, then ram = None
            if ram changed, then ram eq value of after changed
            if disk not changed, then disk = []
            cpu: kwargs = {
                           'configure_step': 'ip',
                        }
        """
        try:
            session = self.engine.get_session()
            vm = session.query(models.Vm).\
                options(joinedload_all('*')).\
                filter(models.Vm.vm_id == vm_id).one()
            vm.configure_step = kwargs['configure_step']
            for disk in vm.flavor_info[0].disk:
                if disk.is_load == 0:
                    disk.is_load = 1
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found vm')

    def update_vm(self, vm_id, **kwargs):
        """
            if ram not changed, then ram = None
            if ram changed, then ram eq value of after changed
            if disk not changed, then disk = []
            cpu: kwargs = {'cpu': 8,
                           'ram': None,
                           'status': 'updating',
                           'configure_step': 'ip',
                           'disks': [
                                {'size': 1000, 'is_load': 0},
                                {'size': 6000, 'is_load': 0}
                            ],
                           'network_info': {'subinterface_id': 'macaddress'},
                    }
        """
        try:
            if not kwargs:
                raise exc.DBError('kwargs is null in update of vm')

            session = self.engine.get_session()
            vm = session.query(models.Vm).filter(models.Vm.vm_id == vm_id).one()
            if kwargs.get('cpu', None):
                vm.flavor_info[0].cpu = kwargs['cpu']
            if kwargs.get('ram', None):
                vm.flavor_info[0].ram = kwargs['ram']
            if kwargs.get('status', None):
                vm.status = kwargs['status']
            if kwargs.get('configure_step', None):
                vm.configure_step = kwargs['configure_step']
            if kwargs.get('disks', None):
                for disk in kwargs['disks']:
                    d = models.Disk(disk['size'], disk['is_load'])
                    d.flavor_info = vm.flavor_info[0]
            if kwargs.get('network_info', None):
                pipes = kwargs['network_info']
                for network in vm.vm_network_info:
                    mac = pipes.get(network.subinterface_id, None)
                    if mac:
                        network.mac = mac
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found vm')

    def deleting_vm(self, vm_id, **kwargs):
        try:
            LOG.debug('db Instance delete id: %s' % vm_id)
            session = self.engine.get_session()
            q = session.query(models.Vm).filter(models.Vm.vm_id == vm_id)
            q.one()
            q.update(kwargs)
            session.commit()
        except NoResultFound:
            raise exc.NoResultFound('not found vm')

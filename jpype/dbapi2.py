import _jpype
from . import _jinit
from . import _jcustomizer
from . import types as _jtypes
import typing
import _jpype
import time
import threading
import datetime

# TODO
#  - Callable procedures
#  - Isolation levels
#  - Default adaptors
#  - A complete testbench
#  - Testbench with more than one DB
#  - Documentation

# This a generic implementation of PEP-249
__all__ = ['ARRAY', 'ASCII_STREAM', 'BIGINT', 'BINARY', 'BINARY_STREAM', 'BIT',
           'BLOB', 'BOOLEAN', 'BY_COLNAME', 'BY_JDBCTYPE', 'Binary', 'CHAR',
           'CHARACTER_STREAM', 'CLOB', 'Connection', 'Cursor', 'DATE', 'DATETIME',
           'DECIMAL', 'DOUBLE', 'DataError', 'DatabaseError', 'Date',
           'DateFromTicks', 'Error', 'FLOAT', 'INTEGER', 'IntegrityError',
           'InterfaceError', 'InternalError', 'JDBCType', 'LONGNVARCHAR',
           'LONGVARBINARY', 'LONGVARCHAR', 'NCHAR', 'NCHARACTER_STREAM', 'NCLOB',
           'NULL', 'NUMBER', 'NUMERIC', 'NVARCHAR', 'NotSupportedError', 'OBJECT',
           'OTHER', 'OperationalError', 'ProgrammingError', 'REAL', 'REF',
           'RESULTSET', 'ROWID', 'SMALLINT', 'SQLXML', 'STRING', 'TEXT', 'TIME',
           'TIMESTAMP', 'TIMESTAMP_WITH_TIMEZONE', 'TIME_WITH_TIMEZONE',
           'TINYINT', 'Time', 'TimeFromTicks', 'Timestamp', 'TimestampFromTicks',
           'URL', 'VARBINARY', 'VARCHAR', 'Warning', 'connect']

apilevel = "2.0"
threadsafety = 2
paramstyle = 'qmark'

_SQLException = None
_SQLTimeoutException = None
_registry = {}
_types = []


def _nop(x):
    return x

###############################################################################
# Types


class JDBCType:
    def __init__(self, name, code, getter=None, setter=None):
        """ (internal) Create a new JDBC type. """
        if isinstance(name, (str, type(None))):
            self._name = name
            self._values = [name]
        else:
            self._name = name[0]
            self._values = name
        self._code = code
        self._getter = getter
        self._setter = setter
        if code is not None:
            _registry[code] = self
        _types.append(self)

    def _initialize(self, cs, ps, rs):
        """ Called after the JVM starts initialize Java resources """
        if self._getter is None:
            self._getter = "getObject"
        self._rsget = getattr(rs, self._getter)
        self._csget = getattr(cs, self._getter, None)
        if self._setter is None:
            self._setter = "setObject"
        self._psset = getattr(ps, self._setter)

    def get(self, rs, column, st):
        """ A method to retrieve a specific JDBC type.

        To use a getter add the fetch method to the JDBC type matching the
        column type to be pulled.  For example, to set the getter for FLOAT to
        use the OBJECT getter, use  ``cx.getter[FLOAT] = OBJECT.get``.

        Not all getters are available on all database drivers.  Consult the
        database driver documentation for details.
        """
        try:
            if st:
                return self._csget(rs, column)
            return self._rsget(rs, column)
        except _SQLException as ex:
            raise InterfaceError("Unable to get '%s' using '%s'" % (self._name, self._getter)) from ex

    def set(self, ps, column, value):
        """ A method used to set a parameter to a query.

        To use a setter place the set method in the setter dict corresponding.
        For example, if the database supports Blob types, the default handler
        for BLOB can be changed from OBJECT to BLOB with
        ``cx.setter[BLOB] = BLOB.set``.

        Not all setters are available on all database drivers.  Consult the
        database driver documentation for details.
        """
        # Set the column with the specialized method
        try:
            if self._psset._matches(ps, column, value):
                return self._psset(ps, column, value)
            # Otherwise, try to set with the generic method
            return ps.setObject(column, value)
        except TypeError as ex:
            raise InterfaceError("Unable to convert '%s' into '%s'" % (type(value).__name__, self._name)) from ex
        except OverflowError as ex:
            raise InterfaceError("Unable to convert '%s' into '%s' calling '%s'" % (type(value).__name__, self._name, self._setter)) from ex

    def __repr__(self):
        if self._name is None:
            return ""
        return self._name

    def __eq__(self, other):
        return other in self._values

    def __hash__(self):
        return hash(self._name)


class _JDBCTypePrimitive(JDBCType):
    def get(self, rs, column, st):
        try:
            if st:
                rc = self._csget(rs, column)
            else:
                rc = self._rsget(rs, column)
            if rc == 0 and rs.wasNull():
                return None
            return rc
        except _SQLException as ex:
            raise InterfaceError("Unable to get '%s' using '%s'" % (self._name, self._getter)) from ex


# From https://www.cis.upenn.edu/~bcpierce/courses/629/jdkdocs/guide/jdbc/getstart/mapping.doc.html
# DATALINK = JDBCType('DATALINK',70)
# DISTINCT= JDBCType('DISTINCT',2001)
# REF_CURSOR = JDBCType('REF_CURSOR',2012)
# STRUCT = JDBCType('STRUCT',2002)
ARRAY = JDBCType('ARRAY', 2003, 'getArray', 'setArray')
BIGINT = _JDBCTypePrimitive('BIGINT', -5, 'getLong', 'setLong')
BIT = JDBCType('BIT', -7, 'getBoolean', 'setBoolean')
BLOB = JDBCType('BLOB', 2004, 'getBlob', 'setBlob')
BOOLEAN = _JDBCTypePrimitive('BOOLEAN', 16, 'getBoolean', 'setBoolean')
CHAR = JDBCType('CHAR', 1, 'getString', 'setString')
CLOB = JDBCType('CLOB', 2005, 'getClob', 'setClob')
DATE = JDBCType('DATE', 91, 'getDate', 'setDate')
DOUBLE = _JDBCTypePrimitive('DOUBLE', 8, 'getDouble', 'setDouble')
INTEGER = _JDBCTypePrimitive('INTEGER', 4, 'getInt', 'setInt')
OBJECT = JDBCType('OBJECT', 2000)
LONGNVARCHAR = JDBCType('LONGNVARCHAR', -16, 'getString', 'setString')
LONGVARBINARY = JDBCType('LONGVARBINARY', -4, 'getBytes', 'setBytes')
LONGVARCHAR = JDBCType('LONGVARCHAR', -1, 'getString', 'setString')
NCHAR = JDBCType('NCHAR', -15, 'getString', 'setString')
NCLOB = JDBCType('NCLOB', 2011, 'getNClob', 'setNClob')
NULL = JDBCType('NULL', 0)
NUMERIC = JDBCType('NUMERIC', 2, 'getBigDecimal', 'setBigDecimal')
NVARCHAR = JDBCType('NVARCHAR', -9, 'getClob', 'setClob')
OTHER = JDBCType('OTHER', 1111)
REAL = _JDBCTypePrimitive('REAL', 7, 'getFloat', 'setFloat')
REF = JDBCType('REF', 2006, 'getRef', 'setRef')
ROWID = JDBCType('ROWID', -8, 'getRowId', 'setRowId')
RESULTSET = JDBCType('RESULTSET', -10, 'getObject', 'setObject')
SMALLINT = _JDBCTypePrimitive('SMALLINT', 5, 'getShort', 'setShort')
SQLXML = JDBCType('SQLXML', 2009, 'getSQLXML', 'setSQLXML')
TIME = JDBCType('TIME', 92, 'getTime', 'setTime')
TIME_WITH_TIMEZONE = JDBCType('TIME_WITH_TIMEZONE', 2013, 'getTime', 'setTime')
TIMESTAMP = JDBCType('TIMESTAMP', 93, 'getTimestamp', 'setTimestamp')
TIMESTAMP_WITH_TIMEZONE = JDBCType('TIMESTAMP_WITH_TIMEZONE', 2014, 'getTimestamp', 'setTimestamp')
TINYINT = _JDBCTypePrimitive('TINYINT', -6, 'getShort', 'setShort')
VARBINARY = JDBCType('VARBINARY', -3, 'getBytes', 'setBytes')
VARCHAR = JDBCType('VARCHAR', 12, 'getString', 'setString')

# Aliases required by DBAPI2
STRING = JDBCType(['STRING', 'CHAR', 'NCHAR', 'NVARCHAR', 'VARCHAR', 'OTHER'], None,
                  'getString', 'setString')
TEXT = JDBCType(['TEXT', 'CLOB', 'LONGVARCHAR', 'LONGNVARCHAR', 'NCLOB', 'SQLXML'], None,
                'getString', 'setString')
BINARY = JDBCType(['BINARY', 'BLOB', 'LONGVARBINARY', 'VARBINARY'], -2,
                  'getBytes', 'setBytes')
NUMBER = JDBCType(['NUMBER', 'BOOLEAN', 'BIGINT', 'BIT', 'INTEGER', 'SMALLINT', 'TINYINT'], None,
                  'getObject', 'setObject')
FLOAT = _JDBCTypePrimitive(['FLOAT', 'REAL', 'DOUBLE'], 6,
                           'getDouble', 'setDouble')
DECIMAL = JDBCType(['DECIMAL', 'NUMERIC'], 3,
                   'getBigDecimal', 'setBigDecimal')
DATETIME = TIMESTAMP

# Special types
ASCII_STREAM = JDBCType(None, None, 'getAsciiStream', 'setAsciiStream')
BINARY_STREAM = JDBCType(None, None, 'getBinaryStream', 'setBinaryStream')
CHARACTER_STREAM = JDBCType(None, None, 'getCharacterStream', 'setCharacterStream')
NCHARACTER_STREAM = JDBCType(None, None, 'getNCharacterStream', 'setNCharacterStream')
URL = JDBCType(None, None, 'getURL', 'setURL')

# The converters are defined in a customizer

TRANSACTION_NONE = 0
TRANSACTION_READ_COMMITTED = 2
TRANSACTION_READ_UNCOMMITTED = 1
TRANSACTION_REPEATABLE_READ = 4
TRANSACTION_SERIALIZABLE = 8


def _asPython(x):
    return x._py()


_default_getters = {ARRAY: OBJECT.get, OBJECT: OBJECT.get, NULL: OBJECT.get,
                    REF: OBJECT.get, ROWID: OBJECT.get, RESULTSET: OBJECT.get,
                    TIME_WITH_TIMEZONE: OBJECT.get, TIMESTAMP_WITH_TIMEZONE: OBJECT.get,
                    NVARCHAR: STRING.get, CHAR: STRING.get,
                    NCHAR: STRING.get, VARCHAR: STRING.get, BINARY: BINARY.get,
                    BLOB: BINARY.get, LONGVARBINARY: BINARY.get, VARBINARY: BINARY.get,
                    NUMBER: NUMBER.get, BOOLEAN: BOOLEAN.get, BIGINT: BIGINT.get,
                    BIT: BIT.get, INTEGER: INTEGER.get, SMALLINT: SMALLINT.get,
                    TINYINT: TINYINT.get, FLOAT: FLOAT.get, REAL: REAL.get,
                    DECIMAL: DECIMAL.get, NUMERIC: NUMERIC.get,
                    DATE: DATE.get, TIMESTAMP: TIMESTAMP.get, TIME: TIME.get,
                    CLOB: STRING.get, NCLOB: STRING.get, STRING: STRING.get,
                    TEXT: STRING.get, SQLXML: STRING.get, LONGVARCHAR: STRING.get,
                    LONGNVARCHAR: STRING.get, DOUBLE: DOUBLE.get, OTHER: OBJECT.get
                    }

# This table converts most returns into Python types.
_default_converters = {
    CLOB: str, LONGNVARCHAR: str, LONGVARCHAR: str, NCLOB: str,
    SQLXML: str, NVARCHAR: str, CHAR: str, NCHAR: str,
    VARCHAR: str, FLOAT: float, DOUBLE: float, REAL: float,
    BOOLEAN: int, BIT: int, TINYINT: int, SMALLINT: int,
    INTEGER: int, BIGINT: int, DATE: _asPython, TIMESTAMP: _asPython,
    TIME: _asPython, DECIMAL: _asPython, NUMERIC: _asPython,
    BINARY: bytes, VARBINARY: bytes, BLOB: bytes,
}

_default_adapters = {}

_default_setters = {}


###############################################################################
# Exceptions


class Warning(Exception):
    """Exception raised for important warnings like data truncations while
    inserting, etc. """
    pass


class Error(Exception):
    """Exception that is the base class of all other error exceptions. You can use
    this to catch all errors with one single except statement. Warnings are not
    considered errors and thus should not use this class as base.
    """
    pass


class InterfaceError(Error, TypeError):
    """ Exception raised for errors that are related to the database interface
    rather than the database itself."""
    pass


class DatabaseError(Error):
    """ Exception raised for errors that are related to the database."""
    pass


class DataError(DatabaseError):
    """ Exception raised for errors that are due to problems with the processed
    data like division by zero, numeric value out of range, etc."""
    pass


class OperationalError(DatabaseError):
    """ Exception raised for errors that are related to the database's operation
    and not necessarily under the control of the programmer, e.g. an unexpected
    disconnect occurs, the data source name is not found, a transaction could not
    be processed, a memory allocation error occurred during processing, etc."""
    pass


class IntegrityError(DatabaseError):
    """ Exception raised when the relational integrity of the database is affected,
    e.g. a foreign key check fails."""
    pass


class InternalError(DatabaseError):
    """ Exception raised when the database encounters an internal error, e.g. the
    cursor is not valid anymore, the transaction is out of sync, etc."""
    pass


class ProgrammingError(DatabaseError):
    """ Exception raised for programming errors, e.g. table not found or already
    exists, syntax error in the SQL statement, wrong number of parameters
    specified, etc."""
    pass


class NotSupportedError(DatabaseError):
    """ Exception raised in case a method or database API was used which is not
    supported by the database, e.g. requesting a .rollback() on a connection that
    does not support transaction or has transactions turned off.
    """
    pass


class _UnsupportedTypeError(InterfaceError, TypeError):
    pass


###############################################################################
# Connection

_default = object()


def BY_JDBCTYPE(types, meta, col):
    """ Option to converterkeys to find converters by the JDBC type of the column """
    return types[col]


def BY_COLNAME(types, meta, col):
    """ Option to converterkeys to find converters by the column name """
    return meta.getColumnName(col + 1)


def connect(url, driver=None, driver_args=None,
            adapters=_default, converters=_default, getters=_default, setters=_default,
            converterkeys=BY_JDBCTYPE, **kwargs):
    """ Create a connection to a database.

    Arguments to the driver depend on the database type.

    Args:
       url (str): The database connection string for JDBC.
       driver (str, optional): A JDBC driver to load.
       driver_args: Arguments to the driver.  This may either be a dict,
          java.util.Properties.  If not supplied, kwargs are used as as the
          parameters for the JDBC connection.
       adapters (dict, optional): A mapping from types to JDBC types.  It is
          generally better to add the adapter to JDBC type directly.  Connection
          adapters are only used if a type specific adapter is not found.
       converters (dict, optional): A mapping from JDBC types to converter functions
          which convert JDBC types to result types.  If converters are None
          than Java types are returned.
       getters (dict, optional): A mapping of JDBC types to functions that retrieve
          data from a result set.
       setters (dict, optional): A mapping of types to functions that set
          parameters on queries.
       converterkeys (list): The list used to search for converters.  By
          default this is be BY_JDBCTYPE and will use the JDBC type as the key
          in lookup converters.  Key functions are called in order.  The first
          converter with a matching key is used.
       *kwargs: Arguments to the driver if not supplied as
          driver_args.

    Raises:
       Error if the connection cannot be established.

    Returns:
       A new connection if successful.
    """
    Properties = _jpype.JClass("java.util.Properties")
    if driver:
        _jpype.JClass('java.lang.Class').forName(driver).newInstance()
    DM = _jpype.JClass('java.sql.DriverManager')

    if not isinstance(converterkeys, (typing.Sequence, type(None))):
        converterkeys = (converterkeys,)
    if adapters is _default:
        adapters = dict(_default_adapters)
    if converters is _default:
        converters = dict(_default_converters)
    if converters is None:
        converters = {}
    if getters is _default or getters is None:
        getters = dict(_default_getters)
    if setters is _default or setters is None:
        setters = dict(_default_setters)

    # User is supplying Java properties
    if isinstance(driver_args, Properties):
        connection = DM.getConnection(url, driver_args)

    # User is supplying a mapping that can be converted Properties
    elif isinstance(driver_args, typing.Mapping):
        info = Properties()
        for k, v in driver_args.items():
            info.setProperty(k, v)
        connection = DM.getConnection(url, info)

    # User supplied nothing
    elif driver_args is None:
        connection = DM.getConnection(url)

    # Otherwise use the kwargs
    else:
        info = Properties()
        for k, v in kwargs.items():
            info.setProperty(k, v)
        connection = DM.getConnection(url, info)

    return Connection(connection, adapters, converters, getters, setters, converterkeys)


class Connection:
    """ Connection provides access to a JDBC database.

    Connections are managed and can be as part of a Python with statement.
    Connections close automatically when they are garbage collected, at the
    end of a with statement scope, or when manually closed.  Once a connection
    is closed all operations using the database will raise an Error.
    """
    Error = Error
    Warning = Warning
    InterfaceError = InterfaceError
    DatabaseError = DatabaseError
    InternalError = InternalError
    OperationalError = OperationalError
    ProgrammingError = ProgrammingError
    IntegrityError = IntegrityError
    DataError = DataError
    NotSupportedError = NotSupportedError

    def __init__(self, jconnection, adapters, converters, getters, setters, keystyle):
        self._jcx = jconnection
        # Required by PEP 249
        # https://www.python.org/dev/peps/pep-0249/#commit
        self._jcx.setAutoCommit(False)
        self._closed = False
        self._batch = jconnection.getMetaData().supportsBatchUpdates()
        self._adapters = adapters
        self._converters = converters
        self._getters = getters
        self._setters = setters
        self._keystyle = keystyle

    @property
    def adapters(self):
        """ Adapters are used to convert Python types into JDBC types.

        Adaptors are stored in a mapping from incoming type to an adapter
        function.  Adapters set on a connection apply only to that connection.
        Adapters can be overriden when calling the ``.execute*()`` method.

        Adapters can also be set on the JDBC types directly.
        """
        return self._adapters

    @adapters.setter
    def adapters(self, v):
        if not isinstance(v, typing.Mapping):
            raise TypeError("Mapping is required")
        self._adapters = v

    @property
    def converters(self):
        """ Converters are applied when retrieving a JDBC type from
        the database.

        Converters are stored in a mapping from a JDBC type to a converter.
        The key for matchin a converter is either the JDBC type or the column
        name depending on converter_type setting on the connection.  Converters
        can be overridden when calling the ``.fetch*()`` method.
        """
        return self._converters

    @converters.setter
    def converters(self, v):
        if not isinstance(v, typing.Mapping):
            raise TypeError("Mapping is required")
        self._converters = v

    @property
    def getters(self):
        """ Getters are used to retrieve JDBC types from the database.

        Each JDBC type must have a getter to retrieve a result.  The resulting
        Java value is then passed to the converter.  Getters can be defined for
        each connection.  If no getter if found ``getObject`` is used.
        """
        return self._getters

    @getters.setter
    def getters(self, v):
        if not isinstance(v, typing.Mapping):
            raise TypeError("Mapping is required")
        self._getters = v

    @property
    def setters(self):
        """ Setter are used to set parameters to ``.execute*()`` methods.

        Each paramter type must have a setter to set a parameter.  Adapters are
        applied before the setter.  Setters can be defined for each connection.
        """
        return self._setters

    @setters.setter
    def setters(self, v):
        if not isinstance(v, typing.Mapping):
            raise TypeError("Mapping is required")
        self._setters = v

    def __setattr__(self, name, value):
        if isinstance(vars(type(self)).get(name, None), property):
            return object.__setattr__(self, name, value)
        if not name.startswith("_"):
            raise AttributeError("'%s' cannot be set" % name)
        object.__setattr__(self, name, value)

    def _close(self):
        if self._closed or not _jpype.isStarted():
            return
        if not self._jcx.isClosed():
            self._jcx.close()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._close()

    def __del__(self):
        try:
            self._close()
        except Exception:  # pragma: no cover
            pass

    def close(self):
        """ Close the connection immediately (rather than whenever .__del__() is called).

        The connection will be unusable from this point forward; an Error (or
        subclass) exception will be raised if any operation is attempted with
        the connection. The same applies to all cursor objects trying to use
        the connection. Note that closing a connection without committing the
        changes first will cause an implicit rollback to be performed.  """
        self._validate()
        self._close()

    def commit(self):
        """Commit any pending transaction to the database.

        Calling commit on a cooonection that does not support the operation
        will raise NotSupportedError.
        """
        self._validate()
        if self._jcx.getAutoCommit():
            raise NotSupportedError("Autocommit is enabled")
        try:
            self._jcx.commit()
        except Exception as ex:  # pragma: no cover
            raise OperationalError(ex.message()) from ex

    def rollback(self):
        """Rollback the transaction.

        This method is optional since not all databases provide transaction
        support.  Calling rollback on a cooonection that does not support will
        raise NotSupportedError.

        In case a database does provide transactions this method causes the
        database to roll back to the start of any pending transaction. Closing
        a connection without committing the changes first will cause an
        implicit rollback to be performed.
        """
        self._validate()
        if self._jcx.getAutoCommit():
            raise NotSupportedError("Autocommit is enabled", self.autocommit)
        try:
            self._jcx.rollback()
        except Exception as ex:  # pragma: no cover
            raise OperationalError(ex.message()) from ex

    def cursor(self):
        """ Return a new Cursor Object using the connection. """
        self._validate()
        return Cursor(self)

    def _validate(self):
        if self._closed or self._jcx.isClosed():
            raise ProgrammingError

    @property
    def connection(self):
        """ Get the JDBC connection that is backing this Python
        Connection object.

        This can be used to retrieve additional metadata and other features
        that are outside of the scope of the DBAPI driver.
        """
        return self._jcx

    @property
    def autocommit(self):
        """ bool: Property controlling autocommit behavior.

        By default connects are not autocommit.  Setting autocommit
        will result in commit and rollback producing a ProgrammingError.
        """
        self._validate()
        return self._jcx.getAutoCommit()

    @autocommit.setter
    def autocommit(self, enabled):
        self._validate()
        self._jcx.setAutoCommit(enabled)

    @property
    def typeinfo(self):
        """ list: The list of types that are supported by this driver.

        This is useful to find out the capabilities of the driver.
        """
        self._validate()
        out = {}
        metadata = self._jcx.getMetaData()
        with metadata.getTypeInfo() as resultSet:
            while (resultSet.next()):
                try:
                    key = str(resultSet.getString("TYPE_NAME"))
                    out[key] = _registry[resultSet.getInt("DATA_TYPE")]
                except KeyError as ex:  # pragma: no cover
                    raise DatabaseError("Unknown data type '%s'" % key) from ex
        return out


###############################################################################
# Cursor


class Cursor:
    """ Cursors are used to execute queries and retrieve results.

    Part PreparedStatement, part ResultSet,  Cursors are a mixture of
    both.  The native resultSet can be accessed with ``resultSet``.

    Cursors are managed and can be as part of a Python with statement.
    Cursors close automatically when they are garbage collected, at the
    end of a with statement scope, or when manually closed.  Once a cursor
    is closed all operations using the database will raise an Error.
    """

    def __init__(self, connection):
        if not isinstance(connection, Connection):
            raise TypeError
        self._connection = connection
        self._jcx = connection._jcx
        self._resultSet = None
        self._statement = None
        self._rowcount = -1
        self._arraysize = 1
        self._description = None
        self._closed = False
        self._resultGetters = None
        self._thread = threading.get_ident()
        self._getters = self._connection._getters
        self._setters = self._connection._setters
        self._adapters = self._connection._adapters
        self._converters = self._connection._converters
        self._last = None

    def _close(self):
        if self._closed or not _jpype.isStarted():
            return
        self._finish()
        self._closed = True

    def _setParams(self, params):
        cx = self._connection
        meta = self._statement.getParameterMetaData()
        count = meta.getParameterCount()
        if isinstance(params, str):
            raise _UnsupportedTypeError("parameters must be a sequence of values")
        if isinstance(params, typing.Sequence):
            if count != len(params):
                raise ProgrammingError("incorrect number of parameters (%d!=%d)"
                                       % (count, len(params)))
            for i in range(len(params)):
                p = params[i]
                a = self._adapters.get(type(p), None)
                if a is not None:
                    p = a(p)
                s = self._setters.get(type(p), None)
                if s is None:
                    raise _UnsupportedTypeError("no setter found for '%s'" % type(p).__name__)
                s(self._statement, i + 1, p)
        elif isinstance(params, typing.Mapping):
            raise _UnsupportedTypeError("mapping parameters not supported")
        elif isinstance(params, typing.Iterable):
            for i, p in enumerate(params):
                if i >= count:
                    raise ProgrammingError("incorrect number of parameters (%d!=%d)" % (count, i + 1))
                a = self._adapters.get(type(p), None)
                if a is not None:
                    p = a(p)
                s = self._setters.get(type(p), None)
                if s is None:
                    raise _UnsupportedTypeError("no setter found for '%s'" % type(p).__name__)
                s(self._statement, i + 1, p)
            if count != i + 1:
                raise ProgrammingError("incorrect number of parameters (%d!=%d)" % (count, i + 1))
        else:
            raise _UnsupportedTypeError("'%s' parameters not supported" % (type(params).__name__))  # pragma: no cover

    def _fetchColumns(self):
        """ Get the list of getters and converters that apply to
        the result set. """
        if self._resultGetters is not None:
            return
        getters = self._getters
        converters = self._converters

        # Restore the defaults
        self._getters = self._connection._getters
        self._converters = self._connection._converters

        cx = self._connection
        meta = self._resultSet.getMetaData()
        count = meta.getColumnCount()

        # We need the type information for the columns
        jdbcTypes = [_registry[meta.getColumnType(i + 1)] for i in range(count)]

        # Set up all the converters
        if isinstance(converters, typing.Sequence):
            # Support for direct converter list
            if len(converters) != count:
                raise ProgrammingError("incorrect number of converters")
            self._resultConverters = converters
        else:
            # Support for JDBC type and column based converters
            rconverters = []
            for i in range(count):
                # Find the converter to apply to the column
                cnext = _nop
                if cx._keystyle is not None:
                    for lookup in cx._keystyle:
                        cnext = converters.get(lookup(jdbcTypes, meta, i), cnext)
                        if cnext is not _nop:
                            break
                if cnext is None:
                    cnext = _nop
                rconverters.append(cnext)
                self._resultConverters = rconverters

        # Set up all the getters
        if isinstance(getters, typing.Sequence):
            # Support for direct getter list
            if len(getters) != count:
                raise ProgrammingError("incorrect number of getters")
            self._resultGetters = getters
        else:
            self._resultGetters = [getters.get(t, OBJECT.get) for t in jdbcTypes]

    def use(self, *, converters=_default, getters=_default, adapters=_default, setters=_default):
        """ (extension) Apply a specific set of getter or converters to fetch
        operations for the current result set.

        This is called before an ``.execute*()`` or ``.callproc()`` method.
        The next statement executed will have these properties instead of the
        connection defaults.  The defaults will be restored once the statement
        is complete.  If called after ``.execute*()`` or ``nextset``, it will
        apply to the next result set.

        Args:
            converters (dict or list, optional):  Converters to apply to the
                next statement.  If converters is a list, then the converters are
                applied directly in order of column.  The number of converters must
                match the number of colums.  If converters is a dict, then the
                converts are looked up according to converterkeys.
            getters (dict or list, optional): Getters to use for this
                the next statement.  If getters is a list, then the
                getters are applied directly in order of the column.  The
                number of getters must match the number of columns.  If the
                getters is a dict, then the getters are looked up by type.
            adapters (dict, optional): Adapters to apply to the next statement.
                If this argument is None, then no adapters will be applied.
                This argument should only be used before an execute or 
                call proc statement.
            setter (dict, optional): Setters to use for the next statement.
                This argument should only be used before an execute or 
                call proc statement.

        Returns:
            This cursor.

        """
        self._validate()
        # Clear the caches
        self._resultConverters = None
        self._resultGetters = None
        if getters is _default:
            self._getters = self._connection._getters
        else:
            self._getters = getters
        if setters is _default:
            self._setters = self._connection._setters
        else:
            self._setters = setters
        if adapters is _default:
            self._adapters = self._connection._adapters
        else:
            self._adapters = adapters
        if converters is _default:
            self._converters = self._connection._converters
        elif converters is None:
            self._converters = {}
        else:
            self._converters = converters
        return self

    def _fetchRow(self):
        try:
            row = []
            for idx in range(len(self._resultGetters)):
                value = self._resultGetters[idx](self._resultSet, idx + 1, False)
                if value is None:
                    row.append(None)
                else:
                    row.append(self._resultConverters[idx](value))
            return row
        except TypeError as ex:
            raise _UnsupportedTypeError(str(ex)) from ex

    def _validate(self):
        """ Called before any method that requires the statement to be open. """
        if self._closed or self._jcx.isClosed() or threading.get_ident() != self._thread:
            raise ProgrammingError("Cursor is closed")

    def _check_executed(self):
        """ Called before any method that requires the resultSet to be open. """
        if self._closed or self._jcx.isClosed() or threading.get_ident() != self._thread:
            raise ProgrammingError("Cursor is closed")
        if self._resultSet is None:
            raise ProgrammingError("execute() first")

    def _finish(self):
        if self._resultSet is not None:
            self._resultSet.close()
            self._resultSet = None
        if self._statement is not None:
            self._statement.close()
            self._statement = None
        self._resultGetters = None
        self._rowcount = -1
        self._description = None
        self._last = None

    @property
    def resultSet(self):
        """ Get the Java result set if available.

        The object will be closed on the next call to ``.execute*()``.
        """
        return self._resultSet

    @property
    def parameters(self):
        """ (extension) Parameters is read-only attribute is a sequence of
        6-item sequences.

        Each of these sequences contains information describing one result
        column:

        - type_name
        - jdbc_type
        - parameter_mode (1=in, 2=in/out, 4=out)
        - precision
        - scale
        - null_ok

        This can only be used after execute or callproc.
        """
        desc = []
        if not self._statement:
            raise ProgrammingError("No statement")
        meta = self._statement.getParameterMetaData()
        for i in range(1, meta.getParameterCount() + 1):
            desc.append((str(meta.getParameterTypeName(i)),
                         _registry[meta.getParameterType(i)],
                         meta.getParameterMode(i),
                         meta.getPrecision(i),
                         meta.getScale(i),
                         meta.isNullable(i),))
        return desc

    @property
    def description(self):
        """ Description is read-only attribute is a sequence of 7-item
        sequences.

        Each of these sequences contains information describing one result
        column:

        - name
        - type_code
        - display_size
        - internal_size
        - precision
        - scale
        - null_ok

        This can only be used if the last query produced a result set.
        """
        if self._description is not None:
            return self._description
        desc = []
        if not self._resultSet:
            return None
        meta = self._resultSet.getMetaData()
        for i in range(1, meta.getColumnCount() + 1):
            size = meta.getColumnDisplaySize(i)
            desc.append((str(meta.getColumnName(i)),
                         str(meta.getColumnTypeName(i)),
                         size,
                         size,
                         meta.getPrecision(i),
                         meta.getScale(i),
                         meta.isNullable(i),))
        self._description = desc
        return desc

    @property
    def rowcount(self):
        """ This read-only attribute specifies the number of rows that the last
        .execute*() affected (for DML statements like UPDATE or INSERT).

        The attribute is -1 in case no .execute*() has been performed on the
        cursor or the rowcount of the last operation is cannot be determined by
        the interface.  JDBC does not support getting the number of rows
        returned from SELECT, so for most drivers rowcount will be -1 after a
        SELECT statement.
        """
        return self._rowcount

    def close(self):
        """ Close the cursor now (rather than whenever __del__ is called).

        The cursor will be unusable from this point forward; an Error (or
        subclass) exception will be raised if any operation is attempted with
        the cursor.
        """
        self._validate()
        self._close()

    def callproc(self, procname, parameters=()):
        """ Call a stored procedure.

        (Not all JDBC drivers support this method)

        Call a stored database procedure with the given name. The sequence of
        parameters must contain one entry for each argument that the procedure
        expects. The result of the call is returned as modified copy of the
        input sequence. Input parameters are left untouched, output and
        input/output parameters replaced with possibly new values.

        Converters are applied to out parameters.  Converters may not be a list
        for this method.

        The procedure may also provide a result set as output. This must then
        be made available through the standard .fetch*() methods. 
        """
        try:
            self._validate()
            self._finish()
            if not isinstance(procname, str):
                raise _UnsupportedTypeError("procname must be str, not '%s'" % type(procname).__name__)
            if not isinstance(parameters, typing.Sequence):
                raise _UnsupportedTypeError("parameters must be sequence, not '%s'" % type(procname).__name__)
            query = "{CALL %s(%s)}" % (procname, ",".join("?" * len(parameters)))
            try:
                self._statement = self._jcx.prepareCall(query)
            except _SQLException as ex:
                raise ProgrammingError(ex.message()) from ex

            # This is a special one as we need to deal with in and out arguments
            out = list(parameters)
            cx = self._connection
            meta = self._statement.getParameterMetaData()
            count = meta.getParameterCount()
            retrieve = [None] * count
            for i in range(count):
                # Lookup the JDBC Type
                p = parameters[i]
                a = self._adapters.get(type(p), None)
                if a is not None:
                    p = a(p)
                setter = self._setters.get(type(p), None)
                if setter is None:
                    raise _UnsupportedTypeError("no setter found for '%s'" % type(p).__name__)

                mode = meta.getParameterMode(i + 1)
                if mode == 1:
                    setter(self._statement, i + 1, p)
                if mode == 2:
                    setter(self._statement, i + 1, p)
                    self.registerOutParameter(i, sqlType)
                    retrieve[i] = jdbcType
                if mode == 4:
                    self.registerOutParameter(i + 1, sqlType)
                    retrieve[i] = jdbcType

            self._resultSet = self._statement.executeQuery()
            for i, t in enumerate(retrieve):
                if t is None:
                    continue

                # Find the converter to apply to the column
                cnext = _nop
                if cx._keystyle is not None:
                    for lookup in cx._keystyle:
                        cnext = converters.get(lookup(jdbcTypes, meta, i), cnext)
                        if cnext is not _nop:
                            break
                if cnext is None:
                    cnext = _nop
                    continue
                get = getters.get(t, OBJECT.get)
                out[i] = get(self._statement, i + 1, True)

            return out

        # Restore the defaults
        except Exception as ex:
            self._converters = self._connection._converters
            self._getters = self._connection._getters
            raise ex
        finally:
            self._adapters = self._connection._adapters
            self._setters = self._connection._setters

    def execute(self, operation, parameters=None, *, keys=False):
        """
        Prepare and execute a database operation (query or command).

        Parameters may be provided as sequence and will be bound to variables
        in the operation. Variables are specified in a qmark notation.  JDBC
        does not support mapping style parameters.

        After executing a statement, the rowcount will be updated.  If the
        statement has no result set then the rowcount will be -1.  A statement
        can produce multiple result sets.  Use ``.nextset()`` to traverse the
        sets.

        Parameters:
           operation (str): A statement to be executed.
           parameters (list, optional): A list of parameters for the statement.
              The number of parameters much match the number required by the
              statement or an Error will be raised.
           keys (bool, optional): Specify if the keys should be available to 
              retrieve. (Default False) 

        Returns:
           This cursor.
        """
        try:
            self._validate()
            self._finish()
            if parameters is None:
                parameters = ()
            if not isinstance(parameters, (typing.Sequence, typing.Iterable, typing.Iterator)):
                raise _UnsupportedTypeError("parameters are of unsupported type '%s'" % type(parameters).__name__)
            # complete the previous operation
            try:
                if keys:
                    self._statement = self._jcx.prepareStatement(operation, 1)
                else:
                    self._statement = self._jcx.prepareStatement(operation)
            except TypeError as ex:
                raise _UnsupportedTypeError(str(ex))
            except _SQLException as ex:
                raise ProgrammingError(ex.message()) from ex
            self._executeone(parameters)
            return self

        # Restore the defaults
        except Exception as ex:
            self._converters = self._connection._converters
            self._getters = self._connection._getters
            raise ex
        finally:
            self._adapters = self._connection._adapters
            self._setters = self._connection._setters

    def _executeone(self, params):
        self._setParams(params)
        if self._statement.execute():
            self._resultSet = self._statement.getResultSet()
        self._rowcount = self._statement.getUpdateCount()
        return self._rowcount

    def executemany(self, operation, seq_of_parameters, *, keys=False):
        """
        Prepare a database operation (query or command) and then execute it
        against all parameter sequences or mappings found in the sequence
        seq_of_parameters.

        Modules are free to implement this method using multiple calls to the
        .execute() method or by using array operations to have the database
        process the sequence as a whole in one call.

        Use of this method for an operation which produces one or more result
        sets constitutes undefined behavior, and the implementation is
        permitted (but not required) to raise an exception when it detects that
        a result set has been created by an invocation of the operation.

        The same comments as for .execute() also apply accordingly to this
        method.

        Args:
           operation (str): A statement to be executed.
           seq_of_parameters (list, optional): A list of lists of parameters
               for the statement.  The number of parameters much match the number
               required by the statement or an Error will be raised.
           keys (bool, optional): Specify if the keys should be available to 
              retrieve. (Default False) For drivers that do not support
              batch updates only that last key will be returned.

        Returns:
           This cursor.
        """
        try:
            self._validate()
            if seq_of_parameters is None:
                seq_of_parameters = ()
            # complete the previous operation
            self._finish()
            try:
                if keys:
                    self._statement = self._jcx.prepareStatement(operation, 1)
                else:
                    self._statement = self._jcx.prepareStatement(operation)
            except TypeError as ex:
                raise _UnsupportedTypeError(str(ex))
            except _SQLException as ex:
                raise ProgrammingError("Failed to prepare '%s'" % operation) from ex
            if self._connection._batch:
                return self._executeBatch(seq_of_parameters)
            else:  # pragma: no cover
                return self._executeRepeat(seq_of_parameters)

        # Restore the defaults
        except Exception as ex:
            self._converters = self._connection._converters
            self._getters = self._connection._getters
            raise ex
        finally:
            self._adapters = self._connection._adapters
            self._setters = self._connection._setters

    def _executeBatch(self, seq_of_parameters):
        if isinstance(seq_of_parameters, typing.Iterable):
            for params in seq_of_parameters:
                self._setParams(params)
                self._statement.addBatch()
        else:
            raise _UnsupportedTypeError("'%s' is not supported" % type(seq_of_parameters).__name__)
        try:
            counts = self._statement.executeBatch()
        except _SQLException as ex:  # pragma: no cover
            raise ProgrammingError(ex.message()) from ex
        self._rowcount = sum(counts)
        if self._rowcount < 0:  # pragma: no cover
            self._rowcount = -1
        return self

    def _executeRepeat(self, seq_of_parameters):  # pragma: no cover
        counts = []
        if isinstance(seq_of_parameters, typing.Iterable):
            for params in seq_of_parameters:
                counts.append(self._executeone(params))
        elif isinstance(seq_of_parameters, typing.Iterator):
            while True:
                try:
                    params = next(seq_of_parameters)
                    counts.append(self._executeone(params))
                except StopIteration:
                    break
        else:
            raise _UnsupportedTypeError("'%s' is not supported" % str(type(seq_of_parameters)))
        try:
            counts = self._statement.executeBatch()
        except _SQLException as ex:
            raise ProgrammingError from ex
        self._rowcount = sum(counts)
        if self._rowcount < 0:
            self._rowcount = -1
        return self

    def fetchone(self):
        """
        Fetch the next row of a query result set, returning a single
        sequence, or None when no more data is available.

        An Error (or subclass) exception is raised if the previous call to
        .execute*() did not produce any result set or no call was issued yet.

        The retrieval of the columns can be altered using ``use`` prior
        to calling a fetch.
        """
        self._check_executed()
        if not self._resultSet.next():
            return None
        self._fetchColumns()
        return self._fetchRow()

    def fetchmany(self, size=None):
        """ Fetch multiple results.

        Fetch the next set of rows of a query result, returning a sequence of
        sequences (e.g. a list of tuples). An empty sequence is returned when
        no more rows are available.

        The number of rows to fetch per call is specified by the parameter. If it
        is not given, the cursor's arraysize determines the number of rows to be
        fetched. The method should try to fetch as many rows as indicated by the
        size parameter. If this is not possible due to the specified number of rows
        not being available, fewer rows may be returned.

        An Error (or subclass) exception is raised if the previous call to
        ``.execute*()`` did not produce any result set or no call was issued yet.

        Note there are performance considerations involved with the size parameter.
        For optimal performance, it is usually best to use the .arraysize
        attribute. If the size parameter is used, then it is best for it to retain
        the same value from one ``.fetchmany()`` call to the next.

        The retrieval of the columns can be altered using ``use`` prior
        to calling a fetch.
        """
        self._check_executed()
        if size is None:
            size = self._arraysize
        # Set a fetch size
        self._resultSet.setFetchSize(size)
        self._fetchColumns()
        rows = []
        for i in range(size):
            if not self._resultSet.next():
                break
            row = self._fetchRow()
            rows.append(row)
        # Restore the default fetch size
        self._resultSet.setFetchSize(0)
        return rows

    def fetchall(self):
        """ Fetch all (remaining) rows of a query result, returning them as
        a sequence of sequences (e.g. a list of tuples). Note that the cursor's
        arraysize attribute can affect the performance of this operation.

        An Error (or subclass) exception is raised if the previous call to
        ``.execute*()`` did not produce any result set or no call was issued yet.

        The retrieval of the columns can be altered using ``use`` prior
        to calling a fetch.
        """
        self._check_executed()
        # Set a fetch size
        self._fetchColumns()
        rows = []
        while self._resultSet.next():
            row = self._fetchRow()
            rows.append(row)
        return rows

    def __iter__(self):
        """ (extension) Iterate through a cursor one record at a time.

        The retrieval of the columns can be altered using ``use`` prior
        to calling a fetch.
        """
        self._check_executed()
        # Set a fetch size
        self._fetchColumns()
        while self._resultSet.next():
            yield self._fetchRow()

    def nextset(self):
        """ Get the next result set in this cursor.

        Not all databases support multiple result sets.

        This method will make the cursor skip to the next available set, discarding
        any remaining rows from the current set.

        If there are no more sets, the method returns None. Otherwise, it returns a
        true value and subsequent calls to the ``.fetch*()`` methods will return rows
        from the next result set.

        An Error (or subclass) exception is raised if the previous call to
        ``.execute*()`` did not produce any result set or no call was issued yet.
        """
        self._resultSet.close()
        self._resultGetters = None
        self._resultConverters = None
        if self._statement.getMoreResults():  # pragma: no cover
            self._resultSet = self._prepareStatement.getResultSet()
            return True
        else:
            self._rowcount = self._statement.getUpdateCount()
            return None

    @property
    def arraysize(self):
        """
        Specify the number of rows to fetch with ``.fetchmany()``.

        This read/write attribute specifies the number of rows to fetch
        at a time with ``.fetchmany()``. It defaults to 1 meaning to fetch a single row
        at a time.
        """
        return self._arraysize

    @arraysize.setter
    def arraysize(self, sz):
        self._arraysize = sz

    @property
    def lastrowid(self):
        """ Get the id of the last row inserted.

        This is not supported on all JDBC drivers. The ``.execute*()`` must have
        been executed with keys set to True.

        Returns:
           None if there is no rowid, the rowid if only one row was inserted,
           or a list of row ids if multiple rows were inserted.
        """
        with self._statement.getGeneratedKeys() as rs:
            if rs.isClosed():
                return self._last
            last = []
            while rs.next():
                last.append(rs.getLong(1))
            if len(last) == 0:
                return None
            if len(last) == 1:
                self._last = last[0]
                return last[0]
            self._last = last
            return last

    def setinputsizes(self, sizes):
        """ This can be used before a call to .execute*() to
        predefine memory areas for the operation's parameters.

        sizes is specified as a sequence — one item for each input parameter. The
        item should be a Type Object that corresponds to the input that will be
        used, or it should be an integer specifying the maximum length of a string
        parameter. If the item is None, then no predefined memory area will be
        reserved for that column (this is useful to avoid predefined areas for
        large inputs).

        This method would be used before the .execute*() method is invoked.

        (not implemented)
        """
        pass

    def setoutputsize(self, size, column=None):
        """
        Set a column buffer size for fetches of large columns (e.g. LONGs, BLOBs, etc.).

        The column is specified as an index into the result sequence. Not
        specifying the column will set the default size for all large columns
        in the cursor.

        (not implemented)
        """
        pass

    def __del__(self):
        try:
            self._close()
        except Exception:  # pragma: no cover
            pass

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._close()

###############################################################################
# Factories


def Date(year, month, day):
    """ This function constructs an object holding a date value. """
    return _jpype.JClass('java.sql.Date')(year - 1900, month - 1, day)


def Time(hour, minute, second):
    """ This function constructs an object holding a time value. """
    return _jpype.JClass('java.sql.Time')(hour, minute, second)


def Timestamp(year, month, day, hour, minute, second, nano=0):
    """ This function constructs an object holding a time stamp value. """
    return _jpype.JClass('java.sql.Timestamp')(year - 1900, month - 1, day, hour, minute, second, nano)


def DateFromTicks(ticks):
    """
    This function constructs an object holding a date value from the given
    ticks value (number of seconds since the epoch; see the documentation of
    the standard Python time module for details).
    """
    return Date(*time.localtime(ticks)[:3])


def TimeFromTicks(ticks):
    """

    This function constructs an object holding a time value from the given
    ticks value (number of seconds since the epoch; see the documentation of
    the standard Python time module for details).
    """
    return Time(*time.localtime(ticks)[3:6])


def TimestampFromTicks(ticks):
    """
    This function constructs an object holding a time stamp value from the
    given ticks value (number of seconds since the epoch; see the documentation
    of the standard Python time module for details).
    """
    return Timestamp(*time.localtime(ticks)[:6])


def Binary(data):
    """
    This function constructs an object capable of holding a binary (long)
    string value.
    """
    return _jtypes.JArray(_jtypes.JByte)(data)


#  SQL NULL values are represented by the Python None singleton on input and output.
_accepted = set(["exact", "implicit"])


def _populateTypes():
    global _SQLException, _SQLTimeoutException
    _SQLException = _jpype.JClass("java.sql.SQLException")
    _SQLTimeoutException = _jpype.JClass("java.sql.SQLTimeoutException")
    cs = _jpype.JClass("java.sql.CallableStatement")
    ps = _jpype.JClass("java.sql.PreparedStatement")
    rs = _jpype.JClass("java.sql.ResultSet")
    for v in _types:
        v._initialize(cs, ps, rs)

    java = _jpype._JPackage("java")

    _default_setters[java.lang.String] = STRING.set
    _default_setters[java.sql.Date] = DATE.set
    _default_setters[java.sql.Time] = TIME.set
    _default_setters[java.sql.Timestamp] = TIMESTAMP.set
    _default_setters[_jpype.JArray(_jtypes.JByte)] = TIMESTAMP.set
    _default_setters[java.math.BigDecimal] = DECIMAL.set
    _default_setters[_jtypes.JFloat] = REAL.set
    _default_setters[_jtypes.JDouble] = DOUBLE.set
    _default_setters[_jtypes.JBoolean] = BOOLEAN.set
    _default_setters[_jtypes.JShort] = INTEGER.set
    _default_setters[_jtypes.JInt] = INTEGER.set
    _default_setters[_jtypes.JLong] = BIGINT.set
    _default_setters[bool] = BOOLEAN.set
    _default_setters[int] = BIGINT.set
    _default_setters[float] = DOUBLE.set
    _default_setters[str] = STRING.set
    _default_setters[memoryview] = BINARY.set
    _default_setters[bytes] = BINARY.set
    _default_setters[bytearray] = BINARY.set
    _default_setters[type(None)] = OBJECT.set
    _default_setters[java.sql.Clob] = CLOB.set
    _default_setters[java.sql.Blob] = BLOB.set
    _default_setters[datetime.datetime] = TIMESTAMP.set
    _default_setters[datetime.date] = DATE.set
    _default_setters[datetime.time] = TIME.set
    # Adaptors can be installed after the JVM is started
    # JByteArray = _jpype.JArray(_jtypes.JByte)
    # VARCHAR.adapters[memoryview] = JByteArray


_jcustomizer.getClassHints("java.sql.SQLException").registerClassBase(Error)
_jinit.registerJVMInitializer(_populateTypes)

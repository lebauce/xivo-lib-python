# -*- coding: utf-8 -*-
# Copyright 2007-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""DBAPI Helper using URI to create talk to various DB

Copyright (C) 2007-2010  Avencall

WARNING: this module is not DBAPI 2.0 compliant by itself

"""

__version__ = "$Revision$ $Date$"

import logging
from six.moves.urllib import parse

__uri_create_methods = {}

any_paramstyle = 'format'
any_threadsafety = 1
any_apilevel = '2.0'

METHOD_CONNECT = 0
METHOD_MODULE = 1
METHOD_C14N_URI = 2
METHOD_ESCAPE = 3
METHOD_CAST = 4

log = logging.getLogger("xivo.anysql")


class cursor(object):
    """
    This class is a Anysql wrapper for DBAPI2.0 Cursor Objects.

    .executeXYZ() methods are replaced by .queryXYZ(), which are kind of
    slightly enhanced versions of the former.
    .fetchXYZ() returns augmented DBAPI2.0 rows.

    .close()
    .setinputsizes()
    .setoutputsize()
    .description
    .rowcount
    .arraysize      passthrough

    .query()
    .querymany()    preformat the request by injecting column names in
                    place of the "${columns}" substring and save the
                    associations between columns names and their position
                    in the query.

    .fetchone()
    .fetchmany()
    .fetchall()     return near DBAPI2.0 compatible rows (list based
                    instead of tuple based) that are also indexable by
                    their column names.
    """

    class row(list):
        def __init__(self, col2idx_map, dbapi2_result):
            list.__init__(self, dbapi2_result)
            self.__col2idx_map = col2idx_map

        def __getitem__(self, k):
            if isinstance(k, int):
                return list.__getitem__(self, k)
            else:
                return list.__getitem__(self, self.__col2idx_map[k])

        def iteritems(self):
            return (
                (k, list.__getitem__(self, pos))
                for (k, pos) in self.__col2idx_map.iteritems()
            )

    def __init__(self, connection, methods):
        """
        WARNING: For internal use only.
        - dbapi2_cursor is an underlying DBAPI2.0 cursor
        - methods: private object describing the underlying backend,
          internally generated by this module using information
          provided by the backend at registration time.
        """
        self.__connection = connection
        self.__dbapi2_cursor = connection._get_raw_cursor()
        self.__methods = methods

    def close(self):
        "As in DBAPI2.0"
        self.__dbapi2_cursor.close()

    def __preparequery(self, sql_query, columns):
        """
        WARNING: You can't both pass a ${columns} literal to the
        underlying .execute() method and use the columns escaping,
        injection and symbolic access mechanism.
        WARNING: It is not recommended to SELECT *
        """
        if columns:
            if "${columns}" not in sql_query:
                raise TypeError("received columns but ${columns} not in query")

            escape = self.__methods[METHOD_ESCAPE]

            self.__col2idx_map = {}
            col_list = []

            for idx, col in enumerate(columns):
                self.__col2idx_map[col] = idx
                col_list.append(escape(col))

            return sql_query.replace("${columns}", ",".join(col_list))
        else:
            self.__col2idx_map = None

            return sql_query

    def query(self, sql_query, columns=None, parameters=None):
        """
        If columns evaluates to true, sql_query must contain
        "${columns}" (only once) and this substring will be replaced
        by an SQL representation of the list of columns, correctly
        escaped for the backend.
        The resulting string is passed to the DBAPI2.0 .execute()
        method of the underlying DBAPI2.0 cursor, alongside with
        parameters.
        If ''not columns'', the sql_query string will be passed
        unchanged to the DBAPI2.0 .execute() method.
        """
        tmp_query = self.__preparequery(sql_query, columns)

        if self.__methods[METHOD_MODULE].paramstyle == "qmark":
            if parameters is not None:
                tmp_query = tmp_query % parameters
                parameters = None

        try:
            if parameters is None:
                self.__dbapi2_cursor.execute(tmp_query)
            else:
                self.__dbapi2_cursor.execute(tmp_query, parameters)
        except Exception:
            # try to reconnect
            self.__connection.reconnect()
            self.__dbapi2_cursor = self.__connection._get_raw_cursor()

            if parameters is None:
                self.__dbapi2_cursor.execute(tmp_query)
            else:
                self.__dbapi2_cursor.execute(tmp_query, parameters)

    def querymany(self, sql_query, columns, seq_of_parameters):
        """
        Same as .query() but eventually call the .executemany() method
        of the underlying DBAPI2.0 cursor instead of .execute()
        """
        tmp_query = self.__preparequery(sql_query, columns)

        if self.__methods[METHOD_MODULE].paramstyle == "qmark":
            raise NotImplementedError("qmark isn't fully supported")

        try:
            self.__dbapi2_cursor.executemany(tmp_query, seq_of_parameters)
        except Exception:
            self.__connection.reconnect()
            self.__dbapi2_cursor = self.__connection._get_raw_cursor()

            self.__dbapi2_cursor.executemany(tmp_query, seq_of_parameters)

    def fetchone(self):
        """
        As in DBAPI2.0 (except the fact rows are not tuples but
        lists so if you try to modify them, you will succeed instead of
        the correct behaviour of raising an exception).
        Additionally every row returned by this class is addressable
        by column name besides the column position in the query.
        """
        try:
            result = self.__dbapi2_cursor.fetchone()
        except Exception:
            self.__connection.reconnect()
            self.__dbapi2_cursor = self.__connection._get_raw_cursor()

            result = self.__dbapi2_cursor.fetchone()

        if not result:
            return result
        else:
            return self.row(self.__col2idx_map, result)

    def fetchmany(self, size=None):
        """
        As in DBAPI2.0 (except the fact rows are not tuples but
        lists so if you try to modify them, you will succeed instead of
        the correct behavior that would be that an exception would have
        been raised)
        Additionally every row returned by this class is addressable
        by column name besides the column position in the query.
        """
        try:
            if size is None:
                manyrows = self.__dbapi2_cursor.fetchmany()
            else:
                manyrows = self.__dbapi2_cursor.fetchmany(size)
        except Exception:
            self.__connection.reconnect()
            self.__dbapi2_cursor = self.__connection._get_raw_cursor()

            if size is None:
                manyrows = self.__dbapi2_cursor.fetchmany()
            else:
                manyrows = self.__dbapi2_cursor.fetchmany(size)

        if not manyrows:
            return manyrows
        else:
            return [self.row(self.__col2idx_map, dbapi2_row) for dbapi2_row in manyrows]

    def fetchall(self):
        """
        As in DBAPI2.0 (except the fact rows are not tuples but
        lists so if you try to modify them, you will succeed instead of
        the correct behavior that would be that an exception would have
        been raised)
        Additionally every row returned by this class is addressable
        by column name besides the column position in the query.
        """
        try:
            allrows = self.__dbapi2_cursor.fetchall()
        except Exception:
            self.__connection.reconnect()
            self.__dbapi2_cursor = self.__connection._get_raw_cursor()

            allrows = self.__dbapi2_cursor.fetchall()

        if not allrows:
            return allrows
        else:
            return [self.row(self.__col2idx_map, dbapi2_row) for dbapi2_row in allrows]

    def setinputsizes(self, sizes):
        "As in DBAPI2.0"
        self.__dbapi2_cursor.setinputsizes(sizes)

    def setoutputsize(self, size, column=None):
        "As in DBAPI2.0"
        if column is None:
            self.__dbapi2_cursor.setoutputsize(size)
        else:
            self.__dbapi2_cursor.setoutputsize(size, column)

    def __get_description(self):
        return self.__dbapi2_cursor.description

    def __get_lastrowid(self):
        return self.__dbapi2_cursor.lastrowid

    def __get_rowcount(self):
        return self.__dbapi2_cursor.rowcount

    def __get_arraysize(self):
        return self.__dbapi2_cursor.arraysize

    def __set_arraysize(self, arraysize):
        self.__dbapi2_cursor.arraysize = arraysize

    def cast(self, fieldname, type):
        cast_ = self.__methods[METHOD_CAST]
        if cast_ is None:
            return fieldname

        return cast_(fieldname, type)

    description = property(__get_description, None, None, "As in DBAPI2.0")
    lastrowid = property(__get_lastrowid, None, None, "As in DBAPI2.0")
    rowcount = property(__get_rowcount, None, None, "As in DBAPI2.0")
    arraysize = property(__get_arraysize, __set_arraysize, None, "As in DBAPI2.0")


class connection:
    """
    This class is a Anysql wrapper for DBAPI2.0 Connection Objects.
    It does not do much: essentially it just pass method calls to the
    underlying DBAPI2.0 object, with the exception of the .cursor()
    method which will not directly returns the DBAPI2.0 cursor but wrap
    it using the anysql.cursor class.
    WARNING: instantiation of this class is private to this module and is
    automatically performed by connect_by_uri()
    WARNING: even if the instantiation mecanism is put appart, this class
    still does not constitute a DBAPI2.0 Connection Object because the
    .cursor() method generate a Cursor Object that is not a real DBAPI2.0
    Cursor Object (it has a slightly different and incompatible method
    .query() instead of .execute())
    """

    def __init__(self, sqluri):
        """
        Contructor: takes two arguments
          - dbapi2_conn: underlying DBAPI2.0 connection object
          - methods: private object describing the underlying backend,
            internally generated by this module using information
            provided by the backend at registration time.
        WARNING: instantiation of this class is private to this module
        and is automatically performed by connect_by_uri()
        """
        self.sqluri = sqluri
        self.__connect()

    def __connect(self):
        """
        Connect to the database.
        """
        self.__methods = _get_methods_by_uri(self.sqluri)
        uri_connect_method = self.__methods[METHOD_CONNECT]

        self.__dbapi2_conn = uri_connect_method(self.sqluri)

    def reconnect(self):
        """
        Reconnect to the database.
        """
        log.warning('reconnecting to %s database' % self.sqluri)
        self.__connect()

    def close(self):
        """
        As in DBAPI2.0:
        Close the connection now (rather than whenever __del__ is
        called).  The connection will be unusable from this point
        forward; an Error (or subclass) exception will be raised
        if any operation is attempted with the connection. The
        same applies to all cursor objects trying to use the
        connection.  Note that closing a connection without
        committing the changes first will cause an implicit
        rollback to be performed.
        """
        self.__dbapi2_conn.close()

    def commit(self):
        """
        As in DBAPI2.0:
        Commit any pending transaction to the database. Note that
        if the database supports an auto-commit feature, this must
        be initially off. An interface method may be provided to
        turn it back on.

        Database modules that do not support transactions should
        implement this method with void functionality.
        """
        self.__dbapi2_conn.commit()

    def rollback(self):
        """
        As in DBAPI2.0:
        This method is optional since not all databases provide
        transaction support. [3]

        In case a database does provide transactions this method
        causes the database to roll back to the start of any
        pending transaction.  Closing a connection without
        committing the changes first will cause an implicit
        rollback to be performed.
        """
        self.__dbapi2_conn.rollback()

    def cursor(self):
        """
        Returns a new Cursor Object using the connection,
        that is NOT a DBAPI2.0 cursor.
        An underlying real DBAPI2.0 cursor will be asked to the
        underlying backend for use by the cursor object returned by
        this method, and the former will only be referenced by the
        latter.
        The Cursor Object returned by this method will be an instance
        of the class cursor of this module.
        """
        return cursor(self, self.__methods)

    def _get_raw_cursor(self):
        """
            Return a new DBAPI2.0 cursor object.
        """
        return self.__dbapi2_conn.cursor()


def __compare_api_level(als1, als2):
    lst1 = map(int, als1.split('.'))
    lst2 = map(int, als2.split('.'))
    if lst1 < lst2:
        return -1 - bool(lst1[0] < lst2[0])
    elif lst1 > lst2:
        return 1 + bool(lst1[0] > lst2[0])
    else:
        return 0


def register_uri_backend(
    uri_scheme, create_method, module, c14n_uri_method, escape, cast
):
    """
    This method is intended to be used by backends only.

    It lets them register their services, identified by the URI scheme,
    at import time. The associated method create_method must take one
    parameter: the complete requested RFC 3986 compliant URI.

    The associated module must be compliant with DBAPI v2.0 but will not
    be directly used for other purposes than compatibility testing.

    c14n_uri_method must be a function that takes one string argument (the
    same form that the one that would be passed to connect_by_uri) and
    returns its canonicalized form in an implementation dependant way. This
    includes transforming any local pathname into an absolute form.
    c14n_uri_method can also be None, in which case the behavior will be
    the same as the one of the identity function.

    escape must be a function that takes one string argument (an unescaped
    column name) and returns an escaped version for use as an escaped
    column name in an SQL query for this backend.

    If something obviously not compatible is tried to be registred,
    NotImplementedError is raised.
    """
    try:
        delta_api = __compare_api_level(module.apilevel, any_apilevel)
        mod_paramstyle = module.paramstyle
        mod_threadsafety = module.threadsafety
    except NameError:
        raise NotImplementedError(
            "This module does not support registration of non DBAPI services of at least apilevel 2.0"
        )
    if delta_api < 0 or delta_api > 1:
        raise NotImplementedError(
            "This module does not support registration of DBAPI services with a specified apilevel of %s"
            % module.apilevel
        )
    if mod_paramstyle not in ['pyformat', 'format', 'qmark']:
        raise NotImplementedError(
            "This module only supports registration of DBAPI services with a 'format' or 'pyformat' 'qmark' paramstyle, not %r"
            % mod_paramstyle
        )
    if mod_threadsafety < any_threadsafety:
        raise NotImplementedError(
            "This module does not support registration of DBAPI services of threadsafety %d (more generally under %d)"
            % (mod_threadsafety, any_threadsafety)
        )
    __uri_create_methods[uri_scheme] = (
        create_method,
        module,
        c14n_uri_method,
        escape,
        cast,
    )


def _get_methods_by_uri(sqluri):
    uri_scheme = parse.urlsplit(sqluri)[0]
    if uri_scheme not in __uri_create_methods:
        raise NotImplementedError('Unknown URI scheme "%s"' % str(uri_scheme))
    return __uri_create_methods[uri_scheme]


def connect_by_uri(sqluri):
    """
    Same purpose as the classical DBAPI v2.0 connect constructor, but
    with a unique prototype and routing the request to a registred method
    for this uri. It is not the responsibility of this anysql module to
    load any backend SQL implementation, so be sure the application has
    imported the correct one before calling this constructor.

    If no handler is found for this uri method, a NotImplementedError
    will be raised.

    A malformed URI will result in an exception being raised by the
    supporting URI parsing module.
    """
    return connection(sqluri)


def c14n_uri(sqluri):
    """
    Ask the backend to c14n the uri. See register_uri_backend() for
    details.

    If no backend is found for this uri method, a NotImplementedError
    will be raised.
    """
    uri_c14n_method = _get_methods_by_uri(sqluri)[METHOD_C14N_URI]
    if not uri_c14n_method:
        return sqluri
    return uri_c14n_method(sqluri)


__all__ = [
    "register_uri_backend",
    "connect_by_uri",
    "c14n_uri",
    "cursor",
    "connection",
    "any_paramstyle",
    "any_threadsafety",
    "any_apilevel",
]

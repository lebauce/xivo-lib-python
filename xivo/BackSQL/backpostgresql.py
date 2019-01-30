# -*- coding: utf-8 -*-
# Copyright (C) 2007-2016 Avencall
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import print_function

"""Backend support for PostgreSQL for anysql

Copyright (C) 2010  Avencall

"""

__version__ = "$Revision$ $Date$"

import psycopg2
import psycopg2.extensions
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

from xivo import anysql
from xivo import urisup
from xivo.urisup import SCHEME, AUTHORITY, PATH, QUERY, FRAGMENT, uri_help_split

__typemap = {
    "host": str,
    "user": str,
    "passwd": str,
    "db": str,
    "port": int,
    "unix_socket": str,
    "compress": bool,
    "connect_timeout": int,
    "read_default_file": str,
    "read_default_group": str,
    "use_unicode": (lambda x: bool(int(x))),
    "conv": None,
    "quote_conv": None,
    "cursorclass": None,
    "charset": str,
}

def __apply_types(params, typemap):
    for k in typemap.iterkeys():
        if k in params:
            if typemap[k] is not None:
                params[k] = typemap[k](params[k])
            else:
                del params[k]

def __dict_from_query(query):
    print("dfQ=",query)
    if not query:
        return {}
    return dict(query)

def connect_by_uri(uri):
    """General URI syntax:

    postgresql://user:passwd@host:port/db

    NOTE: the authority and the path parts of the URI have precedence
    over the query part, if an argument is given in both.

        conv,quote_conv,cursorclass
    are not (yet?) allowed as complex Python objects are needed, hard to
    transmit within an URI...
    """
    puri   = urisup.uri_help_split(uri)
		#params = __dict_from_query(puri[QUERY])
    params = {}

    if puri[AUTHORITY]:
        user, passwd, host, port = puri[AUTHORITY]
        if user:
            params['user'] = user
        if passwd:
            params['password'] = passwd
        if host:
            params['host'] = host
        if port:
            params['port'] = port
    if puri[PATH]:
        params['database'] = puri[PATH]
        if params['database'] and params['database'][0] == '/':
            params['database'] = params['database'][1:]

    #__apply_types(params, __typemap)

    return psycopg2.connect(**params)

def escape(s):
    return '.'.join(['"%s"' % comp for comp in s.split('.')])

def cast(fieldname, type):
    return "%s::%s" % (fieldname, type)


anysql.register_uri_backend('postgresql', connect_by_uri, psycopg2, None, escape, cast)

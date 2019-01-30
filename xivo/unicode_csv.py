# -*- coding: utf-8 -*-
# Copyright (C) 2013-2016 Avencall
# SPDX-License-Identifier: GPL-3.0-or-later

import csv

import six


# The CSV lib always yields binary data; we will only use Unicode down the
# chain and would prefer any invalid data to be caught ASAP. Therefore, we
# define a thin wrapper around DictReader so that binary data won't touch the
# rest of our code.
#
# Note that we still use bytes as *input* to the CSV parser.

class UnicodeDictReader(csv.DictReader):

    def __init__(self, *args, **kwargs):
        self._encoding = kwargs.pop('encoding', 'utf-8')
        csv.DictReader.__init__(self, *args, **kwargs)

    @property
    def fieldnames(self):
        return [field.decode(self._encoding)
                for field in csv.DictReader.fieldnames.fget(self)]

    def next(self):
        next = csv.DictReader.next(self).items()
        return dict((key, self._deep_decode(val))
                    for (key, val) in next)

    def _deep_decode(self, value):
        if hasattr(value, 'decode'):
            return value.decode(self._encoding)
        try:
            iter(value)
        except TypeError:
            return value
        else:
            return [self._deep_decode(item) for item in value]


class UnicodeDictWriter(csv.DictWriter):

    def __init__(self, *args, **kwargs):
        self._encoding = kwargs.pop('encoding', 'utf-8')
        csv.DictWriter.__init__(self, *args, **kwargs)

    def writerow(self, row):
        csv.DictWriter.writerow(self, dict((key, unicode(val).encode(self._encoding)) for (key, val) in row.iteritems()))

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


if six.PY3:
    UnicodeDictReader = csv.DictReader
    UnicodeDictWriter = csv.DictWriter

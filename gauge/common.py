# -*- coding: utf-8 -*-
"""
    gauge.common
    ~~~~~~~~~~~~

    The common components such as constants or utility functions.

    :copyright: (c) 2013-2014 by What! Studio
    :license: BSD, see LICENSE for more details.
"""
from time import time as now
import warnings


__all__ = ['ADD', 'REMOVE', 'TIME', 'VALUE', 'inf', 'now_or', 'deprecate']


# events
ADD = +1
REMOVE = -1


# indices
TIME = 0
VALUE = 1


inf = float('inf')


def now_or(time):
    """Returns the current time if `time` is ``None``."""
    return now() if time is None else float(time)


def deprecate(message, *args, **kwargs):
    warnings.warn(DeprecationWarning(message.format(*args, **kwargs)))
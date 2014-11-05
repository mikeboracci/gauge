# -*- coding: utf-8 -*-
"""
    gauge
    ~~~~~

    Deterministic linear gauge library.

    :copyright: (c) 2013-2014 by What! Studio
    :license: BSD, see LICENSE for more details.

"""
from bisect import bisect_left
from collections import namedtuple
import operator
from time import time as now
import warnings
import weakref

from sortedcontainers import SortedList, SortedListWithKey


__all__ = ['Gauge', 'Momentum']
__version__ = '0.1.6'


# indices
TIME = 0
VALUE = 1

# events
ADD = +1
REMOVE = -1


inf = float('inf')


def deprecate(message, *args, **kwargs):
    warnings.warn(DeprecationWarning(message.format(*args, **kwargs)))


def now_or(time):
    """Returns the current time if `time` is ``None``."""
    return now() if time is None else float(time)


class Gauge(object):
    """Represents a gauge.  A gauge has a value at any moment.  It can be
    modified by an user's adjustment or an effective momentum.
    """

    #: The base time and value.
    base = (None, 0)

    #: A sorted list of momenta.  The items are :class:`Momentum` objects.
    momenta = None

    def __init__(self, value, max, min=0, at=None):
        at = now_or(at)
        self.base = (at, value)
        self.momenta = SortedListWithKey(key=lambda m: m[2])  # sort by until
        self.set_max(max, at=at)
        self.set_min(min, at=at)
        self._events = SortedList()
        self._links = set()

    @property
    def determination(self):
        """The cached determination.  If there's no the cache, it redetermines
        and caches that.

        A determination is a sorted list of 2-dimensional points which take
        times as x-values, gauge values as y-values.
        """
        try:
            return self._determination
        except AttributeError:
            pass
        # redetermine and cache.
        self._determination = []
        prev_time = None
        for time, value in self.determine():
            if prev_time == time:
                continue
            self._determination.append((time, value))
            prev_time = time
        return self._determination

    def invalidate(self):
        """Invalidates the cached determination.  If you touches the
        determination at the next first time, that will be redetermined.

        You don't need to call this method because all mutating methods such as
        :meth:`incr` or :meth:`add_momentum` calls it.
        """
        # invalidate linked gauges together.  A linked gauge refers this gauge
        # as a limit.
        try:
            links = list(self._links)
        except AttributeError:
            pass
        else:
            for gauge_ref in links:
                gauge = gauge_ref()
                if gauge is None:
                    # the gauge has gone away
                    self._links.remove(gauge_ref)
                    continue
                gauge.invalidate()
        # remove the cached determination.
        try:
            del self._determination
        except AttributeError:
            pass

    @property
    def max(self):
        return self._max

    @max.setter
    def max(self, max):
        self.set_max(max)

    @property
    def min(self):
        return self._min

    @min.setter
    def min(self, min):
        self.set_min(min)

    def _get_limit(self, limit, at=None):
        if isinstance(limit, Gauge):
            return limit.get(at)
        else:
            return limit

    def get_max(self, at=None):
        """Predicts the current maximum value."""
        return self._get_limit(self.max, at=at)

    def get_min(self, at=None):
        """Predicts the current minimum value."""
        return self._get_limit(self.min, at=at)

    def _set_limits(self, max=None, min=None, clamp=False, at=None):
        for limit, attr in [(max, '_max'), (min, '_min')]:
            if limit is None:
                continue
            try:
                prev_limit = getattr(self, attr)
            except AttributeError:
                pass
            else:
                if isinstance(prev_limit, Gauge):
                    # unlink this gauge from the previous limiting gauge.
                    prev_limit._links.discard(weakref.ref(self))
            if isinstance(limit, Gauge):
                # link this gauge to the new limiting gauge.
                limit._links.add(weakref.ref(self))
            # set the internal attribute.
            setattr(self, attr, limit)
        if clamp:
            # clamp the current value.
            at = now_or(at)
            value = self.get(at=at)
            max_ = value if max is None else self.get_max(at=at)
            min_ = value if min is None else self.get_min(at=at)
            if value > max_:
                limited = max_
            elif value < min_:
                limited = min_
            else:
                limited = None
            if limited is not None:
                self.forget_past(limited, at=at)
                # :meth:`forget_past` calls :meth:`invalidate`.
                return
        self.invalidate()

    def set_max(self, max, clamp=False, at=None):
        """Changes the maximum.

        :param max: a number or gauge to set as the maximum.
        :param clamp: limits the current value to be below the new maximum.
                      (default: ``True``)
        :param at: the time to change.  (default: now)
        """
        self._set_limits(max=max, clamp=clamp, at=at)

    def set_min(self, min, clamp=False, at=None):
        """Changes the minimum.

        :param min: a number or gauge to set as the minimum.
        :param clamp: limits the current value to be above the new minimum.
                      (default: ``True``)
        :param at: the time to change.  (default: now)
        """
        self._set_limits(min=min, clamp=clamp, at=at)

    def clamp(self, value, at=None):
        """Clamps by the limits at the given time.

        :param at: the time to get limits.  (default: now)
        """
        at = now_or(at)
        max = self.get_max(at)
        if value > max:
            return max
        min = self.get_min(at)
        if value < min:
            return min
        return value

    def _value_and_velocity(self, at=None):
        at = now_or(at)
        determination = self.determination
        if len(determination) == 1:
            # skip bisect_left() because it is expensive
            x = 0
        else:
            x = bisect_left(determination, (at,))
        if x == 0:
            return (determination[0][VALUE], 0.)
        try:
            until, final = determination[x]
        except IndexError:
            return (determination[-1][VALUE], 0.)
        since, value = determination[x - 1]
        seg = Segment(since, until, value, final)
        value, velocity = seg.get(at), seg.velocity
        # if inside:
        #     value = self.clamp(value, at=at)
        return (value, velocity)

    def get(self, at=None):
        """Predicts the current value.

        :param at: the time to observe.  (default: now)
        """
        value, velocity = self._value_and_velocity(at)
        return value

    def velocity(self, at=None):
        """Predicts the current velocity.

        :param at: the time to observe.  (default: now)
        """
        value, velocity = self._value_and_velocity(at)
        return velocity

    def incr(self, delta, over=False, clamp=False, at=None):
        """Increases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to increase.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to increase.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        prev_value = self.get(at=at)
        value = prev_value + delta
        max_, min_ = self.get_max(at), self.get_min(at)
        if over:
            pass
        elif clamp:
            if delta > 0 and value > max_:
                value = max(prev_value, max_)
            elif delta < 0 and value < min_:
                value = min(prev_value, min_)
        else:
            if delta > 0 and value > max_:
                raise ValueError('The value to set is bigger than the '
                                 'maximum ({0} > {1})'.format(value, max_))
            elif delta < 0 and value < min_:
                raise ValueError('The value to set is smaller than the '
                                 'minimum ({0} < {1})'.format(value, min_))
        self.forget_past(value, at=at)
        return value

    def decr(self, delta, over=False, clamp=False, at=None):
        """Decreases the value by the given delta immediately.  The
        determination would be changed.

        :param delta: the value to decrease.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to decrease.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        return self.incr(-delta, over=over, clamp=clamp, at=at)

    def set(self, value, over=False, clamp=False, at=None):
        """Sets the current value immediately.  The determination would be
        changed.

        :param value: the value to set.
        :param limit: checks if the value is in the range.  (default: ``True``)
        :param at: the time to set.  (default: now)

        :raises ValueError: the value is out of the range.
        """
        at = now_or(at)
        delta = value - self.get(at=at)
        return self.incr(delta, over=over, clamp=clamp, at=at)

    def when(self, value, after=0):
        """When the gauge reaches to the goal value.

        :param value: the goal value.
        :param after: take (n+1)th time.  (default: 0)

        :raises ValueError: the gauge will not reach to the goal value.
        """
        x = 0
        for x, at in enumerate(self.whenever(value)):
            if x == after:
                return at
        form = 'The gauge will not reach to {0}' + \
               (' more than {1} times' if x else '')
        raise ValueError(form.format(value, x))

    def whenever(self, value):
        """Yields multiple times when the gauge reaches to the goal value.

        :param value: the goal value.
        """
        if self.determination:
            determination = self.determination
            first_time, first_value = determination[0]
            if first_value == value:
                yield first_time
            zipped_determination = zip(determination[:-1], determination[1:])
            for node1, node2 in zipped_determination:
                time1, value1 = node1
                time2, value2 = node2
                if not (value1 < value <= value2 or value1 > value >= value2):
                    continue
                ratio = (value - value1) / float(value2 - value1)
                yield (time1 + (time2 - time1) * ratio)

    def _make_momentum(self, velocity_or_momentum, since=None, until=None):
        """Makes a :class:`Momentum` object by the given arguments.

        Override this if you want to use your own momentum class.

        :param velocity_or_momentum: a :class:`Momentum` object or just a
                                     number for the velocity.
        :param since: if the first argument is a velocity, it is the time to
                      start to affect the momentum.  (default: ``-inf``)
        :param until: if the first argument is a velocity, it is the time to
                      finish to affect the momentum.  (default: ``+inf``)

        :raises ValueError: `since` later than or same with `until`.
        :raises TypeError: the first argument is a momentum, but other
                           arguments passed.
        """
        if isinstance(velocity_or_momentum, Momentum):
            if not (since is until is None):
                raise TypeError('Arguments behind the first argument as a '
                                'momentum should be None')
            momentum = velocity_or_momentum
        else:
            velocity = velocity_or_momentum
            if since is None:
                since = -inf
            if until is None:
                until = +inf
            momentum = Momentum(velocity, since, until)
        since, until = momentum.since, momentum.until
        if since == -inf or until == +inf or since < until:
            pass
        else:
            raise ValueError('\'since\' should be earlier than \'until\'')
        return momentum

    def add_momentum(self, *args, **kwargs):
        """Adds a momentum.  A momentum includes the velocity and the times to
        start to affect and to stop to affect.  The determination would be
        changed.

        All arguments will be passed to :meth:`_make_momentum`.

        :returns: a momentum object.  Use this to remove the momentum by
                  :meth:`remove_momentum`.

        :raises ValueError: `since` later than or same with `until`.
        """
        momentum = self._make_momentum(*args, **kwargs)
        since, until = momentum.since, momentum.until
        self.momenta.add(momentum)
        self._events.add((since, ADD, momentum))
        if until != +inf:
            self._events.add((until, REMOVE, momentum))
        self.invalidate()
        return momentum

    def remove_momentum(self, *args, **kwargs):
        """Removes the given momentum.  The determination would be changed.

        All arguments will be passed to :meth:`_make_momentum`.

        :raises ValueError: the given momentum not in the gauge.
        """
        momentum = self._make_momentum(*args, **kwargs)
        try:
            self.momenta.remove(momentum)
        except ValueError:
            raise ValueError('{0} not in the gauge'.format(momentum))
        self.invalidate()

    def _coerce_and_remove_momenta(self, value=None, at=None,
                                   start=None, stop=None):
        """Coerces to set the value and removes the momenta between indexes of
        ``start`` and ``stop``.

        :param value: the value to set coercively.  (default: the current
                      value)
        :param at: the time to set.  (default: now)
        :param start: the starting index of momentum removal.
                      (default: the first)
        :param stop: the stopping index of momentum removal.
                     (default: the last)
        """
        at = now_or(at)
        if value is None:
            value = self.get(at=at)
        self.base = (at, value)
        del self.momenta[start:stop]
        self.invalidate()
        return value

    def clear_momenta(self, value=None, at=None):
        """Removes all momenta.  The value is set as the current value.  The
        determination would be changed.

        :param value: the value to set coercively.
        :param at: the time base.  (default: now)
        """
        return self._coerce_and_remove_momenta(value, at)

    def forget_past(self, value=None, at=None):
        """Discards the momenta which doesn't effect anymore.

        :param value: the value to set coercively.
        :param at: the time base.  (default: now)
        """
        at = now_or(at)
        start = self.momenta.bisect_right((+inf, +inf, -inf))
        stop = self.momenta.bisect_left((-inf, -inf, at))
        return self._coerce_and_remove_momenta(value, at, start, stop)

    def walk_events(self):
        """Yields momentum adding and removing events.  An event is a tuple of
        ``(time, ADD|REMOVE, momentum)``.
        """
        yield (self.base[TIME], None, None)
        for time, method, momentum in list(self._events):
            if momentum not in self.momenta:
                self._events.remove((time, method, momentum))
                continue
            yield time, method, momentum
        yield (+inf, None, None)

    def walk_lines(self, number_or_gauge):
        """Yields :class:`Line`s on the graph from `number_or_gauge`.  If
        `number_or_gauge` is a gauge, the graph is the determination of the
        gauge.  Otherwise, just a Horizon line which has the number as the
        Y-intercept.
        """
        if isinstance(number_or_gauge, Gauge):
            determination = number_or_gauge.determination
            first, last = determination[0], determination[-1]
            if self.base[TIME] < first[TIME]:
                yield Horizon(self.base[TIME], first[TIME], first[VALUE])
            zipped_determination = zip(determination[:-1], determination[1:])
            for node1, node2 in zipped_determination:
                time1, value1 = node1
                time2, value2 = node2
                yield Segment(time1, time2, value1, value2)
            yield Horizon(last[TIME], +inf, last[VALUE])
        else:
            # just a number.
            value = number_or_gauge
            yield Horizon(self.base[TIME], +inf, value)

    def determine(self):
        """Determines the transformations from the time when the value set to
        the farthest future.
        """
        since, value = self.base
        velocity, velocities = 0, []
        bound, overlapped = None, False
        # boundaries.
        ceil = Boundary(self.walk_lines(self.max), operator.lt)
        floor = Boundary(self.walk_lines(self.min), operator.gt)
        boundaries = [ceil, floor]
        for boundary in boundaries:
            # skip past boundaries.
            while boundary.line.until <= since:
                boundary.walk()
            # check overflowing.
            if bound is not None:
                continue
            boundary_value = boundary.line.guess(since)
            if boundary.cmp(boundary_value, value):
                bound, overlapped = boundary, False
        for time, method, momentum in self.walk_events():
            # normalize time.
            until = max(time, self.base[TIME])
            # if True, An iteration doesn't choose next boundaries.  The first
            # iteration doesn't require to choose next boundaries.
            again = True
            while since < until:
                if again:
                    again = False
                    walked_boundaries = boundaries
                else:
                    # stop the loop if all boundaries have been proceeded.
                    if all(b.line.until >= until for b in boundaries):
                        break
                    # choose the next boundary.
                    boundary = min(boundaries, key=lambda b: b.line.until)
                    boundary.walk()
                    walked_boundaries = [boundary]
                # calculate velocity.
                if bound is None:
                    velocity = sum(velocities)
                elif overlapped:
                    velocity = bound.best(sum(velocities), bound.line.velocity)
                else:
                    velocity = sum(v for v in velocities if bound.cmp(v, 0))
                # is still bound?
                if overlapped and bound.cmp(velocity, bound.line.velocity):
                    bound, overlapped = None, False
                    again = True
                    continue
                # current value line.
                line = Ray(since, until, value, velocity)
                if overlapped:
                    bound_until = min(bound.line.until, until)
                    if bound_until == +inf:
                        break
                    # released from the boundary.
                    since, value = (bound_until, bound.line.get(bound_until))
                    yield (since, value)  # , True)
                    continue
                for boundary in walked_boundaries:
                    # find the intersection with a boundary.
                    try:
                        intersection = line.intersect(boundary.line)
                    except ValueError:
                        continue
                    if intersection[TIME] == since:
                        continue
                    again = True  # iterate with same boundaries again.
                    bound, overlapped = boundary, True
                    since, value = intersection
                    # clamp by the boundary.
                    value = boundary.best(value, boundary.line.guess(since))
                    yield (since, value)  # , True)
                    break
                if bound is not None:
                    continue  # the intersection was found.
                for boundary in walked_boundaries:
                    # find missing intersection caused by floating-point
                    # inaccuracy.
                    bound_until = min(boundary.line.until, until)
                    if bound_until == +inf or bound_until < since:
                        continue
                    boundary_value = boundary.line.get(bound_until)
                    if boundary.cmp_eq(line.get(bound_until), boundary_value):
                        continue
                    bound, overlapped = boundary, True
                    since, value = bound_until, boundary_value
                    yield (since, value)  # , True)
                    break
            if until == +inf:
                break
            # determine the final node in the current itreration.
            value += velocity * (until - since)
            yield (until, value)  # , boundary is None or overlapped)
            # prepare the next iteration.
            if method == ADD:
                velocities.append(momentum.velocity)
            elif method == REMOVE:
                velocities.remove(momentum.velocity)
            since = until

    def __getstate__(self):
        momenta = list(map(tuple, self.momenta))
        return (self.base, self._max, self._min, momenta)

    def __setstate__(self, state):
        base, max, min, momenta = state
        self.__init__(base[VALUE], max=max, min=min, at=base[TIME])
        for momentum in momenta:
            self.add_momentum(*momentum)

    def __repr__(self, at=None):
        """Example strings:

        - ``<Gauge 0.00/2.00>``
        - ``<Gauge 0.00 between 1.00~2.00>``
        - ``<Gauge 0.00 between <Gauge 0.00/2.00>~<Gauge 2.00/2.00>>``

        """
        at = now_or(at)
        value = self.get(at=at)
        hyper = False
        limit_reprs = []
        for limit in [self.max, self.min]:
            if isinstance(limit, Gauge):
                hyper = True
                limit_reprs.append('{0!r}'.format(limit))
            else:
                limit_reprs.append('{0:.2f}'.format(limit))
        form = '<{0} {1:.2f}'
        if not hyper and self.min == 0:
            form += '/{2}>'
        else:
            form += ' between {3}~{2}>'
        return form.format(type(self).__name__, value, *limit_reprs)

    # deprecated features

    @property
    def set_at(self):
        # deprecated since v0.1.0
        deprecate('Get Gauge.base[0] instead')
        return self.base[TIME]

    @set_at.setter
    def set_at(self, time):
        # deprecated since v0.1.0
        deprecate('Update Gauge.base instead')
        self.base = (time, self.base[VALUE])

    @property
    def value(self):
        # deprecated since v0.1.0
        deprecate('Get Gauge.base[1] instead')
        return self.base[VALUE]

    @value.setter
    def value(self, value):
        # deprecated since v0.1.0
        deprecate('Update Gauge.base instead')
        self.base = (self.base[TIME], value)

    def current(self, at=None):
        # deprecated since v0.0.5
        deprecate('Use Gauge.get() instead')
        return self.get(at=at)

    current.__doc__ = get.__doc__


class Momentum(namedtuple('Momentum', ['velocity', 'since', 'until'])):
    """A power of which increases or decreases the gauge continually between a
    specific period.
    """

    def __new__(cls, velocity, since=-inf, until=+inf):
        velocity = float(velocity)
        return super(Momentum, cls).__new__(cls, velocity, since, until)

    def __repr__(self):
        string = '<{0} {1:+.2f}/s'.format(type(self).__name__, self.velocity)
        if self.since != -inf or self.until != +inf:
            string += ' ' + '~'.join([
                '' if self.since == -inf else '{0:.2f}'.format(self.since),
                '' if self.until == +inf else '{0:.2f}'.format(self.until)])
        string += '>'
        return string


class Line(object):
    """An abstract class to represent lines between 2 times which start from
    `value`.  Subclasses should describe where lines end.

    .. note::

       Each subclass must implement :meth:`_get`, :meth:`_earlier`,
       :meth:`_later`, and :attr:`velocity` property.

    """

    since = None
    until = None
    value = None

    velocity = NotImplemented

    def __init__(self, since, until, value):
        self.since = since
        self.until = until
        self.value = value

    def get(self, at=None):
        """Returns the value at the given time.

        :raises ValueError: the given time is out of the time range.
        """
        at = now_or(at)
        if not self.since <= at <= self.until:
            raise ValueError('Out of the time range: {0:.2f}~{1:.2f}'
                             ''.format(self.since, self.until))
        return self._get(at)

    def guess(self, at=None):
        """Returns the value at the given time even the time it out of the time
        range.
        """
        at = now_or(at)
        if at < self.since:
            return self._earlier(at)
        elif at > self.until:
            return self._later(at)
        else:
            return self.get(at)

    def _get(self, at):
        """Implement at subclass as to calculate the value at the given time
        which is between the time range.
        """
        raise NotImplementedError

    def _earlier(self, at):
        """Implement at subclass as to calculate the value at the given time
        which is earlier than `since`.
        """
        raise NotImplementedError

    def _later(self, at):
        """Implement at subclass as to calculate the value at the given time
        which is later than `until`.
        """
        raise NotImplementedError

    def intersect(self, line):
        """Gets the intersection with the given line.

        :raises ValueError: there's no intersection.
        """
        intercept_delta = line.intercept() - self.intercept()
        velocity_delta = self.velocity - line.velocity
        try:
            time = intercept_delta / velocity_delta
        except ZeroDivisionError:
            raise ValueError('Parallel line given')
        since = max(self.since, line.since)
        until = min(self.until, line.until)
        if since <= time <= until:
            pass
        else:
            raise ValueError('Intersection not in the time range')
        value = self.get(time)
        return (time, value)

    def intercept(self):
        """Gets the value-intercept. (Y-intercept)"""
        return self.value - self.velocity * self.since


class Horizon(Line):
    """A line which has no velocity."""

    velocity = 0

    def _get(self, at):
        return self.value

    def _earlier(self, at):
        return self.value

    def _later(self, at):
        return self.value


class Ray(Line):
    """A line based on starting value and velocity."""

    velocity = None

    def __init__(self, since, until, value, velocity):
        super(Ray, self).__init__(since, until, value)
        self.velocity = velocity

    def _get(self, at):
        return self.value + self.velocity * (at - self.since)

    def _earlier(self, at):
        return self.value

    def _later(self, at):
        return self._get(self.until)


class Segment(Line):
    """A line based on starting and ending value."""

    #: The value at `until`.
    final = None

    @property
    def velocity(self):
        value_delta = self.final - self.value
        time_delta = self.until - self.since
        return value_delta / time_delta

    def __init__(self, since, until, value, final):
        super(Segment, self).__init__(since, until, value)
        self.final = final

    def _get(self, at):
        if at == self.since:
            # rate: 0
            return self.value
        elif at == self.until:
            # rate: 1
            return self.final
        rate = float(at - self.since) / (self.until - self.since)
        return self.value + rate * (self.final - self.value)

    def _earlier(self, at):
        return self.value

    def _later(self, at):
        return self.final


class Boundary(object):

    #: The current line.  To select next line, call :meth:`walk`.
    line = None

    #: The iterator of lines.
    lines_iter = None

    #: Compares two values.  Choose one of `operator.lt` and `operator.gt`.
    cmp = None

    #: Returns the best value in an iterable or arguments.  It is indicated
    #: from :attr:`cmp` function.  `operator.lt` indicates :func:`min` and
    #: `operator.gt` indicates :func:`max`.
    best = None

    def __init__(self, lines_iter, cmp=operator.lt):
        assert cmp in [operator.lt, operator.gt]
        self.lines_iter = lines_iter
        self.cmp = cmp
        self.best = {operator.lt: min, operator.gt: max}[cmp]
        self.walk()

    def walk(self):
        """Choose the next line."""
        self.line = next(self.lines_iter)

    def cmp_eq(self, x, y):
        return x == y or self.cmp(x, y)

    def cmp_inv(self, x, y):
        return x != y and not self.cmp(x, y)

    def __repr__(self):
        return ('<{0} line={1}, cmp={2}>'
                ''.format(type(self).__name__, self.line, self.cmp))

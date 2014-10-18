# -*- coding: utf-8 -*-
from contextlib import contextmanager
import operator
import pickle
import time
import types

import pytest

import gauge
from gauge import Boundary, Gauge, Momentum, Segment, inf


@contextmanager
def t(timestamp):
    gauge.now = lambda: float(timestamp)
    try:
        yield
    finally:
        gauge.now = time.time


def round_determination(determination, precision=0):
    return [(round(time, precision), round(value, precision))
            for time, value in determination]


def test_deprecations():
    g = Gauge(0, 10, at=0)
    pytest.deprecated_call(g.current, 0)
    # removed since v0.1.0
    # pytest.deprecated_call(g.set, 0, limit=True)
    # pytest.deprecated_call(g.set_max, 0, limit=True)
    pytest.deprecated_call(Gauge.value.fget, g)
    pytest.deprecated_call(Gauge.value.fset, g, 10)
    pytest.deprecated_call(Gauge.set_at.fget, g)
    pytest.deprecated_call(Gauge.set_at.fset, g, 10)


def test_in_range():
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    assert list(g.determination) == [
        (0, 12), (1, 12), (3, 14), (6, 14), (8, 12)]


def test_over_max():
    g = Gauge(8, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    assert list(g.determination) == [(0, 8), (2, 10), (4, 10)]
    g = Gauge(12, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    assert list(g.determination) == [(0, 12), (2, 10), (4, 8)]
    g = Gauge(12, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    g.add_momentum(-2, since=0, until=4)
    assert list(g.determination) == [(0, 12), (1, 10), (4, 7)]
    g = Gauge(12, 10, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.add_momentum(+1, since=10, until=14)
    g.add_momentum(-1, since=13, until=16)
    assert list(g.determination) == [
        (0, 12), (1, 12), (3, 12), (5, 10), (6, 10), (8, 8),
        (10, 8), (12, 10), (13, 10), (14, 10), (16, 8)]


def test_under_min():
    g = Gauge(2, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    assert list(g.determination) == [(0, 2), (2, 0), (4, 0)]
    g = Gauge(-2, 10, at=0)
    g.add_momentum(+1, since=0, until=4)
    assert list(g.determination) == [(0, -2), (2, 0), (4, 2)]
    g = Gauge(-2, 10, at=0)
    g.add_momentum(-1, since=0, until=4)
    g.add_momentum(+2, since=0, until=4)
    assert list(g.determination) == [(0, -2), (1, 0), (4, 3)]
    g = Gauge(-2, 10, at=0)
    g.add_momentum(-1, since=1, until=6)
    g.add_momentum(+1, since=3, until=8)
    g.add_momentum(-1, since=10, until=14)
    g.add_momentum(+1, since=13, until=16)
    assert list(g.determination) == [
        (0, -2), (1, -2), (3, -2), (5, 0), (6, 0), (8, 2),
        (10, 2), (12, 0), (13, 0), (14, 0), (16, 2)]


def test_permanent():
    g = Gauge(10, 10, at=0)
    g.add_momentum(-1)
    assert list(g.determination) == [(0, 10), (10, 0)]
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    assert list(g.determination) == [(0, 0), (10, 10)]
    g = Gauge(12, 10, at=0)
    g.add_momentum(-1)
    assert list(g.determination) == [(0, 12), (2, 10), (12, 0)]
    g = Gauge(5, 10, at=0)
    g.add_momentum(+1, since=3)
    assert list(g.determination) == [(0, 5), (3, 5), (8, 10)]
    g = Gauge(5, 10, at=0)
    g.add_momentum(+1, until=8)
    assert list(g.determination) == [(0, 5), (5, 10), (8, 10)]


def test_life():
    with t(0):
        life = Gauge(100, 100)
        life.add_momentum(-1)
        assert life.get() == 100
    with t(1):
        assert life.get() == 99
    with t(2):
        assert life.get() == 98
    with t(10):
        assert life.get() == 90
        life.incr(1)
        assert life.get() == 91
    with t(11):
        assert life.get() == 90


def test_no_momentum():
    g = Gauge(1, 10, at=0)
    assert list(g.determination) == [(0, 1)]
    assert g.get() == 1


def test_over():
    g = Gauge(1, 10)
    with pytest.raises(ValueError):
        g.set(11)
    with pytest.raises(ValueError):
        g.incr(100)
    with pytest.raises(ValueError):
        g.decr(100)
    g.set(10)
    assert g.get() == 10
    g.set(11, over=True)
    assert g.get() == 11


def test_clamp():
    g = Gauge(1, 10)
    g.set(11, clamp=True)
    assert g.get() == 10
    g.incr(100, clamp=True)
    assert g.get() == 10
    g.decr(100, clamp=True)
    assert g.get() == 0
    g.incr(3, clamp=True)
    assert g.get() == 3
    g.decr(1, clamp=True)
    assert g.get() == 2
    g.set(100, over=True)
    g.incr(3, clamp=True)
    assert g.get() == 100
    g.decr(3, clamp=True)
    assert g.get() == 97


def test_set_min_max():
    # without momentum
    g = Gauge(5, 10)
    assert g.max == 10
    assert g.min == 0
    assert g.get() == 5
    g.max = 100
    g.min = 10
    assert g.max == 100
    assert g.min == 10
    assert g.get() == 5
    g.set_min(10, clamp=True)
    assert g.get() == 10
    g.set_min(5, clamp=True)  # to test meaningless clamping
    assert g.get() == 10
    g.min = 0
    g.max = 5
    assert g.max == 5
    assert g.min == 0
    assert g.get() == 10
    g.set_max(5, clamp=True)
    assert g.get() == 5
    # with momentum
    g = Gauge(5, 10, at=0)
    g.add_momentum(+1)
    assert list(g.determination) == [(0, 5), (5, 10)]
    g.set_max(50, at=0)
    assert list(g.determination) == [(0, 5), (45, 50)]
    g.set_min(40, clamp=True, at=0)
    assert list(g.determination) == [(0, 40), (10, 50)]


def test_pickle():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1, since=0)
    g.add_momentum(-2, since=5, until=7)
    assert list(g.determination) == [(0, 0), (5, 5), (7, 3), (14, 10)]
    data = pickle.dumps(g)
    g2 = pickle.loads(data)
    assert list(g2.determination) == [(0, 0), (5, 5), (7, 3), (14, 10)]


def test_make_momentum():
    g = Gauge(0, 10, at=0)
    m = g.add_momentum(+1)
    assert isinstance(m, Momentum)
    with pytest.raises(TypeError):
        g.add_momentum(m, since=1)
    with pytest.raises(TypeError):
        g.add_momentum(m, until=2)


def test_clear_momenta():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    g.clear_momenta(at=5)
    assert g.get(5) == 5
    assert list(g.determination) == [(5, 5)]
    # clear momenta when the value is out of the range
    g.add_momentum(+1)
    g.set(15, over=True, at=10)
    g.clear_momenta(at=10)
    assert g.get(10) == 15
    assert list(g.determination) == [(10, 15)]
    # coerce to set a value with Gauge.clear_momenta()
    g.clear_momenta(100)
    assert g.get() == 100


def test_when():
    g = Gauge(0, 10, at=0)
    assert g.when(0) == 0
    with pytest.raises(ValueError):
        g.when(10)
    g.add_momentum(+1)
    assert g.when(10) == 10
    g.add_momentum(+1, since=3, until=5)
    assert g.when(10) == 8
    g.add_momentum(-2, since=4, until=8)
    assert g.when(0) == 0
    assert g.when(1) == 1
    assert g.when(2) == 2
    assert g.when(3) == 3
    assert g.when(4) == 3.5
    assert g.when(5) == 4
    assert g.when(6) == 12
    assert g.when(7) == 13
    assert g.when(8) == 14
    assert g.when(9) == 15
    assert g.when(10) == 16
    with pytest.raises(ValueError):
        g.when(11)


def test_whenever():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    g.add_momentum(-2, since=3, until=4)
    g.add_momentum(-2, since=5, until=6)
    g.add_momentum(-2, since=7, until=8)
    assert g.when(3) == 3
    assert g.when(3, after=1) == 5
    assert g.when(3, after=2) == 7
    assert g.when(3, after=3) == 9
    with pytest.raises(ValueError):
        g.when(3, after=4)
    whenever = g.whenever(3)
    assert isinstance(whenever, types.GeneratorType)
    assert list(whenever) == [3, 5, 7, 9]
    # inverse
    g = Gauge(10, 10, at=0)
    g.add_momentum(-1)
    g.add_momentum(+2, since=3, until=4)
    g.add_momentum(+2, since=5, until=6)
    g.add_momentum(+2, since=7, until=8)
    assert g.when(7) == 3
    assert g.when(7, after=1) == 5


def test_since_gte_until():
    g = Gauge(0, 10, at=0)
    with pytest.raises(ValueError):
        g.add_momentum(+1, since=1, until=1)
    with pytest.raises(ValueError):
        g.add_momentum(+1, since=2, until=1)


def test_repr():
    g = Gauge(0, 10, at=0)
    assert repr(g) == '<Gauge 0.00/10.00>'
    g.set_min(-10, at=0)
    assert repr(g) == '<Gauge 0.00 between -10.00~10.00>'
    g.set_max(Gauge(10, 10), at=0)
    assert repr(g) == '<Gauge 0.00 between -10.00~<Gauge 10.00/10.00>>'
    m = Momentum(+100, since=10, until=20)
    assert repr(m) == '<Momentum +100.00/s 10.00~20.00>'


def test_case1():
    g = Gauge(0, 5, at=0)
    g.add_momentum(+1)
    g.add_momentum(-2, since=1, until=3)
    g.add_momentum(+1, since=5, until=7)
    assert list(g.determination) == [
        (0, 0), (1, 1), (2, 0), (3, 0), (5, 2), (6.5, 5), (7, 5)]


def test_case2():
    g = Gauge(12, 10, at=0)
    g.add_momentum(+2, since=2, until=10)
    g.add_momentum(-1, since=4, until=8)
    assert list(g.determination) == [
        (0, 12), (2, 12), (4, 12), (6, 10), (8, 10), (10, 10)]


def test_case3():
    g = Gauge(0, 10, at=0)
    assert g.get(0) == 0
    g.add_momentum(+1, since=0)
    assert g.get(10) == 10
    g.incr(3, over=True, at=11)
    assert g.get(11) == 13
    g.add_momentum(-1, since=13)
    assert g.get(13) == 13
    assert g.get(14) == 12
    assert g.get(15) == 11
    assert g.get(16) == 10
    assert g.get(17) == 10


def test_case4():
    g = Gauge(0, 10, at=0)
    g.add_momentum(+1)
    g.add_momentum(+1)
    assert list(g.determination) == [(0, 0), (5, 10)]


def test_remove_momentum():
    g = Gauge(0, 10, at=0)
    m1 = g.add_momentum(+1)
    m2 = g.add_momentum(Momentum(+1))
    g.add_momentum(+2, since=10)
    g.add_momentum(-3, until=100)
    assert len(g.momenta) == 4
    g.remove_momentum(m2)
    assert len(g.momenta) == 3
    assert m1 in g.momenta
    assert m2 in g.momenta
    g.remove_momentum(m2)
    assert len(g.momenta) == 2
    assert m1 not in g.momenta
    assert m2 not in g.momenta
    with pytest.raises(ValueError):
        g.remove_momentum(+2)
    g.remove_momentum(+2, since=10)
    assert len(g.momenta) == 1
    g.remove_momentum(Momentum(-3, until=100))
    assert not g.momenta


def test_momenta_order():
    g = Gauge(0, 50, at=0)
    g.add_momentum(+3, since=0, until=5)
    g.add_momentum(+2, since=1, until=4)
    g.add_momentum(+1, since=2, until=3)
    assert g.get(0) == 0
    assert g.get(1) == 3
    assert g.get(2) == 8
    assert g.get(3) == 14
    g.decr(1, at=3)
    assert g.get(3) == 13
    assert g.get(4) == 18
    assert g.get(5) == 21


def test_forget_past():
    g = Gauge(0, 50, at=0)
    g.add_momentum(+1, since=0, until=5)
    g.add_momentum(0, since=0)
    g.add_momentum(0, until=999)
    assert g.get(0) == 0
    assert g.get(1) == 1
    assert g.get(2) == 2
    assert g.get(3) == 3
    assert g.get(4) == 4
    assert g.get(5) == 5
    assert g.get(10) == 5
    assert g.get(20) == 5
    assert len(g.momenta) == 3
    g.forget_past(at=30)
    assert len(g.momenta) == 2


def test_extensibility_of_make_momentum():
    class MyGauge(Gauge):
        def _make_momentum(self, *args):
            args = args[::-1]
            return super(MyGauge, self)._make_momentum(*args)
    g = MyGauge(0, 10, at=0)
    m = g.add_momentum(3, 2, 1)
    assert m == (1, 2, 3)


def test_just_one_momentum():
    def gen_gauge(since=None, until=None):
        g = Gauge(5, 10, at=0)
        g.add_momentum(+0.1, since, until)
        return g
    # None ~ None
    g = gen_gauge()
    assert g.determination == [(0, 5), (50, 10)]
    # 0 ~ None
    g = gen_gauge(since=0)
    assert g.determination == [(0, 5), (50, 10)]
    # None ~ 100
    g = gen_gauge(until=100)
    assert g.determination == [(0, 5), (50, 10), (100, 10)]
    # 0 ~ 100
    g = gen_gauge(since=0, until=100)
    assert g.determination == [(0, 5), (50, 10), (100, 10)]
    # -100 ~ 100
    g = gen_gauge(since=-100, until=100)
    assert g.determination == [(0, 5), (50, 10), (100, 10)]


def test_segment():
    seg = Segment(0, +1, since=0, until=10)
    assert seg.get(0) == 0
    assert seg.get(5) == 5
    with pytest.raises(ValueError):
        seg.get(-1)
    with pytest.raises(ValueError):
        seg.get(11)
    assert seg.guess(-1) == 0
    assert seg.guess(11) == 10
    assert seg.intersect(Segment(5, 0, since=0, until=10)) == (5, 5)
    assert seg.intersect(Segment(10, 0, since=0, until=10)) == (10, 10)
    assert seg.intersect(Segment(5, 0, since=0, until=inf)) == (5, 5)
    with pytest.raises(ValueError):
        seg.intersect(Segment(15, 0, since=0, until=10))
    with pytest.raises(ValueError):
        seg.intersect(Segment(5, 0, since=6, until=10))
    with pytest.raises(ValueError):
        seg.intersect(Segment(5, 0, since=-inf, until=inf))
    seg = Segment(0, +1, since=0, until=inf)
    assert seg.get(100) == 100
    assert seg.get(100000) == 100000


def test_boundary():
    # walk
    segs = [Segment(0, 0, since=0, until=10),
            Segment(0, +1, since=10, until=20),
            Segment(10, -1, since=20, until=30)]
    boundary = Boundary(iter(segs))
    assert boundary.seg is segs[0]
    boundary.walk()
    assert boundary.seg is segs[1]
    boundary.walk()
    assert boundary.seg is segs[2]
    with pytest.raises(StopIteration):
        boundary.walk()
    # cmp
    assert boundary.cmp(1, 2)
    assert not boundary.cmp(2, 1)
    assert boundary.cmp_eq(1, 2)
    assert boundary.cmp_eq(1, 1)
    assert not boundary.cmp_eq(2, 1)
    assert boundary.cmp_inv(2, 1)
    assert not boundary.cmp_inv(1, 2)
    assert not boundary.cmp_inv(1, 1)
    # best
    zero_seg = Segment(0, 0, 0, 0)
    ceil = Boundary(iter([zero_seg]), operator.lt)
    floor = Boundary(iter([zero_seg]), operator.gt)
    assert ceil.best is min
    assert floor.best is max
    assert ceil.best_inv(xrange(10)) == 9
    assert floor.best_inv(xrange(10)) == 0


def test_hypergauge():
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    # case 1
    g.max = Gauge(15, 15, at=0)
    g.max.add_momentum(-1, until=5)
    assert g.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (5, 10), (6, 10), (8, 8)]
    assert g.max.determination == [(0, 15), (5, 10)]
    # case 2
    g.max = Gauge(15, 15, at=0)
    g.max.add_momentum(-1, until=4)
    g.max.add_momentum(+1, since=4, until=6)
    assert g.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (4, 11), (6, 11), (8, 9)]
    # case 3
    g.set_max(10, at=0)
    assert g.determination == [
        (0, 12), (1, 12), (3, 12), (5, 10), (6, 10), (8, 8)]
    g.set_max(Gauge(10, 100, at=0), at=0)
    assert g.determination == [
        (0, 12), (1, 12), (3, 12), (5, 10), (6, 10), (8, 8)]
    # case 4
    g.max = Gauge(15, 15, at=0)
    g.max.add_momentum(-1)
    assert g.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (6, 9), (8, 7), (15, 0)]
    # case 5
    ceil = Gauge(10, 10, at=0)
    ceil.add_momentum(-1, since=0, until=4)
    ceil.add_momentum(+1, since=6, until=7)
    floor = Gauge(0, 10, at=0)
    floor.add_momentum(+1, since=1, until=6)
    floor.add_momentum(-1, since=6, until=8)
    g = Gauge(5, ceil, floor, at=0)
    g.add_momentum(+1, since=0, until=3)
    g.add_momentum(-1, since=3, until=6)
    g.add_momentum(+1, since=6, until=9)
    g.add_momentum(-1, since=9, until=12)
    assert g.determination == [
        (0, 5), (2.5, 7.5), (3, 7), (4, 6), (5.5, 4.5), (6, 5), (8, 7),
        (9, 7), (12, 4)]
    # case 6: just one momentum
    g = Gauge(5, Gauge(5, 10, at=0), Gauge(5, 10, at=0), at=0)
    g.max.add_momentum(+1)
    g.min.add_momentum(-1)
    assert g.determination == [(0, 5)]
    g.add_momentum(+0.1, until=100)
    assert g.determination == [(0, 5), (50, 10), (100, 10)]


def test_zigzag_hypergauge():
    # case 1
    g = Gauge(1, Gauge(2, 3, 2, at=0), Gauge(1, 1, 0, at=0), at=0)
    for x in xrange(6):
        g.max.add_momentum(+1, since=x * 2, until=x * 2 + 1)
        g.max.add_momentum(-1, since=x * 2 + 1, until=x * 2 + 2)
        g.min.add_momentum(-1, since=x * 2, until=x * 2 + 1)
        g.min.add_momentum(+1, since=x * 2 + 1, until=x * 2 + 2)
    for x in xrange(3):
        t = sum(y * 2 for y in xrange(x + 1))
        g.add_momentum(+1, since=t, until=t + (x + 1))
        g.add_momentum(-1, since=t + (x + 1), until=t + 2 * (x + 1))
    assert g.determination == [
        (0, 1), (1, 2), (2, 1), (3.5, 2.5), (4, 2), (5.5, 0.5), (6, 1),
        (7.5, 2.5), (8, 2), (9, 3), (10, 2), (11.5, 0.5), (12, 1)]
    # case 2
    g = Gauge(2, Gauge(3, 5, 3, at=0), Gauge(2, 2, 0, at=0), at=0)
    for x in xrange(5):
        g.max.add_momentum(+1, since=x * 4, until=x * 4 + 2)
        g.max.add_momentum(-1, since=x * 4 + 2, until=x * 4 + 4)
        g.min.add_momentum(-1, since=x * 4, until=x * 4 + 2)
        g.min.add_momentum(+1, since=x * 4 + 2, until=x * 4 + 4)
    for x in xrange(4):
        t = sum(y * 2 for y in xrange(x + 1))
        g.add_momentum(+1, since=t, until=t + (x + 1))
        g.add_momentum(-1, since=t + (x + 1), until=t + 2 * (x + 1))
    assert g.determination == [
        (0, 2), (1, 3), (2, 2), (3.5, 3.5), (4, 3), (6, 1), (8, 3), (9, 4),
        (11.5, 1.5), (12, 2), (14.5, 4.5), (16, 3), (18.5, 0.5), (20, 2)]


def test_hyper_hypergauge():
    # same with a hyper-gauge in :func:`test_zigzag_hypergauge`.
    g = Gauge(1, Gauge(2, 3, 2, at=0), Gauge(1, 1, 0, at=0), at=0)
    for x in xrange(6):
        g.max.add_momentum(+1, since=x * 2, until=x * 2 + 1)
        g.max.add_momentum(-1, since=x * 2 + 1, until=x * 2 + 2)
        g.min.add_momentum(-1, since=x * 2, until=x * 2 + 1)
        g.min.add_momentum(+1, since=x * 2 + 1, until=x * 2 + 2)
    for x in xrange(3):
        t = sum(y * 2 for y in xrange(x + 1))
        g.add_momentum(+1, since=t, until=t + (x + 1))
        g.add_momentum(-1, since=t + (x + 1), until=t + 2 * (x + 1))
    # bug `g` is also a ceil of another gauge.
    gg = Gauge(1, g, at=0)
    gg.add_momentum(+0.5)
    assert round_determination(gg.determination, precision=2) == [
        (0, 1), (1.33, 1.67), (2, 1), (4, 2), (5.5, 0.5), (9.5, 2.5),
        (10, 2), (11.5, 0.5), (12.5, 1)]


def test_over_max_on_hypergauge():
    g = Gauge(1, Gauge(10, 20, at=0), at=0)
    g.max.add_momentum(+1)
    with pytest.raises(ValueError):
        g.set(20, at=0)
    g.set(20, at=0, over=True)
    assert g.get(at=0) == 20
    g.set(20, at=10)
    assert g.get(at=10) == 20
    assert g.get(at=0) == 20  # past was forgot


def test_pickle_hypergauge():
    # case 1 from :func:`test_hypergauge`.
    g = Gauge(12, 100, at=0)
    g.add_momentum(+1, since=1, until=6)
    g.add_momentum(-1, since=3, until=8)
    g.max = Gauge(15, 15, at=0)
    g.max.add_momentum(-1, until=5)
    assert g.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (5, 10), (6, 10), (8, 8)]
    assert g.max.determination == [(0, 15), (5, 10)]
    data = pickle.dumps(g)
    g2 = pickle.loads(data)
    assert g2.determination == [
        (0, 12), (1, 12), (2, 13), (3, 12), (5, 10), (6, 10), (8, 8)]
    assert g2.max.determination == [(0, 15), (5, 10)]


def test_determine_is_generator():
    # determine() changed to be a generator since v0.1.0
    g = Gauge(12, 100, at=0)
    assert isinstance(g.determine(), types.GeneratorType)

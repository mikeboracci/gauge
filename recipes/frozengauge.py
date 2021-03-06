# -*- coding: utf-8 -*-
from gauge import Gauge


__all__ = [b'FrozenGauge']


class FrozenGauge(Gauge):

    def __init__(self, gauge):
        cls = type(self)
        limit_attrs = [('max_value', 'max_gauge'), ('min_value', 'min_gauge')]
        for value_attr, gauge_attr in limit_attrs:
            limit_gauge = getattr(gauge, gauge_attr)
            if limit_gauge is None:
                setattr(self, value_attr, getattr(gauge, value_attr))
                none_attr = gauge_attr
            else:
                setattr(self, gauge_attr, cls(limit_gauge))
                none_attr = value_attr
            setattr(self, none_attr, None)
        self._determination = gauge.determination
        self.linked_gauges = ()

    @property
    def base(self):
        raise TypeError('FrozenGauge doesn\'t keep the base')

    def _mutate_momenta(self, *args, **kwargs):
        raise TypeError('FrozenGauge doesn\'t keep the momenta')

    add_momenta = remove_momenta = _mutate_momenta

    def _rebase(self, *args, **kargs):
        self.base

    def __getstate__(self):
        return (self._determination, self.max_value, self.max_gauge,
                self.min_value, self.min_gauge)

    def __setstate__(self, state):
        self._determination, \
            self.max_value, self.max_gauge, \
            self.min_value, self.min_gauge = state

    def invalidate(self):
        raise AssertionError('FrozenGauge cannot be invalidated')

    def _set_limits(self, *args, **kwargs):
        raise TypeError('FrozenGauge is immutable')


def test_same_determination():
    g = Gauge(10, 100, at=0)
    g.add_momentum(+1, since=5, until=10)
    g.add_momentum(+1, since=20, until=30)
    g.add_momentum(-2, since=50, until=60)
    fg = FrozenGauge(g)
    assert fg.get(0) == g.get(0) == 10
    assert fg.get(10) == g.get(10) == 15
    assert fg.get(30) == g.get(30) == 25
    assert fg.get(60) == g.get(60) == 5
    assert fg.get(100) == g.get(100) == 5


def test_immutability():
    import pytest
    fg = FrozenGauge(Gauge(10, 100, at=0))
    with pytest.raises(AssertionError):
        fg.invalidate()
    with pytest.raises(TypeError):
        fg.incr(10, at=100)
    with pytest.raises(TypeError):
        fg.decr(10, at=100)
    with pytest.raises(TypeError):
        fg.set(10, at=100)
    with pytest.raises(TypeError):
        fg.add_momentum(+1, since=10, until=20)
    with pytest.raises(TypeError):
        fg.remove_momentum(+1, since=10, until=20)
    with pytest.raises(TypeError):
        fg.forget_past(at=10)

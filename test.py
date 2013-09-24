# -*- coding: utf-8 -*-
from gauge import Gauge


class Energy(Gauge):

    min = 0
    max = 10
    transform = Stairs(+1, 10)  # +1 energy per 10 seconds

    def use(self, amount=1, at=None):
        return self.decr(amount, at)


class Life(Gauge):

    min = 0
    max = 100
    transform = Linear(-1, 10)  # -1 life per 10 seconds

    def recover(self, amount=1, at=None):
        return self.incr(amount, at)

    def hurt(self, amount=1, at=None):
        return self.decr(amount, at)


def test_energy():
    with t(0):
        energy = Energy()
        assert energy == 10  # maximum by the default
        energy.use()
        assert energy == 9
        assert energy.recover_in() == 10
    with t(1):
        assert energy == 9
        assert energy.recover_in() == 9
    with t(2):
        assert energy == 9
        assert energy.recover_in() == 8
    with t(9):
        assert energy == 9
        assert energy.recover_in() == 1
    with t(10):
        assert energy == 10  # recovered fully
        assert energy.recover_in() is None
    with t(20):
        assert energy == 10  # no more recovery
        energy.incr(20, limit=False)
        assert energy == 30  # extra 20 energy
    with t(100):
        assert energy == 30


def test_life():
    with t(0):
        life = Life()
        assert life == 100
    with t(1):
        assert life == 99.9
    with t(2):
        assert life == 99.8
    with t(10):
        assert life == 99
    with t(100):
        assert life == 90
        life.recover(1000)
        assert life == 100  # limited by the maximum

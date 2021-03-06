# -*- coding: utf-8 -*-
import importlib
import math

import click

from gauge import TIME


class ImportString(click.ParamType):

    def convert(self, value, param, ctx):
        module_name, name = value.split(':')
        module = importlib.import_module(module_name)
        return getattr(module, name)


class GaugePlotting(object):

    margin_ratio = 0.1
    min_margin = 1

    def __init__(self, gauge):
        self.gauge = gauge

    def divide_lines(self, lines):
        times, values = [], []
        for line in lines:
            times.append(line.since)
            values.append(line.value)
        return times, values

    def expand_time_range(self, times, values, min_time=None, max_time=None):
        time_length = (times[-1] - times[0])
        margin = max(time_length * self.margin_ratio, self.min_margin)
        if min_time is None:
            min_time = math.floor(times[0] - margin)
        if max_time is None:
            max_time = math.ceil(times[-1] + margin)
        times.insert(0, min_time - margin)
        times.append(max_time + margin)
        values.insert(0, values[0])
        values.append(values[-1])
        return min_time, max_time

    def plot(self, plt):
        # determination
        determination_lines = self.gauge.walk_lines(self.gauge)
        times, values = self.divide_lines(determination_lines)
        min_time, max_time = self.expand_time_range(times, values)
        plt.plot(times, values, 'o-')
        # base time
        plt.axvline(self.gauge.base[TIME], linestyle=':')
        # max & min
        for limit in [self.gauge.max, self.gauge.min]:
            times, values = self.divide_lines(self.gauge.walk_lines(limit))
            self.expand_time_range(times, values, min_time, max_time)
            plt.plot(times, values, 'o--')
        # set axes
        plt.xlabel('Time')
        plt.xlim(min_time, max_time)
        plt.ylabel('Value')
        min_value, max_value = plt.ylim()
        y_margin = (max_value - min_value) * self.margin_ratio
        plt.ylim(min_value - y_margin, max_value + y_margin)


def show_gauge(gauge):
    import matplotlib.pyplot as plt
    from mpltools import style
    style.use('ggplot')
    plotter = GaugePlotting(gauge)
    plotter.plot(plt)
    plt.show()


@click.command()
@click.argument('gauge', type=ImportString())
@click.option('--matplotlib-backend', default='Qt4Agg')
def main(gauge, matplotlib_backend):
    import matplotlib
    matplotlib.use(matplotlib_backend)
    show_gauge(gauge)


if __name__ == '__main__':
    main()

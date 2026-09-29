"""Resource accounting and RGB-only sampling boundaries."""
import time

from experiments.noisy_rgb_discovery.core import Statistics
from experiments.noisy_rgb_discovery.sensor import RGBPort, Sensor

LIMITS = dict(max_actions=1000000, max_exposures=500000, max_wall_seconds=1800,
              max_probes_per_membership=30, max_depth=2)


class ResourceLimit(RuntimeError):
    pass


class Budget:
    def __init__(self, max_actions=1000000, max_exposures=500000, max_wall_seconds=1800, **unused):
        self.max_actions, self.max_exposures, self.max_wall_seconds = max_actions, max_exposures, max_wall_seconds
        self.actions = self.exposures = 0
        self.start = time.perf_counter()

    def check(self):
        if time.perf_counter()-self.start >= self.max_wall_seconds:
            raise ResourceLimit('wall_seconds')

    def reserve(self, history, batch):
        self.check()
        if self.actions+len(history) > self.max_actions:
            raise ResourceLimit('environment_actions')
        if self.exposures+batch > self.max_exposures:
            raise ResourceLimit('exposure_sets')
        self.actions += len(history)
        self.exposures += batch


def measured_statistics(sensor, budget=None, **statistics_kwargs):
    def sample(history, replicate):
        if budget is not None:
            budget.reserve(history, sensor.batch)
        return sensor.port.sample(history, replicate)
    return Statistics(RGBPort(sensor.port.actions, sample), **statistics_kwargs)


def stage_sensors(game, bias, directory, phase, budget=None, *,
                  stages=(8, 16, 32), floor_mode='fixed', noise_floor=.01,
                  reference_n=32):
    sensors, statistics = {}, {}
    stages = tuple(stages)
    if not stages or tuple(sorted(stages)) != stages or len(set(stages)) != len(stages):
        raise ValueError('stages must be unique and increasing')
    for n in stages:
        namespace = phase+'-v1' if n == 8 else f'vs-{phase}-{n}-v1'
        sensor = Sensor(game, bias, namespace, directory / f'{phase}_{n}', n, 12)
        sensors[n] = sensor
        statistics[n] = measured_statistics(
            sensor, budget, floor_mode=floor_mode, noise_floor=noise_floor,
            reference_n=reference_n)
    return sensors, statistics

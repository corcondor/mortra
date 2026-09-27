"""Capture public labels only at endpoints actually photographed by Sensor.

The learner receives an equality interface, not a goal-directed reward. The
environment has no terminal API; an absent terminal label is not invented.
"""
from experiments.noisy_rgb_discovery.sensor import Sensor
from experiments.noisy_rgb_discovery.source import environment_class
from experiments.noisy_rgb_version_space.core import SAME, DIFFERENT, UNRESOLVED
from experiments.noisy_rgb_version_space.runtime import measured_statistics


class PublicLabels:
    def __init__(self, records=()):
        self.records={tuple(h):dict(labels) for h,labels in records}

    def record(self):
        return list(self.records.items())

    def add(self,history,labels):
        h=tuple(history)
        if h in self.records:
            assert self.records[h]==labels, 'Public labels changed on deterministic replay'
        self.records[h]=dict(labels)

    def compare(self,h,r,e=()):
        x=self.records.get(tuple(h)+tuple(e))
        y=self.records.get(tuple(r)+tuple(e))
        if x is None or y is None:
            return UNRESOLVED
        return SAME if x==y else DIFFERENT


def labelled_game(seed):
    class ObservedLabelsOnly(environment_class()):
        def noisy_batch(self,raw,*args,**kwargs):
            result=super().noisy_batch(raw,*args,**kwargs)
            self.last_public_labels={'goal':bool(super().raw_goal(raw))}
            return result

        def token_for(self,*args):
            raise AssertionError('State tokens are forbidden')

        def raw_goal(self,*args):
            raise AssertionError('Public labels are captured only at sampled endpoints')

    return ObservedLabelsOnly(seed,'state_opaque')


class LabelledSensor(Sensor):
    def __init__(self,*args,labels,**kwargs):
        self.labels=labels
        super().__init__(*args,**kwargs)

    def sample(self,history,replicate):
        data=super().sample(history,replicate)
        self.labels.add(history,self.game.last_public_labels)
        return data


def labelled_stages(game,bias,directory,phase,budget,labels):
    sensors,statistics={},{}
    for n in (8,16,32):
        namespace=phase+'-v1' if n==8 else f'vs-{phase}-{n}-v1'
        sensor=LabelledSensor(game,bias,namespace,directory/f'{phase}_{n}',n,12,labels=labels)
        sensors[n]=sensor
        statistics[n]=measured_statistics(sensor,budget)
    return sensors,statistics

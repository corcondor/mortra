"""Serialize independent checkpoint inputs; never borrow future statistics."""
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.noisy_rgb_discovery.core import Emission
from experiments.noisy_rgb_discovery.run import save_statistics,write
from experiments.noisy_rgb_version_space.runtime import Budget

CHECKPOINTS=(50000,100000,250000,500000)


class CheckpointBudget(Budget):
    def __init__(self,callback,**kwargs):
        super().__init__(**kwargs)
        self.callback=callback
        self.saved=set()
    def reserve(self,history,batch):
        for target in CHECKPOINTS:
            if target not in self.saved and self.exposures+batch>target:
                self.callback(target,self.exposures)
                self.saved.add(target)
        super().reserve(history,batch)


def v1_record(table):
    return dict(representatives=list(table.S),suffixes=list(table.E),
                transitions=[(q,a,t) for (q,a),t in sorted(table.trans.items())],
                queue=list(table.queue.values()),counts=dict(table.counts),evidence_version=table.evidence.version)


def save_checkpoint(directory,state,statistics,metadata):
    directory.mkdir(parents=True,exist_ok=False)
    write(directory/'state.json',state)
    write(directory/'checkpoint.json',metadata)
    for n,stats in statistics.items():
        folder=directory/f'statistics_{n}'
        folder.mkdir()
        save_statistics(stats,folder)
    write(directory/'hashes.json',{str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in directory.rglob('*') if p.is_file()})


def load_statistics(directory):
    data={}
    for n in (8,16,32):
        folder=directory/f'statistics_{n}'
        keys=json.loads((folder/'statistics_index.json').read_text())
        with gzip.open(folder/'statistics.bin.gz','rb') as f:
            arrays=np.frombuffer(f.read(),'<f4').reshape(-1,2,1728)
        data[n]={(tuple(h),rep):Emission(v[0],v[1],n) for (h,rep),v in zip(keys,arrays)}
        assert len(data[n])==len(keys)==len(arrays)
    return data


def verify_checkpoint(directory):
    hashes=json.loads((directory/'hashes.json').read_text())
    for name,expected in hashes.items():
        assert hashlib.sha256((directory/name.replace('\\','/')).read_bytes()).hexdigest()==expected


def confirmed_graph(state,arm):
    if arm=='V1':
        return {(q,a):t for q,a,t in state['transitions']}
    nodes={tuple(n['history']):n for n in state['nodes']}
    trans={}
    for q,h in enumerate(state['representatives']):
        for a,child in nodes[tuple(h)]['outgoing']:
            target=nodes[tuple(child)]
            if target['status'] in ('representative','merged') and target['representative'] is not None:
                trans[q,a]=target['representative']
    return trans

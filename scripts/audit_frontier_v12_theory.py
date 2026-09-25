"""Staged frozen-parent audit. No evolution entrypoint is exposed."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.frontier_v12_theory import data,landscape,saved,field,summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['register','landscape','saved','field','smoke-check','summarize'])
    for name in ('source','registration','input','saved','field','output'):
        p.add_argument('--'+name,type=Path,required=name=='output')
    p.add_argument('--seed',type=int)
    p.add_argument('--stage',type=int,choices=[1,2],default=2)
    a=p.parse_args()
    if a.mode=='register': data.register(a.source,a.output)
    elif a.mode=='landscape': landscape.run(a.input,a.output,a.stage)
    elif a.mode=='saved': saved.run(a.source,a.output)
    elif a.mode=='field': field.run(a.source,a.output,a.seed,a.stage==1)
    elif a.mode=='smoke-check':
        assert data.read(a.input/'completed.json')['candidates']==210
        assert data.read(a.field/'completed.json')['worlds']==3
        assert data.read(a.saved/'completed.json')['status']=='COMPLETED'
        summary.landscape(a.registration,a.input,a.output,smoke=True)
        data.write(a.output/'gate.json',dict(status='CORRECTNESS_GATE_PASSED',performance_gate=False,
                                           parent_updates=0,replicates_after_gate=10))
    else: summary.combine(a.registration,a.input,a.saved,a.field,a.output)


if __name__=='__main__': main()

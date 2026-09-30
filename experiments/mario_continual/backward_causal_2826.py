"""Backward causal intervention sweep on replayed episode 2826.

No completion/world-coordinate value participates in an intervention.  For each
offset from the terminal, replace exactly one primitive action, replay the
original suffix, and ask whether the mutation survives beyond the original
175-action failure horizon.  Completion is recorded only after each trial as
an audit.
"""
from pathlib import Path
import json, shutil
from experiments.mario_continual.port import MarioRGBPort

ROOT=Path(__file__).resolve().parent
SEED=[8,10,1,0,9,3,9,9,9,10,0,10,1,11,7,1,11,7,1,5,6,8,0,0,0,5,0,0,5,11,3,4,9,7,4,3,9,7,2,10,9,10,8,0,9,2,0,9,3,3,7,6,7,8,5,3,10,4,2,7,2,7,2,7,8,7,5,5,2,7,4,4,10,8,3,9,8,1,7,8,6,3,6,7,9,7,10,11,9,3,6,2,10,0,8,11,1,3,9,6,10,2,6,0,4,4,11,3,5,4,4,5,4,10,8,8,4,6,9,2,9,0,2,8,7,5,8,11,4,8,2,1,5,0,6,6,8,10,0,3,6,6,3,11,4,9,9,7,1,11,0,2,10,11,8,8,5,2,4,8,5,7,3,3,9,8,5,3,3,11,3,9,5,5,6]
OFFSETS=(1,2,4,8,16,32,64,128)
MAX_ACTIONS=250
PAD=tuple(range(12))

def run_trial(name, planned, out):
    d=out/name
    if d.exists(): shutil.rmtree(d)
    port=MarioRGBPort(ROOT/"game",ROOT/"build",ROOT/"java"/"MortraBridge.java",
                      "levels/notch/lvl-1.txt",d,seconds=60,frames_per_action=8)
    executed=0
    try:
        _,packet=port.start()
        for a in planned:
            if packet["kind"]!="observation": break
            _,packet=port.step(a); executed+=1
        survived_original_horizon=(executed>=len(SEED) and packet["kind"]=="observation")
        k=0
        while packet["kind"]=="observation" and executed<MAX_ACTIONS:
            _,packet=port.step(PAD[k%len(PAD)]); executed+=1; k+=1
        return dict(
            executed=executed,
            status=packet.get("status") if packet["kind"]=="terminal" else "SURVIVED_LIMIT",
            survived_original_horizon=survived_original_horizon,
            completion_audit_only=packet.get("completion_audit_only") if packet["kind"]=="terminal" else None)
    finally:
        port.close()

def main():
    out=Path("/tmp/backward-causal-2826")
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    baseline=run_trial("baseline",SEED,out)
    print("BASELINE",json.dumps(baseline,sort_keys=True),flush=True)
    rows=[]
    for off in OFFSETS:
        idx=len(SEED)-off
        original=SEED[idx]
        trials=[]
        for a in range(12):
            if a==original: continue
            planned=list(SEED)
            planned[idx]=a
            r=run_trial(f"off{off}_a{a}",planned,out)
            r.update(offset=off,index=idx,original_action=original,action=a)
            trials.append(r)
        summary=dict(
            offset=off,index=idx,original_action=original,
            alternatives=len(trials),
            survived_past_original=sum(t["survived_original_horizon"] for t in trials),
            max_executed=max(t["executed"] for t in trials),
            max_completion_audit_only=max((t["completion_audit_only"] or 0.0) for t in trials),
            reached_50pct=any((t["completion_audit_only"] or 0.0)>=.5 for t in trials),
            trials=trials)
        rows.append(summary)
        print("OFFSET_RESULT",json.dumps({k:v for k,v in summary.items() if k!="trials"},sort_keys=True),flush=True)
    result=dict(
        experiment="backward_single_action_intervention_episode_2826",
        forbidden_intervention_inputs=["completion_audit_only","world coordinates"],
        baseline=baseline,offsets=rows,
        earliest_tested_offset_with_survival=next((r["offset"] for r in rows if r["survived_past_original"]),None),
        any_50pct=any(r["reached_50pct"] for r in rows))
    Path("/tmp/backward_causal_2826.json").write_text(json.dumps(result,indent=2,sort_keys=True))
    print("BACKWARD_CAUSAL_RESULT",json.dumps({k:v for k,v in result.items() if k!="offsets"},sort_keys=True),flush=True)

if __name__=="__main__":
    main()

"""Evaluator-side static semantics. No sensor sampling or learner invocation."""
from collections import deque
import hashlib

from experiments.noisy_rgb_discovery.source import environment_class


def static_table(seed):
    game=environment_class()(seed,'state_opaque')
    def forbidden(*args,**kwargs):
        raise AssertionError('No stochastic RGB, token, or interactive step is allowed in this audit')
    game.noisy_rgb=game.noisy_batch=game.token_for=game.step=forbidden
    # raw_step is a pure map of explicit immutable tuples. The environment has
    # no changing current state here. Count these as offline table calculations,
    # never as acquired observations or player interactions.
    states=[tuple(game.start_raw)]
    ids={states[0]:0}
    queue=deque(states)
    transition_rows=[]
    while queue:
        s=queue.popleft()
        row=[]
        for a in range(5):
            t=tuple(game.raw_step(s,a))
            if t not in ids:
                ids[t]=len(states); states.append(t); queue.append(t)
            row.append(ids[t])
        transition_rows.append(row)
    clean=[game.obs_bytes(s,0,12) for s in states]
    labels=[bool(game.raw_goal(s)) for s in states]
    # Byte equality is only an evaluator observable, never a learner classifier.
    output_ids={}
    observations=[output_ids.setdefault(x,len(output_ids)) for x in clean]
    return dict(seed=seed,states=states,transitions=transition_rows,observations=observations,
                public_goal=labels,public_terminal='API unavailable',start=0,
                clean_output_sha256=[hashlib.sha256(x).hexdigest() for x in clean],
                offline_pure_transition_evaluations=5*len(states),
                offline_deterministic_output_evaluations=len(states),
                sensor_calls=0,new_exposures=0,interactive_environment_actions=0,
                scope='Clean four-view output plus public labels; not a proof of stochastic-distribution equivalence')

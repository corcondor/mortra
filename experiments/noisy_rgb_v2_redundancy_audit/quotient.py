"""Finite deterministic observation refinement and exact witness depths."""
from collections import Counter
from itertools import product


def canonical(values):
    ids={}
    return [ids.setdefault(value,len(ids)) for value in values]


def partitions(transitions,outputs):
    """P_d equates precisely the outputs after every word of length <= d."""
    initial=canonical(outputs)
    layers=[initial]
    while True:
        old=layers[-1]
        new=canonical((initial[s],tuple(old[t] for t in row)) for s,row in enumerate(transitions))
        if new==old:
            return layers
        assert len(set(new))>len(set(old))
        layers.append(new)


def endpoint(transitions,s,word):
    for a in word:
        s=transitions[s][a]
    return s


def shortest_witness(transitions,layers,s,t):
    depth=next((d for d,p in enumerate(layers) if p[s]!=p[t]),None)
    if depth is None:
        return None
    word=[]
    for d in range(depth,0,-1):
        a=next(a for a in range(len(transitions[s]))
               if layers[d-1][transitions[s][a]]!=layers[d-1][transitions[t][a]])
        word.append(a)
        s,t=transitions[s][a],transitions[t][a]
    assert layers[0][s]!=layers[0][t]
    return tuple(word)


def analyze_table(transitions,outputs,depth=6):
    layers=partitions(transitions,outputs)
    final=layers[-1]
    reps={}
    for s,q in enumerate(final):
        reps.setdefault(q,s)
    pairs=[]
    for q,s in reps.items():
        for r,t in reps.items():
            if q>=r:
                continue
            witness=shortest_witness(transitions,layers,s,t)
            assert witness is not None
            assert outputs[endpoint(transitions,s,witness)]!=outputs[endpoint(transitions,t,witness)]
            pairs.append(dict(class_a=q,class_b=r,state_a=s,state_b=t,
                              minimum_depth=len(witness),witness=witness))
    counts=[len(set(layers[min(d,len(layers)-1)])) for d in range(depth+1)]
    # Independent exhaustive check of the requested 31 experiments.
    words=[w for d in range(3) for w in product(range(len(transitions[0])),repeat=d)]
    explicit=canonical(tuple(outputs[endpoint(transitions,s,w)] for w in words) for s in range(len(outputs)))
    assert explicit==layers[min(2,len(layers)-1)]
    return dict(q_by_depth=counts,q2=counts[2],q_infinity=len(reps),
                stabilization_depth=len(layers)-1,experiments_through_2=len(words),
                d_star_histogram=dict(Counter(p['minimum_depth'] for p in pairs)),
                true_class_pairs=len(pairs),pairs_requiring_over_2=sum(p['minimum_depth']>2 for p in pairs),
                pairs_requiring_over_6=sum(p['minimum_depth']>6 for p in pairs)),layers,pairs

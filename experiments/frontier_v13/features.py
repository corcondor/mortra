"""Pure static program analysis. No file, environment, evaluator or label access."""
from collections import Counter
from difflib import SequenceMatcher
import math
import statistics

from .protocol import ARMS, canonical


def rule_sets(rule):
    reads = {g['var'] for g in rule['guard']}
    writes = {e['var'] for e in rule['assign']}
    reads.update(e['var'] for e in rule['assign'] if e['op'] in ('add', 'add_mod'))
    reads.update(e['value'] for e in rule['assign'] if e['op'] == 'copy_mod')
    return reads, writes


def dependency(rules):
    rw = [rule_sets(r) for r in rules]
    edges = {(i, j) for i, (_, w) in enumerate(rw) for j, (r, _) in enumerate(rw) if w & r}
    # Transitive closure is static rule-dependency analysis, not world rollout.
    reach = {i: {j for u, j in edges if u == i} | {i} for i in range(len(rules))}
    for k in reach:
        for i in reach:
            if k in reach[i]:
                reach[i] |= reach[k]
    blocks = []
    todo = set(reach)
    while todo:
        i = min(todo)
        block = {j for j in todo if j in reach[i] and i in reach[j]}
        blocks.append(block)
        todo -= block
    owner = {i: b for b, block in enumerate(blocks) for i in block}
    dag = {(owner[i], owner[j]) for i, j in edges if owner[i] != owner[j]}
    depth = {i: 1 for i in range(len(blocks))}
    while True:
        nxt = {i: max([1] + [depth[j] + 1 for j, k in dag if k == i]) for i in depth}
        if nxt == depth:
            break
        depth = nxt
    cyc = sum(len(b) > 1 or any((i, i) in edges for i in b) for b in blocks)
    return rw, edges, len(blocks), cyc, max(depth.values(), default=0)


def spatial(g):
    nx, ny = g['domains'][:2]
    free = {(x, y) for x in range(nx) for y in range(ny)} - set(map(tuple, g['walls']))
    edges = {(u, v) for u in free for v in ((u[0]+1, u[1]), (u[0], u[1]+1)) if v in free}
    degrees = Counter(v for edge in edges for v in edge)
    return free, edges, [degrees[p] for p in free]


def program(g):
    rw, edges, scc, cycles, depth = dependency(g['rules'])
    free, spatial_edges, degrees = spatial(g)
    domains = g['domains']
    reads = set().union(*(r for r, w in rw)) if rw else set()
    writes = set().union(*(w for r, w in rw)) if rw else set()
    f = dict(variables=len(domains), actions=g['actions'], rules=len(g['rules']),
             domain_min=min(domains), domain_max=max(domains), domain_sum=sum(domains),
             domain_mean=statistics.mean(domains), domain_product=math.prod(domains),
             log_domain_product=sum(math.log(n) for n in domains),
             guards=sum(len(r['guard']) for r in g['rules']),
             effects=sum(len(r['assign']) for r in g['rules']),
             dependency_edges=len(edges), dependency_scc=scc, dependency_cycles=cycles,
             dependency_depth=depth, read_set_size=len(reads), write_set_size=len(writes),
             board_width=domains[0], board_height=domains[1], board_area=domains[0]*domains[1],
             passable_cells=len(free), walls=len(g['walls']), spatial_edges=len(spatial_edges),
             branching_mean=statistics.mean(degrees) if degrees else 0,
             branching_max=max(degrees, default=0),
             branching_std=statistics.pstdev(degrees) if degrees else 0,
             unguarded_rules=sum(not r['guard'] for r in g['rules']))
    for op in ('eq', 'ne', 'lt', 'ge'):
        f['guard_op_' + op] = sum(c['op'] == op for r in g['rules'] for c in r['guard'])
    for op in ('set', 'add', 'add_mod', 'copy_mod'):
        f['effect_op_' + op] = sum(c['op'] == op for r in g['rules'] for c in r['assign'])
    return f


def leaves(x, prefix=()):
    if isinstance(x, dict):
        return {p: v for k in sorted(x) for p, v in leaves(x[k], (*prefix, k)).items()}
    if isinstance(x, list):
        return {p: v for k, item in enumerate(x) for p, v in leaves(item, (*prefix, k)).items()}
    return {prefix: x}


def sequence_changes(a, b):
    added = removed = changed = 0
    for tag, i, j, k, l in SequenceMatcher(None, list(map(canonical, a)), list(map(canonical, b)), autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        common = min(j-i, l-k)
        changed += common
        added += l-k-common
        removed += j-i-common
    return added, removed, changed


def edit(parent, child):
    a, b = program(parent), program(child)
    f = {'delta_' + k: b[k]-a[k] for k in a}
    for name, key in (('rules', 'rules'),):
        for tag, value in zip(('added', 'removed', 'changed'), sequence_changes(parent[key], child[key])):
            f[name+'_'+tag] = value
    for name, key in (('guards', 'guard'), ('effects', 'assign')):
        before = [x for r in parent['rules'] for x in r[key]]
        after = [x for r in child['rules'] for x in r[key]]
        for tag, value in zip(('added', 'removed', 'changed'), sequence_changes(before, after)):
            f[name+'_'+tag] = value
    for name in ('variables', 'actions'):
        f[name+'_added'] = max(0, b[name]-a[name])
        f[name+'_removed'] = max(0, a[name]-b[name])
    before = leaves({k: parent[k] for k in ('domains', 'actions', 'initial', 'rules')})
    after = leaves({k: child[k] for k in ('domains', 'actions', 'initial', 'rules')})
    changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    # AST change means changed/inserted/deleted scalar syntax leaves; list order is significant.
    f['ast_nodes_changed'] = len(changed)
    f['rules_touched'] = len({k[1] for k in changed if k[0] == 'rules'})
    f['constants_changed'] = sum(k[-1] == 'value' for k in changed)
    f['domain_sizes_changed'] = sum(x != y for x, y in zip(parent['domains'], child['domains']))
    f['domain_change_magnitude'] = sum(abs(x-y) for x, y in zip(parent['domains'], child['domains'])) + sum(parent['domains'][len(child['domains']):]) + sum(child['domains'][len(parent['domains']):])
    variables = {k[1] for k in changed if k[0] in ('domains', 'initial')}
    for g in (parent, child):
        for i in {k[1] for k in changed if k[0] == 'rules'}:
            if i < len(g['rules']):
                r, w = rule_sets(g['rules'][i]); variables |= r | w
    f['variables_touched'] = len(variables)
    _, ae, *_ = dependency(parent['rules'])
    _, be, *_ = dependency(child['rules'])
    f['dependency_edges_added'] = len(be-ae)
    f['dependency_edges_removed'] = len(ae-be)
    af, ae, _ = spatial(parent)
    bf, be, _ = spatial(child)
    f['spatial_cells_changed'] = len(af ^ bf)
    f['wall_declarations_changed'] = len(set(map(tuple, parent['walls'])) ^ set(map(tuple, child['walls'])))
    f['spatial_edges_added'] = len(be-ae)
    f['spatial_edges_removed'] = len(ae-be)
    return f


def history_features(events, arm):
    out = {}
    for name, seq in (('arm', [e for e in events if e['mutation'] == arm]), ('all', events)):
        values = [e['reward'] for e in seq]
        out[name+'_count'] = len(seq)
        out[name+'_mean'] = statistics.mean(values) if values else 0
        out[name+'_variance'] = statistics.pvariance(values) if values else 0
        out[name+'_positive_rate'] = sum(v > 0 for v in values) / len(seq) if seq else 0
        out[name+'_eligible_rate'] = sum(e['outcome']['eligible'] for e in seq)/len(seq) if seq else 0
        out[name+'_invalid_rate'] = sum(not e['outcome']['valid'] for e in seq)/len(seq) if seq else 0
    return out


PARENT_METRICS = ('reachable_states', 'D', 'B50', 'B80', 'B90', 'final_success',
                  'full_info_success', 'state_coverage', 'edge_coverage')


def extract(parent_genome, candidate_genome, primitive, parent_metrics, decision, past_events):
    assert primitive in ARMS
    assert set(parent_metrics) == set(PARENT_METRICS)
    out = {'op_'+a: float(a == primitive) for a in ARMS}
    out.update({'parent_'+k: float(v) for k, v in program(parent_genome).items()})
    for k in PARENT_METRICS:
        out['parent_metric_'+k] = float(parent_metrics[k] or 0)
        out['parent_metric_'+k+'_available'] = float(parent_metrics[k] is not None)
    # An absent genome is a generation-time fact, never an evaluated invalidity label.
    out['edit_genome_available'] = float(candidate_genome is not None)
    out.update({'edit_'+k: float(v) for k, v in edit(parent_genome, candidate_genome or parent_genome).items()})
    n = decision['counts'][primitive]
    total = sum(decision['counts'].values())
    out.update(ucb_context_bin=float(decision['context']['reachable_states'].bit_length()-1),
               ucb_context_reached=float(decision['context']['B80'] is not None),
               ucb_count=float(n), ucb_mean=float(decision['mean_rewards'][primitive] or 0),
               ucb_mean_available=float(n > 0), ucb_bonus=math.sqrt(2*math.log(max(total, 1))/n) if n else 0.,
               ucb_untried=float(n == 0))
    out.update({'history_'+k: float(v) for k, v in history_features(past_events, primitive).items()})
    assert all(math.isfinite(v) for v in out.values())
    return out


def columns(names, feature_set):
    prefixes = {'M0': ('op_',), 'M1': ('op_', 'ucb_'),
                'M2': ('op_', 'parent_'), 'M3': ('op_', 'parent_', 'edit_'),
                'M4': ('op_', 'parent_', 'edit_', 'history_', 'ucb_')}
    return [n for n in names if n.startswith(prefixes[feature_set])]

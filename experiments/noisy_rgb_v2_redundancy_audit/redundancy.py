"""Describe actual checkpoint gates, using only already recorded evidence."""
from collections import Counter,defaultdict
from itertools import product
import hashlib
import json

WORDS=[()]+[(a,) for a in range(5)]+list(product(range(5),repeat=2))


def pair_key(h,r):
    return tuple(sorted((tuple(h),tuple(r))))


def certificate(cache,h,r):
    if tuple(h)==tuple(r):
        return 'SAME',None
    row=cache.get(pair_key(h,r))
    return (row['result'],row['id']) if row else ('NOT_COMPARED',None)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class EventPrefix:
    def __init__(self):
        self.certificates={}
        self.counts=Counter()
        self.status={}
        self.probes=defaultdict(set)
        self.pending={}
        self.progress_cleared=0
        self.nodes_with_progress_cleared=0
        self.exposure_time_events=[]

    def accept(self,row):
        event=row['event']
        self.counts[event]+=1
        if event=='comparison' and row['stage']==32:
            self.certificates[pair_key(*row['pair'])]={k:row[k] for k in ('id','result')}
        if event=='initial_representative':
            self.status[tuple(row['history'])]='representative'
        if event=='provisional_created':
            self.status[tuple(row['history'])]='provisional'
        if event in ('unmerge','merge_reopened'):
            self.status[tuple(row['history'])]='provisional'
        if event=='empirical_merge':
            self.status[tuple(row['history'])]='merged'
        if event=='active_probe':
            self.pending[tuple(row['history'])]=tuple(row['selected'])
        if event=='belief':
            h=tuple(row['history'])
            if h in self.pending:
                self.probes[h].add(self.pending.pop(h))
        if event=='promotion':
            h=tuple(row['history'])
            self.status[h]='representative'
            for r,status in self.status.items():
                if status=='provisional' and self.probes[r]:
                    self.progress_cleared+=len(self.probes[r])
                    self.nodes_with_progress_cleared+=1
                    self.probes[r].clear()


def summarize_buckets(groups):
    return dict(bucket_count=len(groups),size_histogram=dict(Counter(len(v) for v in groups.values())),
                largest_bucket=max(map(len,groups.values()),default=0),
                mixed_true_class_buckets=sum(len(set(v))>1 for v in groups.values()),
                largest_true_class_count=max((len(set(v)) for v in groups.values()),default=0),
                note='Grouping is diagnostic only; matching candidate/outcome signatures do not prove safe merging or shared RGB evidence.')


def checkpoint_audit(state,meta,prefix,table,layers,statistics_keys,write_node,write_pair):
    cache=prefix.certificates
    assert all(c['id']<=state['evidence_version'] for c in cache.values())
    nodes={tuple(n['history']):n for n in state['nodes']}
    representatives=list(map(tuple,state['representatives']))
    labels={tuple(h):lab for h,lab in state.get('public_labels',[])}
    transitions=table['transitions']
    final=layers[-1]
    depth2=layers[min(2,len(layers)-1)]
    end_cache={():table['start']}
    def at(h):
        h=tuple(h)
        if h not in end_cache:
            end_cache[h]=transitions[at(h[:-1])][h[-1]]
        return end_cache[h]
    qclasses=[final[at(r)] for r in representatives]
    class_reps=defaultdict(list)
    for q,c in enumerate(qclasses):
        class_reps[c].append(q)
    provisional=[n for n in state['nodes'] if n['status']=='provisional']
    per_class=defaultdict(list)
    totals=Counter()
    pair_totals=Counter()
    suffixes={str(e):Counter() for e in WORDS}
    masks=Counter()
    candidate_buckets=defaultdict(list)
    outcome_buckets=defaultdict(list)
    literal_buckets=defaultdict(list)
    probe_hist=Counter()
    out_hist=Counter()
    age_hist=Counter()
    passive_index={}
    for (x,y),c in cache.items():
        if c['result']!='DIFFERENT':
            continue
        common=0
        while common<min(len(x),len(y)) and x[-common-1]==y[-common-1]:
            common+=1
        for k in range(common+1):
            a,b=(x[:-k],y[:-k]) if k else (x,y)
            passive_index.setdefault(pair_key(a,b),dict(suffix=x[-k:] if k else (),certificate=c['id']))

    def passive_contradiction(h,r):
        return passive_index.get(pair_key(h,r))

    for node in provisional:
        h=tuple(node['history'])
        true_class=final[at(h)]
        per_class[true_class].append(h)
        belief=node['belief']
        candidates=sorted(belief['existing_candidates'])
        same_candidates=[q for q in candidates if qclasses[q]==true_class]
        flags={}
        flags['true_class_unrepresented']=true_class not in class_reps
        flags['true_class_represented_but_absent_from_candidates']=true_class in class_reps and not same_candidates
        flags['own_outgoing_incomplete']=len(node['outgoing'])<5
        flags['no_existing_candidate']=not candidates
        pair_records=[]
        eligible=[]
        same_eligible=[]
        all_outcomes=[]
        all_ids=[]
        for q in candidates:
            r=representatives[q]
            same_class=qclasses[q]==true_class
            structurally_aliased=depth2[at(h)]==depth2[at(r)] and not same_class
            outcomes=[]
            label_outcomes=[]
            certificate_ids=[]
            complete_saved_rgb=[]
            for i,e in enumerate(WORDS):
                x,y=h+e,r+e
                outcome,cid=certificate(cache,x,y)
                label=('NOT_OBSERVED' if x not in labels or y not in labels else
                       'SAME' if labels[x]==labels[y] else 'DIFFERENT')
                available=all((word,j) in statistics_keys[n] for word in (x,y) for n in (8,16,32) for j in (0,1))
                outcomes.append(outcome); certificate_ids.append(cid)
                label_outcomes.append(label); complete_saved_rgb.append(available)
                suffixes[str(e)][outcome]+=1
                if same_class:
                    suffixes[str(e)]['same_true_class_'+outcome]+=1
                if outcome=='NOT_COMPARED':
                    pair_totals['unmeasured_saved_RGB_available' if available else 'unmeasured_missing_RGB']+=1
                if same_class and outcome=='DIFFERENT':
                    pair_totals['same_true_class_DIFFERENT_certificates']+=1
            counts=Counter(outcomes)
            label_counts=Counter(label_outcomes)
            edges_complete=len(node['outgoing'])==5 and len(nodes[r]['outgoing'])==5
            passive=passive_contradiction(h,r)
            passes=counts['SAME']==31 and label_counts['SAME']==31 and edges_complete and passive is None
            if passes:
                eligible.append(q)
                if same_class:
                    same_eligible.append(q)
            statistical_only=(same_class and counts['UNRESOLVED']>0 and counts['NOT_COMPARED']==0
                              and counts['DIFFERENT']==0 and label_counts['SAME']==31
                              and edges_complete and passive is None)
            pair_totals['pairs']+=1
            pair_totals['same_true_class_pairs' if same_class else 'different_true_class_pairs']+=1
            pair_totals['structural_depth2_alias_pairs']+=structurally_aliased
            pair_totals['same_class_statistical_rule_only_blocker_pairs']+=statistical_only
            pair_totals['same_class_pairs_with_UNRESOLVED']+=same_class and counts['UNRESOLVED']>0
            pair_totals['same_class_pairs_with_NOT_COMPARED']+=same_class and counts['NOT_COMPARED']>0
            pair_totals['same_class_pairs_with_missing_labels']+=same_class and label_counts['NOT_OBSERVED']>0
            flags['any_NOT_COMPARED']=flags.get('any_NOT_COMPARED',False) or counts['NOT_COMPARED']>0
            flags['any_measured_UNRESOLVED']=flags.get('any_measured_UNRESOLVED',False) or counts['UNRESOLVED']>0
            flags['candidate_with_DIFFERENT_still_retained']=flags.get('candidate_with_DIFFERENT_still_retained',False) or counts['DIFFERENT']>0
            flags['any_missing_public_label']=flags.get('any_missing_public_label',False) or label_counts['NOT_OBSERVED']>0
            flags['any_public_label_DIFFERENT']=flags.get('any_public_label_DIFFERENT',False) or label_counts['DIFFERENT']>0
            flags['any_structural_depth2_alias']=flags.get('any_structural_depth2_alias',False) or structurally_aliased
            flags['same_class_statistical_only_match_blocker']=flags.get('same_class_statistical_only_match_blocker',False) or statistical_only
            record=dict(history=h,representative=q,true_class=true_class,representative_true_class=qclasses[q],
                        same_true_class=same_class,depth2_alias=structurally_aliased,
                        rgb_outcomes=outcomes,public_label_outcomes=label_outcomes,certificate_ids=certificate_ids,
                        complete_saved_rgb=complete_saved_rgb,own_outgoing=len(node['outgoing']),
                        representative_outgoing=len(nodes[r]['outgoing']),passive_counterexample=passive,
                        passes_frozen_pair_merge_gate=passes,statistical_rule_only_blocker=statistical_only)
            write_pair(record)
            pair_records.append((counts,label_counts))
            all_outcomes.append((q,outcomes,label_outcomes,edges_complete,passive is not None))
            all_ids.append((q,certificate_ids))
        flags['some_correct_match_passes_but_other_candidate_blocks']=bool(same_eligible) and len(eligible)<len(candidates)
        flags['all_candidates_eligible_but_not_committed']=bool(candidates) and len(eligible)==len(candidates)
        totals.update(k for k,v in flags.items() if v)
        mask=tuple(sorted(k for k,v in flags.items() if v))
        masks['|'.join(mask)]+=1
        candidate_key=digest((candidates,belief['new_state_possible']))
        pattern_key=digest((candidate_key,all_outcomes,len(node['outgoing'])))
        literal_key=digest((pattern_key,all_ids,node.get('certificates',[])))
        candidate_buckets[candidate_key].append(true_class)
        outcome_buckets[pattern_key].append(true_class)
        literal_buckets[literal_key].append(true_class)
        probe_hist[len(node['tested_probes'])]+=1
        out_hist[len(node['outgoing'])]+=1
        age=state['evidence_version']-node['evidence_version']
        age_hist[age]+=1
        write_node(dict(history=h,true_class=true_class,depth2_class=depth2[at(h)],belief=belief,
                        represented_true_class=true_class in class_reps,same_true_class_representatives=class_reps.get(true_class,[]),
                        same_true_class_candidates=same_candidates,eligible_matches=eligible,flags=flags,
                        tested_probes=node['tested_probes'],outgoing_count=len(node['outgoing']),
                        certificate_age=age,candidate_bucket=candidate_key,outcome_bucket=pattern_key,literal_bucket=literal_key))

    class_counts=[dict(true_class=c,provisional_count=len(histories),represented_by=class_reps.get(c,[]),
                       history_lengths=dict(Counter(map(len,histories)))) for c,histories in sorted(per_class.items())]
    photo_classes=Counter()
    for n,keys in statistics_keys.items():
        for h,j in keys:
            photo_classes[final[at(h)]]+=n
    expected=sum(n*len(keys) for n,keys in statistics_keys.items())
    assert expected==meta['actual_exposures']-1600, ('Checkpoint sample prefix mismatch',expected,meta)
    return dict(checkpoint=meta,provisional_count=len(provisional),confirmed_representatives=len(representatives),
        represented_confirmed_classes=len(set(qclasses)),represented_provisional_classes=len(per_class),
        represented_union_classes=len(set(qclasses)|set(per_class)),
        provisional_per_true_class=class_counts,
        within_true_class_redundant_histories=sum(max(0,len(v)-1) for v in per_class.values()),
        same_true_class_provisional_pairs=sum(len(v)*(len(v)-1)//2 for v in per_class.values()),
        provisional_in_unrepresented_classes=sum(len(v) for c,v in per_class.items() if c not in class_reps),
        provisional_in_represented_classes=sum(len(v) for c,v in per_class.items() if c in class_reps),
        node_flags=dict(totals),joint_node_blockers=dict(masks),pair_summary=dict(pair_totals),
        suffix_outcomes={k:dict(v) for k,v in suffixes.items()},word_order=WORDS,
        tested_probe_count_histogram=dict(probe_hist),observed_outgoing_count_histogram=dict(out_hist),
        evidence_age_histogram=dict(age_hist),candidate_buckets=summarize_buckets(candidate_buckets),
        outcome_buckets=summarize_buckets(outcome_buckets),literal_certificate_buckets=summarize_buckets(literal_buckets),
        acquisition_exposures_by_true_class=dict(photo_classes),recorded_event_counts=dict(prefix.counts),
        probe_progress_entries_cleared_by_promotion=prefix.progress_cleared,
        node_reset_occurrences_with_nonempty_progress=prefix.nodes_with_progress_cleared,
        new_sensor_calls=0,learner_updates=0,
        notes=['Flags overlap; joint_node_blockers partitions nodes without claiming causal effects.',
               'Statistical-only blocker means all 31 comparisons exist, same truth class, public labels and edge gates pass, no observed contradiction.',
               'NOT_COMPARED is distinct from a recorded UNRESOLVED result; saved RGB availability is counted without recomputing outcomes.',
               'Redundant histories share evaluator truth only; this does not license learner-side merging.',
               'Literal certificate IDs and equal outcome patterns are different evidence-sharing notions.'])

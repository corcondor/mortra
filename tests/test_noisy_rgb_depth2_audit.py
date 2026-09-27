import itertools
import random
import io
import zipfile

from experiments.noisy_rgb_v2_redundancy_audit.quotient import analyze_table,canonical,endpoint,partitions
from experiments.noisy_rgb_v2_redundancy_audit.artifacts import extract_selected,wanted
from experiments.noisy_rgb_v2_redundancy_audit.redundancy import EventPrefix,checkpoint_audit,pair_key,WORDS


def test_depth_two_is_not_infinite_equivalence():
    transitions=[[1],[2],[3],[3],[4]]
    outputs=[0,0,0,1,0]
    summary,layers,pairs=analyze_table(transitions,outputs)
    assert summary['q2']==4 and summary['q_infinity']==5
    pair=next(p for p in pairs if {p['state_a'],p['state_b']}=={0,4})
    assert pair['minimum_depth']==3 and pair['witness']==(0,0,0)


def test_exhaustive_short_words_match_refinement_on_random_tables():
    rng=random.Random(28)
    for _ in range(40):
        n,a=7,3
        trans=[[rng.randrange(n) for _ in range(a)] for _ in range(n)]
        outputs=[rng.randrange(3) for _ in range(n)]
        summary,layers,pairs=analyze_table(trans,outputs)
        for depth in range(5):
            words=[w for d in range(depth+1) for w in itertools.product(range(a),repeat=d)]
            exact=canonical(tuple(outputs[endpoint(trans,s,w)] for w in words) for s in range(n))
            assert exact==layers[min(depth,len(layers)-1)]
        assert sum(summary['d_star_histogram'].values())==len(pairs)


def test_public_labels_are_part_of_depth_zero():
    trans=[[0],[1]]
    assert len(set(partitions(trans,[0,0])[-1]))==1
    assert len(set(partitions(trans,[(0,False),(0,True)])[-1]))==2


def test_selected_archive_members_exclude_raw_rgb_and_future_evaluation(tmp_path):
    data=io.BytesIO()
    prefix='results/97027000_base_V2/'
    with zipfile.ZipFile(data,'w') as archive:
        archive.writestr(prefix+'checkpoint_50000/state.json','{}')
        archive.writestr(prefix+'checkpoint_50000/statistics_8/statistics_index.json','[]')
        archive.writestr(prefix+'training_8/raw.rgb.gz','do not download')
        archive.writestr(prefix+'checkpoint_50000_evaluation/result.json','do not use later data')
        archive.writestr('../../97027000_base_V2/result.json','unsafe')
    data.seek(0)
    entries=extract_selected(data,tmp_path)
    assert len(entries)==2
    assert not wanted('../../97027000_base_V2/result.json')


def blocker_fixture(missing=False):
    h=(0,)
    prefix=EventPrefix()
    words={w for e in WORDS for w in (h+e,e)}
    for i,e in enumerate(WORDS,1):
        if missing and i==2:
            continue
        prefix.certificates[pair_key(h+e,e)]=dict(id=i,result='UNRESOLVED' if i==2 else 'SAME')
    nodes=[dict(history=[],status='representative',outgoing=[(a,[a]) for a in range(5)]),
           dict(history=h,status='provisional',outgoing=[(a,h+(a,)) for a in range(5)],
                belief=dict(existing_candidates=[0],new_state_possible=True),tested_probes=WORDS[1:],evidence_version=31,certificates=[])]
    state=dict(nodes=nodes,representatives=[[]],evidence_version=31,public_labels=[(w,{'goal':False}) for w in words])
    keys={n:{(w,j) for w in words for j in (0,1)} for n in (8,16,32)}
    meta=dict(actual_exposures=1600+sum(n*len(k) for n,k in keys.items()))
    table=dict(start=0,transitions=[[0]*5])
    return state,meta,prefix,table,[[0]],keys


def test_unmeasured_is_not_relabelled_noise_unresolved():
    for missing in (False,True):
        rows=[]
        summary=checkpoint_audit(*blocker_fixture(missing),lambda row:None,rows.append)
        assert summary['provisional_count']==1
        pair=rows[0]
        if missing:
            assert pair['rgb_outcomes'][1]=='NOT_COMPARED'
            assert not pair['statistical_rule_only_blocker']
            assert summary['pair_summary']['unmeasured_saved_RGB_available']==1
        else:
            assert pair['rgb_outcomes'][1]=='UNRESOLVED'
            assert pair['statistical_rule_only_blocker']


def test_prefix_evidence_cannot_include_later_certificates():
    values=list(blocker_fixture())
    values[0]['evidence_version']=30
    import pytest
    with pytest.raises(AssertionError):
        checkpoint_audit(*values,lambda row:None,lambda row:None)


def test_promotion_progress_reset_is_counted_not_called_new_sampling():
    prefix=EventPrefix()
    prefix.accept(dict(event='provisional_created',history=[0]))
    prefix.accept(dict(event='active_probe',history=[0],selected=[1]))
    prefix.accept(dict(event='belief',history=[0]))
    prefix.accept(dict(event='promotion',history=[2]))
    assert prefix.progress_cleared==1 and not prefix.probes[(0,)]


def test_revoked_progress_is_not_counted_again_at_next_promotion():
    for event in ('unmerge','merge_reopened'):
        prefix=EventPrefix()
        prefix.accept(dict(event='provisional_created',history=[0]))
        prefix.accept(dict(event='active_probe',history=[0],selected=[1]))
        prefix.accept(dict(event='belief',history=[0]))
        prefix.accept(dict(event='empirical_merge',history=[0]))
        prefix.accept(dict(event=event,history=[0],reason='not every current candidate has complete evidence'))
        assert not prefix.probes[(0,)]
        prefix.accept(dict(event='promotion',history=[2]))
        assert prefix.progress_cleared==0


def test_promotion_reopening_preserves_progress_until_completed_event():
    prefix=EventPrefix()
    prefix.accept(dict(event='provisional_created',history=[0]))
    prefix.accept(dict(event='active_probe',history=[0],selected=[1]))
    prefix.accept(dict(event='belief',history=[0]))
    prefix.accept(dict(event='empirical_merge',history=[0]))
    prefix.accept(dict(event='merge_reopened',history=[0],reason='new representative not compared; no transitive exclusion'))
    prefix.accept(dict(event='promotion',history=[2]))
    assert prefix.progress_cleared==1 and not prefix.probes[(0,)]

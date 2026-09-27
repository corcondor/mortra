"""Package completed acquisition evidence, without executing an experiment."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import zipfile


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def csv_write(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root, out = args.input, args.output
    out.mkdir(parents=True, exist_ok=False)
    records = read(root/'final_summary/all_results.json')
    by_key = {(r['seed'], r['camera'], r['arm']): r for r in records}
    assert len(by_key) == len(records) == 128
    remote = {str(a['id']): a for a in read(root/'github_artifacts.json')}
    receipts = []
    for file in sorted((root/'all_compact').rglob('result.json')):
        r = read(file)
        key = (r['seed'], r['camera'], r['arm'])
        assert r == by_key[key]
        receipt = read(file.parent/'full_evidence_receipt.json')
        a = remote[receipt['artifact_id']]
        expected_name = f"vs-{key[0]}-{key[1]}-{key[2]}-36301127275"
        assert a['name'] == expected_name and not a['expired']
        assert a['digest'].removeprefix('sha256:') == receipt['artifact_digest']
        assert a['workflow_run']['head_sha'] == 'cb61cb548f07243250b1ea07ebb0d8ff46bd9dae'
        receipts.append(dict(key=key, artifact_id=a['id'], digest=a['digest'],
                             expires_at=a['expires_at'], size_in_bytes=a['size_in_bytes']))
    assert len(receipts) == 128
    frozen_diff = subprocess.check_output([
        'git', '-C', str(args.repo), 'diff', '--name-only',
        'e178b2faefb05e6c579e475df935836aa0a01d5e',
        'cb61cb548f07243250b1ea07ebb0d8ff46bd9dae', '--',
        'experiments/noisy_rgb_discovery', 'tests/test_noisy_rgb_discovery.py',
        'scripts/evaluate_autonomous_game_design_loop.py'], text=True)
    assert not frozen_diff.strip()
    for name in ('summary.json', 'all_results.json', 'paired_conditions.csv'):
        shutil.copyfile(root/'final_summary'/name, out/name)
    for name in ('final_readback.json', 'github_artifacts.json', 'github_run.json',
                 'github_jobs.json', 'unclosed_saved_table_diagnosis.json'):
        shutil.copyfile(root/name, out/name)
    shutil.copyfile(root/'tests/tests.xml', out/'tests.xml')
    with zipfile.ZipFile(out/'compact_evidence.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for f in sorted((root/'all_compact').rglob('*')):
            if f.is_file():
                archive.write(f, f.relative_to(root/'all_compact'))
    images = out/'images'
    images.mkdir()
    for camera in ('base', 'shifted'):
        for arm in ('H', 'V'):
            prefix = f'97027000_{camera}_{arm}'
            source = root/'all_compact'/f'vs-compact-97027000-{camera}-{arm}-36301127275'/prefix
            shutil.copyfile(source/'recorded_input.png', images/(prefix+'.png'))
            shutil.copyfile(source/'recorded_input_provenance.json', images/(prefix+'.json'))
    write(out/'artifact_integrity.json', dict(
        status='PASS', exact_execution_sha='cb61cb548f07243250b1ea07ebb0d8ff46bd9dae',
        matching_compact_results=128, matching_full_artifact_receipts=128,
        frozen_old_files_unchanged=True, receipts=receipts,
        scope='Compact bytes and source manifests checked; full artifact digests matched GitHub metadata. This is not an exhaustive fresh RGB re-hash.',
        independent_raw_audit='All four development V artifacts were independently rehashed/recomputed in run 36300730576.'))
    mechanism_rows, cost_rows = [], []
    metrics = ('acquisition_environment_actions', 'acquisition_exposure_sets',
               'acquisition_cpu_seconds', 'acquisition_wall_seconds', 'peak_memory_bytes')
    for seed in range(97027000, 97027032):
        for camera in ('base', 'shifted'):
            h, v = by_key[seed,camera,'H'], by_key[seed,camera,'V']
            m = dict(seed=seed, camera=camera, status=v['status'],
                     representative_count=v['access_histories'], suffix_count=v['nonempty_suffix_count'])
            m.update(v['mechanisms'])
            m.update({'audit_'+k: value for k, value in v['acquisition_audit'].items()
                      if not isinstance(value, (dict, list))})
            mechanism_rows.append(m)
            c = dict(seed=seed, camera=camera, H_status=h['status'], V_status=v['status'],
                     implementation_error_pair=any(r['status']=='IMPLEMENTATION_ERROR' or r.get('postfreeze_error') for r in (h,v)))
            for metric in metrics:
                c.update({metric+'_H':h[metric], metric+'_V':v[metric], metric+'_V_minus_H':v[metric]-h[metric]})
            cost_rows.append(c)
    csv_write(out/'mechanism_conditions.csv', mechanism_rows)
    csv_write(out/'cost_conditions.csv', cost_rows)
    vrows = [r for r in records if r['arm']=='V']
    audit = lambda key: sum(r['acquisition_audit'][key] for r in vrows)
    mechanism = lambda key: sum(r['mechanisms'].get(key, 0) for r in vrows)
    write(out/'interpretation_denominators.json', dict(
        worlds=32, paired_world_camera_conditions=64,
        implementation_error_conditions=[[97027025,'shifted','H']],
        evaluable_heldout_pairs=0, heldout_accuracy=None, control_success=None,
        wrong_unique_rate=None, unresolved_heldout_rate=None, transition_error=None,
        incomplete_metric_reason='No completed model in either arm; acquisition observations are not heldout tests.',
        V_candidate_set_snapshots=audit('candidate_set_checks'),
        V_true_class_already_represented_snapshots=audit('candidate_set_checks')-audit('true_class_unrepresented'),
        V_true_class_unrepresented_snapshots=audit('true_class_unrepresented'),
        V_false_exclusion_snapshots=audit('candidate_set_false_exclusion_count'),
        V_different_certificate_checks=audit('different_witness_checks'),
        V_spurious_different_witnesses=audit('spurious_split_witnesses'),
        V_suffix_checks=audit('suffix_witness_checks'),
        V_spurious_suffix_witnesses=audit('spurious_suffix_witnesses'),
        V_historical_provisional_assignment_collisions=audit('observed_assignment_false_merge_states'),
        V_conditions_with_historical_collisions=sum(r['acquisition_audit']['observed_assignment_false_merge_states']>0 for r in vrows),
        V_per_condition_mean_candidate_count=statistics.mean(r['acquisition_audit']['mean_candidate_size'] for r in vrows),
        V_per_condition_p95_candidate_count=statistics.mean(r['acquisition_audit']['p95_candidate_size'] for r in vrows),
        candidate_size_note='Mean of 64 per-condition statistics, not pooled p95. Includes the mandatory unresolved preliminary stages.',
        V_queue_entries_at_stop=mechanism('remaining_unresolved'),
        V_fixed_point_conditions=[dict(seed=r['seed'], camera=r['camera'], representatives=r['access_histories'],
            suffixes=r['nonempty_suffix_count'], remaining_unresolved=r['mechanisms']['remaining_unresolved'])
            for r in vrows if r['status']=='INCOMPLETE_UNRESOLVED_FIXED_POINT'],
        V_represented_classes_total=audit('represented_true_classes'),
        V_true_classes_total=audit('true_classes'),
        class_count_note='Sum across separate world-camera runs, not distinct shared global classes; not exact quotient recovery.',
        initial_ambiguity_note='8 and 16 stages are always UNRESOLVED by the fixed rule. Initial ambiguity is an operational counter, not raw-visual ambiguity frequency.',
        probe_count_note='probe_depth_* and probe_action_* count selected adaptive test suffixes. Full replay actions/exposures are recorded separately; consistency_probes also recorded.',
        readback_failures_not_experimental='A premature local readback before the archive download completed and a malformed reporting query were corrected. No acquisition condition was rerun.'
    ))
    tools = out/'readback_tools'
    tools.mkdir()
    for name in ('noisy_rgb_vs_final_readback.py', 'noisy_rgb_vs_inspect_unclosed.py', 'noisy_rgb_vs_package_report.py'):
        shutil.copyfile(Path(__file__).parent/name, tools/name)
    write(out/'data_sha256.json', {str(f.relative_to(out)): hashlib.sha256(f.read_bytes()).hexdigest()
                                for f in sorted(out.rglob('*')) if f.is_file()})
    print(json.dumps(dict(output=str(out), matching_receipts=len(receipts), compact_runs=128), indent=2))


if __name__ == '__main__':
    main()

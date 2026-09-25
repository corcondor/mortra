"""Reporting-only recovery of run 36140039826, with no fit or candidate calls.

The original extra byte-equality gate failed. Preserve that failure and both
outputs, prove whether rankings/tie classes changed, then summarize Stage 2 only.
No numerical tolerance is used to decide whether a ranking changed.
"""
import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.frontier_v13.protocol import ROOT, SEEDS, read, write

RUN = '36140039826'
HEAD = '4847a287723e8ce4c7387c8539038c55144a55fe'


def api(path, binary=False):
    b = subprocess.check_output(['gh', 'api', 'repos/corcondor/mortra/'+path])
    return b if binary else json.loads(b)


def ordered_tie_classes(rows):
    bins = defaultdict(list)
    for row in rows:
        value = float(row['prediction']); assert math.isfinite(value)
        bins[value].append(int(row['row_id']))
    return [sorted(bins[v]) for v in sorted(bins, reverse=True)]


def compare(smoke, repeated):
    proof = {'byte_identical': True, 'files': {}, 'primary_ranking_and_tie_classes_equal': True}
    for name in ('row_predictions.csv', 'secondary_predictions.csv', 'parent_rank_metrics.csv', 'feature_importance.csv'):
        blobs = [(Path(path)/name).read_bytes() for path in (smoke, repeated)]
        tables = [list(csv.DictReader(io.StringIO(b.decode('utf-8')))) for b in blobs]
        assert len(tables[0]) == len(tables[1])
        differences = defaultdict(lambda: dict(count=0, max_abs=0.))
        for a, b in zip(*tables):
            assert a.keys() == b.keys()
            for k in a:
                if a[k] == b[k]:
                    continue
                assert k in ('prediction', 'mse', 'eligible_precision8', 'top5_recall', 'value'), (name, k)
                x, y = float(a[k]), float(b[k]); assert math.isfinite(x) and math.isfinite(y)
                key = a.get('model', '')+':'+a.get('target', '')+':'+k
                differences[key]['count'] += 1
                differences[key]['max_abs'] = max(differences[key]['max_abs'], abs(x-y))
        groups_checked = 0
        changed_groups = []
        changed_classifications = 0
        if name in ('row_predictions.csv', 'secondary_predictions.csv'):
            groups = [defaultdict(list), defaultdict(list)]
            for dest, table in zip(groups, tables):
                for row in table:
                    key = (row['parent_id'], row['model'], row['feature_set'], row.get('target', 'reward'))
                    dest[key].append(row)
            assert groups[0].keys() == groups[1].keys()
            for key in groups[0]:
                same_order = ordered_tie_classes(groups[0][key]) == ordered_tie_classes(groups[1][key])
                if not same_order:
                    changed_groups.append(list(key))
                if name == 'row_predictions.csv':
                    assert same_order, key
                if key[-1] in ('eligibility', 'positive'):
                    changed_classifications += sum((float(a['prediction']) >= .5) != (float(b['prediction']) >= .5)
                        for a, b in zip(groups[0][key], groups[1][key]))
                groups_checked += 1
        same = blobs[0] == blobs[1]
        proof['byte_identical'] &= same
        proof['files'][name] = dict(byte_equal=same, source_sha256=[hashlib.sha256(b).hexdigest() for b in blobs],
            rows=len(tables[0]), numeric_differences=dict(differences), exact_order_groups_checked=groups_checked,
            changed_secondary_order_groups=changed_groups, changed_secondary_classifications=changed_classifications)
    return proof


def recover(base):
    base = Path(base); base.mkdir(parents=True, exist_ok=False)
    status = api('actions/runs/'+RUN)
    assert status['head_sha'] == HEAD and status['conclusion'] == 'failure'
    jobs = api(f'actions/runs/{RUN}/jobs?per_page=100')['jobs']
    assert all(next(j for j in jobs if j['name'] == name)['conclusion'] == 'success'
               for name in ['stage0', 'stage1', *[f'stage2 ({s})' for s in SEEDS]])
    artifacts = api(f'actions/runs/{RUN}/artifacts?per_page=100')['artifacts']
    downloads = []
    for name, directory in [('v13-dataset', base/'dataset'), ('v13-smoke', base/'smoke'),
                            *[(f'v13-fold-{s}', base/'folds'/str(s)) for s in SEEDS]]:
        item = next(a for a in artifacts if a['name'] == name)
        b = api(f'actions/artifacts/{item["id"]}/zip', True)
        directory.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            for n in z.namelist():
                assert (directory/n).resolve().is_relative_to(directory.resolve())
            z.extractall(directory)
        downloads.append(dict(name=name, id=item['id'], sha256=hashlib.sha256(b).hexdigest()))
    proof = compare(base/'smoke', base/'folds/2101')
    proof.update(original_run=RUN, original_head=HEAD, original_run_conclusion='failure',
        recovery_scope='saved-prediction aggregation only', fitting_calls=0, new_candidate_evaluations=0,
        selected_predictions='unchanged Stage 2 outputs, as originally prescribed', artifact_hashes=downloads,
        explanation='Byte equality was an extra harness condition, not algorithmic equality; no tolerance substituted for ranking/tie checks.')
    write(base/'reproducibility_diagnostic.json', proof)
    print(json.dumps(proof, indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(); p.add_argument('mode', choices=('recover', 'annotate'))
    p.add_argument('--base', type=Path, required=True); p.add_argument('--report', type=Path)
    args = p.parse_args()
    if args.mode == 'recover':
        recover(args.base)
        return
    report = args.report
    proof = read(args.base/'reproducibility_diagnostic.json')
    write(report/'reproducibility_diagnostic.json', proof)
    original_files = subprocess.check_output(['git', 'diff', '--name-only', HEAD, '--',
        'experiments/frontier_v13', 'scripts/evaluate_frontier_v13_structural_edit_prediction.py',
        'tests/test_frontier_v13.py', 'docs/research/FRONTIER-V13-PREREGISTRATION-20260925.md'], cwd=ROOT, text=True)
    assert not original_files.strip()
    metrics = read(report/'metrics.json')
    metrics['reproducibility'] = proof
    metrics['original_training_run'] = RUN
    metrics['reporting_only_run'] = __import__('os').environ.get('GITHUB_RUN_ID')
    write(report/'metrics.json', metrics)
    note = ('## 実行記録に関する注記\n\n'
        '学習run 36140039826は、全8 fold完了後に追加のバイト一致検査で停止しました。'
        'これは未達のまま記録します。主予測の差は最大約7.1e-14でした。'
        '保存済みのStage 1とStage 2について、主予測の全70 parent/model/feature-set群の順位と同点集合が'
        '厳密に一致することを別検査しました。副予測の順位不一致は別途記録し、同一とは扱っていません。'
        '許容誤差で順位差を消してはいません。'
        '学習、特徴、設定、候補評価を一切変更・再実行せず、元のStage 2予測だけを集計しました。'
        '実行環境による数値差と整合しますが、具体的な原因の同定はしていません。\n\n')
    path = report/'FINAL_REPORT.ja.md'
    path.write_text(note+path.read_text(encoding='utf-8'), encoding='utf-8')
    write(report/'reporting_source_sha.json', dict(files={
        n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in (
            'scripts/report_frontier_v13_saved_predictions.py',
            '.github/workflows/frontier-v13-report-saved-predictions.yml')}))


if __name__ == '__main__':
    main()

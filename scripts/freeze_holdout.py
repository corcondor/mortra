# -*- coding: utf-8 -*-
"""holdout を、中身を見る前に固定する。

167問（北大138＋東大29）は、既に誤答の確認・条件抽出規則の追加・
目標選択の改善・guard の設計に使った。純粋な未見テストではない。
以後 development / regression set と呼ぶ。

新しく収集した大学を source holdout として固定する。
manifest をハッシュで封じ、開けた記録を残す。

    python scripts/freeze_holdout.py --freeze
    python scripts/freeze_holdout.py --verify
"""
import glob
import hashlib
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, 'data', 'holdout-manifest.json')

# 開発に使った大学。これらは dev/regression
DEV_UNIVERSITIES = {'10001', '10261'}


def collect():
    dev, holdout = [], []
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'mathexamtest', '*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        code = str(d.get('code'))
        for p in d['problems']:
            if not p.get('mathml'):
                continue
            entry = {'id': p['id'], 'univ': code, 'name': d.get('name'), 'year': p.get('year')}
            (dev if code in DEV_UNIVERSITIES else holdout).append(entry)
    return dev, holdout


def digest(entries) -> str:
    payload = json.dumps(sorted(e['id'] for e in entries), ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def verify_frozen_partition(current, frozen):
    """Verify only the IDs frozen in the manifest.

    Corpus ingestion may add records after a split is frozen.  Those records are
    deliberately left unassigned; they must not silently enlarge the holdout or
    make the original split unverifiable.
    """
    current_by_id = {entry['id']: entry for entry in current}
    frozen_ids = set(frozen['ids'])
    missing = sorted(frozen_ids - set(current_by_id))
    selected = [current_by_id[problem_id] for problem_id in frozen_ids if problem_id in current_by_id]
    valid = not missing and len(selected) == frozen['count'] and digest(selected) == frozen['digest']
    extra = sorted(set(current_by_id) - frozen_ids)
    return {
        'valid': valid,
        'missing': missing,
        'extra': extra,
        'selected_count': len(selected),
    }


def main() -> int:
    dev, holdout = collect()
    if '--verify' in sys.argv:
        if not os.path.exists(MANIFEST):
            print('manifest が無い。--freeze を先に走らせる')
            return 1
        m = json.load(open(MANIFEST, encoding='utf-8'))
        dev_check = verify_frozen_partition(dev, m['dev'])
        hold_check = verify_frozen_partition(holdout, m['holdout'])
        print(
            f"dev      {dev_check['selected_count']:4d} 問  "
            f"frozen digest {'一致' if dev_check['valid'] else '不一致'}"
        )
        print(
            f"holdout  {hold_check['selected_count']:4d} 問  "
            f"frozen digest {'一致' if hold_check['valid'] else '不一致'}"
        )
        if dev_check['extra'] or hold_check['extra']:
            print(
                f"unassigned additions  dev={len(dev_check['extra'])} "
                f"holdout-source={len(hold_check['extra'])}（固定splitには含めない）"
            )
        missing = dev_check['missing'] + hold_check['missing']
        if missing:
            print(f"\n※ 固定IDが {len(missing)} 問欠落している。manifestまたはsourceを確認する。")
        return 0 if (dev_check['valid'] and hold_check['valid']) else 1

    by_univ = {}
    for e in holdout:
        by_univ.setdefault(e['univ'], {'name': e['name'], 'count': 0})
        by_univ[e['univ']]['count'] += 1

    manifest = {
        'note': '167問（北大138＋東大29）は開発に使用済み。dev/regression set。'
                '汎化の主張には holdout を使う。',
        'dev': {'count': len(dev), 'digest': digest(dev),
                'universities': sorted(DEV_UNIVERSITIES),
                'ids': sorted(e['id'] for e in dev)},
        'holdout': {'count': len(holdout), 'digest': digest(holdout),
                    'kind': 'source_holdout',
                    'universities': by_univ,
                    'ids': sorted(e['id'] for e in holdout)},
        'rules': [
            'holdout の本文・解答を実装前に読まない',
            'holdout で失敗した問題を見て規則を足さない',
            '足した場合、その問題は dev へ移し holdout から外す',
            '結果は dev と holdout を分けて報告する',
        ],
    }
    with open(MANIFEST, 'w', encoding='utf-8') as h:
        json.dump(manifest, h, ensure_ascii=False, indent=2)

    print(f'dev      {len(dev):4d} 問  digest {manifest["dev"]["digest"]}')
    print(f'holdout  {len(holdout):4d} 問  digest {manifest["holdout"]["digest"]}')
    print('\nholdout の内訳（大学名だけ。問題文は見ていない）:')
    for code, info in sorted(by_univ.items()):
        print(f'  {code}  {info["name"]:16s} {info["count"]:4d} 問')
    print(f'\n→ {os.path.relpath(MANIFEST, ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

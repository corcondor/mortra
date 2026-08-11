# -*- coding: utf-8 -*-
"""自分が出した答えを、収集した解答と突き合わせる。

これが無いと「解けた」と言えない。
判定は三段階に分ける。曖昧なものを正解に混ぜない。

    一致        解答本文の中に、こちらの答えが見つかった
    不一致      解答本文はあるが、こちらの答えが見つからない
    照合不能    解答が手元にない、または本文が取れない

「照合不能」を分母から外さない。外すと数字が嘘になる。

    python scripts/grade_pastexam.py
"""
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalize(text: str) -> str:
    """全角・空白・LaTeX の飾りを落として、比較できる形にする"""
    t = text
    t = re.sub(r'\\(left|right|displaystyle|,|;|!|quad|qquad)', '', t)
    t = re.sub(r'\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}', r'(\1)/(\2)', t)
    t = re.sub(r'\\sqrt\s*\{([^{}]*)\}', r'sqrt(\1)', t)
    t = re.sub(r'[{}\s$]', '', t)
    t = t.translate(str.maketrans(
        '０１２３４５６７８９＋－＝（）／　',
        '0123456789+-=()/ ',
    ))
    return t.lower()


def answer_forms(latex_answer):
    """答えの書き方の揺れを吸収する。複数解は個別に見る"""
    values = latex_answer if isinstance(latex_answer, list) else [latex_answer]
    out = []
    for v in values:
        s = normalize(str(v))
        if not s or s in {'0', '1'}:   # 短すぎるものは偶然当たるので使わない
            continue
        out.append(s)
    return out


def main() -> int:
    solved_path = os.path.join(ROOT, 'data', 'pastexam-solved.json')
    if not os.path.exists(solved_path):
        print('先に scripts/solve_pastexam.py を走らせる')
        return 1
    solved = json.load(open(solved_path, encoding='utf-8'))

    # 解答本文を読み込む
    index_path = os.path.join(ROOT, 'data', 'answers', 'index.json')
    texts: dict[str, str] = {}
    if os.path.exists(index_path):
        try:
            import pdfplumber
        except ImportError:
            pdfplumber = None
        for entry in json.load(open(index_path, encoding='utf-8')):
            body = ''
            fp = os.path.join(ROOT, 'data', 'answers', f"{entry['id']}.{'pdf' if entry['isPdf'] else 'html'}")
            if not os.path.exists(fp):
                continue
            try:
                if entry['isPdf'] and pdfplumber:
                    with pdfplumber.open(fp) as pdf:
                        body = '\n'.join(p.extract_text() or '' for p in pdf.pages)
                elif not entry['isPdf']:
                    body = re.sub(r'<[^>]*>', ' ', open(fp, encoding='utf-8', errors='replace').read())
            except Exception:
                continue
            if not body:
                continue
            norm = normalize(body)
            for cover in entry['covers']:
                texts.setdefault(cover['problemId'], '')
                texts[cover['problemId']] += norm

    stats = Counter()
    details = []
    for item in solved:
        pid = item.get('mathexamtest_id') or item['id']
        body = texts.get(pid)
        if not body:
            stats['照合不能'] += 1
            continue
        forms = answer_forms(item.get('answer'))
        if not forms:
            stats['照合不能'] += 1
            continue
        hit = any(f in body for f in forms)
        stats['一致' if hit else '不一致'] += 1
        details.append({**item, 'matched': hit})

    total = len(solved)
    print(f'\n答えを出した {total} 問の照合\n')
    for k, v in stats.most_common():
        print(f'  {k:10s} {v:5d}  {100 * v / max(1, total):5.1f}%')
    checkable = stats['一致'] + stats['不一致']
    if checkable:
        print(f'\n照合できた {checkable} 問での一致率: '
              f'{stats["一致"]}/{checkable} = {100 * stats["一致"] / checkable:.1f}%')
    print('\n※ 照合不能を分母から外していない。外すと数字が嘘になる。')

    with open(os.path.join(ROOT, 'data', 'pastexam-graded.json'), 'w', encoding='utf-8') as h:
        json.dump(details, h, ensure_ascii=False, indent=2)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

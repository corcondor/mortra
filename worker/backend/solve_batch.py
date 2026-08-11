# -*- coding: utf-8 -*-
"""標準入力から問題の束を受け取り、答えを返す。

Windows では ProcessPoolExecutor を打ち切りのたびに作り直すとハンドルが尽きる
（PermissionError: WinError 5）。束ごとに別プロセスで走らせ、
親側で subprocess の timeout を使う方が壊れない。
"""
import json
import sys

import cas_solver as C

payload = json.loads(sys.stdin.read())
out = []
for item in payload:
    try:
        r = C.solve_request({'relations': item.get('relations', []), 'goal': item.get('goal', '')})
    except Exception as exc:
        r = {'status': 'exception', 'detail': repr(exc)[:120]}
    out.append({'id': item.get('id'), **r})
sys.stdout.write(json.dumps(out, ensure_ascii=False, default=str))

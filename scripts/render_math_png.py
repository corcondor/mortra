#!/usr/bin/env python3
"""
render_math_png.py
==================
LaTeX 数式を含む問題文を高品質 PNG 画像にレンダリングする。
Playwright + KaTeX (CDN) を使用。

使い方:
  python render_math_png.py --statement "問題文" --answer "答え" --topic "整数論" --out out.png
"""
import sys, os, argparse, tempfile, textwrap, html as html_lib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

CARD_W = 1200   # px (Twitter OGP 最適: 1200×628)
CARD_H = 628


def build_html(statement: str, answer: str, topic: str, score: float) -> str:
    esc_stmt   = html_lib.escape(statement)
    esc_ans    = html_lib.escape(answer)
    esc_topic  = html_lib.escape(topic)
    score_str  = f"{score:.1f}" if score else ""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    width:{CARD_W}px; height:{CARD_H}px; overflow:hidden;
    background: linear-gradient(135deg,#05050f 0%,#0d0820 50%,#060616 100%);
    font-family: -apple-system,"Helvetica Neue",Arial,sans-serif;
    color:#fff;
    display:flex; flex-direction:column; justify-content:center;
    padding:56px 72px;
    position:relative;
  }}
  /* 背景グラデーション装飾 */
  body::before {{
    content:''; position:absolute; inset:0; z-index:0;
    background:
      radial-gradient(ellipse 70% 60% at 15% 30%, rgba(120,40,200,.25) 0%, transparent 60%),
      radial-gradient(ellipse 60% 50% at 85% 20%, rgba(10,100,220,.20) 0%, transparent 60%),
      radial-gradient(ellipse 50% 60% at 70% 90%, rgba(200,40,120,.15) 0%, transparent 60%);
  }}
  .inner {{ position:relative; z-index:1; }}

  /* ヘッダー */
  .header {{
    display:flex; align-items:center; gap:12px; margin-bottom:32px;
  }}
  .brand {{
    font-size:15px; font-weight:700; letter-spacing:.08em;
    color:rgba(255,255,255,.35);
  }}
  .topic {{
    font-size:13px; font-weight:600; letter-spacing:.06em;
    color:rgba(10,132,255,.9);
    background:rgba(10,132,255,.12);
    border:1px solid rgba(10,132,255,.3);
    border-radius:20px; padding:3px 12px;
  }}
  .score {{
    margin-left:auto; font-size:13px; color:rgba(255,255,255,.3);
    font-variant-numeric:tabular-nums;
  }}

  /* 問題文 */
  .statement {{
    font-size:22px; line-height:1.75; color:rgba(255,255,255,.88);
    margin-bottom:28px;
    /* auto-wrap long lines */
    word-break:break-word;
  }}

  /* 答え */
  .answer-row {{
    display:flex; align-items:baseline; gap:12px;
  }}
  .answer-label {{
    font-size:12px; font-weight:700; letter-spacing:.1em;
    color:rgba(255,255,255,.3); text-transform:uppercase; white-space:nowrap;
  }}
  .answer {{
    font-size:20px; color:rgba(48,209,88,.85); line-height:1.5;
  }}

  /* KaTeX 調整 */
  .katex {{ font-size:1em !important; color:inherit; }}
  .katex-display {{ margin:.5em 0; overflow-x:visible; }}
</style>
</head>
<body>
<div class="inner">
  <div class="header">
    <span class="brand">✦ Sakumon</span>
    <span class="topic">{esc_topic}</span>
    {f'<span class="score">score {score_str}</span>' if score_str else ''}
  </div>
  <div class="statement" id="stmt">{esc_stmt}</div>
  {f'''
  <div class="answer-row">
    <span class="answer-label">Ans</span>
    <span class="answer" id="ans">{esc_ans}</span>
  </div>
  ''' if answer else ''}
</div>
<script>
  renderMathInElement(document.body, {{
    delimiters:[
      {{left:'$$',right:'$$',display:true}},
      {{left:'$',right:'$',display:false}},
      {{left:'\\\\[',right:'\\\\]',display:true}},
      {{left:'\\\\(',right:'\\\\)',display:false}},
    ],
    throwOnError:false,
    trust:true,
  }});
</script>
</body>
</html>"""


def render(statement: str, answer: str, topic: str, score: float, out_path: str):
    html_content = build_html(statement, answer, topic, score)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page(viewport={"width": CARD_W, "height": CARD_H})
        page.set_content(html_content, wait_until="domcontentloaded")
        # KaTeX CDN の読み込みと描画を待つ
        page.wait_for_timeout(2_500)
        page.screenshot(path=out_path, clip={"x":0,"y":0,"width":CARD_W,"height":CARD_H})
        browser.close()

    print(f"✅ PNG 保存: {out_path}", flush=True)
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--statement", required=True)
    parser.add_argument("--answer",    default="")
    parser.add_argument("--topic",     default="数学")
    parser.add_argument("--score",     type=float, default=0.0)
    parser.add_argument("--out",       required=True)
    args = parser.parse_args()

    render(args.statement, args.answer, args.topic, args.score, args.out)

"""Build a self-contained review gallery for engineering-geometry artifacts."""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _record_markup(output: Path, record: dict) -> str:
    part_id = record["part_id"]
    manifest_path = output / part_id / f"{part_id}.json"
    if not manifest_path.exists():
        return ""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts", {})
    svg_name = artifacts.get("svg")
    if not svg_name:
        return ""

    geometry = manifest["geometry"]
    operators = record["operator_histogram"]
    active_ops = sum(1 for count in operators.values() if count)
    links = []
    for label, key in (("SVG", "svg"), ("DXF", "dxf"), ("STEP", "step"), ("STL", "stl")):
        filename = artifacts.get(key)
        if filename:
            links.append(
                f'<a href="{escape(part_id)}/{escape(filename)}">{label}</a>'
            )
    return f"""
      <article class="part">
        <header>
          <div>
            <span>{escape(record['role'].upper())}</span>
            <h2>{escape(manifest['title'])}</h2>
          </div>
          <strong>{'VERIFIED' if record['passed'] else 'FAILED'}</strong>
        </header>
        <img src="{escape(part_id)}/{escape(svg_name)}" alt="{escape(manifest['title'])} technical drawing">
        <dl>
          <div><dt>Volume</dt><dd>{geometry['volume_mm3']:,.3f} mm3</dd></div>
          <div><dt>Faces</dt><dd>{geometry['face_count']}</dd></div>
          <div><dt>Edges</dt><dd>{geometry['edge_count']}</dd></div>
          <div><dt>Active operators</dt><dd>{active_ops} / 8</dd></div>
        </dl>
        <nav>{''.join(links)}</nav>
      </article>
    """


def build_gallery(output: Path) -> Path:
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    records = "".join(_record_markup(output, record) for record in summary["records"])
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MORTRA Engineering Geometry Basis</title>
  <style>
    :root {{ color-scheme: dark; --ink: #edf5f5; --muted: #90a0a4; --line: #263238; --cyan: #69ddea; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #050708; color: var(--ink); font: 14px/1.6 Inter, system-ui, sans-serif; }}
    main {{ width: min(1500px, calc(100% - 40px)); margin: 0 auto; padding: 64px 0 96px; }}
    .intro {{ display: grid; grid-template-columns: 1fr auto; gap: 40px; align-items: end; padding-bottom: 36px; border-bottom: 1px solid var(--line); }}
    .intro span, .part header span {{ color: var(--cyan); font: 11px/1.4 ui-monospace, monospace; }}
    h1 {{ max-width: 820px; margin: 10px 0 14px; font-size: clamp(38px, 6vw, 74px); line-height: 1.02; letter-spacing: 0; }}
    .intro p {{ max-width: 780px; margin: 0; color: var(--muted); font-size: 16px; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, minmax(110px, 1fr)); border: 1px solid var(--line); }}
    .summary div {{ min-width: 120px; padding: 20px; border-right: 1px solid var(--line); }}
    .summary div:last-child {{ border-right: 0; }}
    .summary strong {{ display: block; color: var(--cyan); font: 30px/1 ui-monospace, monospace; }}
    .summary small {{ color: var(--muted); }}
    .parts {{ display: grid; gap: 72px; padding-top: 72px; }}
    .part {{ border-top: 1px solid var(--line); padding-top: 22px; }}
    .part header {{ display: flex; justify-content: space-between; gap: 24px; align-items: start; margin-bottom: 20px; }}
    .part h2 {{ margin: 5px 0 0; font-size: 23px; letter-spacing: 0; }}
    .part header strong {{ color: #75e9b9; font: 11px/1.4 ui-monospace, monospace; }}
    .part img {{ display: block; width: 100%; max-height: 82vh; object-fit: contain; background: #fff; border: 1px solid #bac5c9; }}
    dl {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 0; border-bottom: 1px solid var(--line); }}
    dl div {{ padding: 16px 0; }}
    dt {{ color: var(--muted); font-size: 11px; }}
    dd {{ margin: 3px 0 0; font: 14px/1.4 ui-monospace, monospace; }}
    nav {{ display: flex; gap: 8px; padding-top: 14px; }}
    nav a {{ color: var(--ink); border-bottom: 1px solid #53656b; padding: 5px 0; margin-right: 16px; text-decoration: none; font: 11px/1.4 ui-monospace, monospace; }}
    nav a:hover {{ color: var(--cyan); }}
    @media (max-width: 760px) {{
      main {{ width: min(100% - 24px, 680px); padding-top: 36px; }}
      .intro {{ grid-template-columns: 1fr; }}
      .summary {{ grid-template-columns: 1fr; }}
      .summary div {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .summary div:last-child {{ border-bottom: 0; }}
      dl {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="intro">
      <div>
        <span>EXECUTABLE GEOMETRY / 2026-08-31</span>
        <h1>One geometric basis, many engineering parts.</h1>
        <p>Every drawing is derived from the same exact B-rep as its STEP and STL files. Orthographic views, hidden lines, sections and dimensions are outputs of the same construction DAG.</p>
      </div>
      <div class="summary">
        <div><strong>{summary['basis']['basis_size']}</strong><small>generic operators</small></div>
        <div><strong>{summary['passed_cases']}/{summary['cases']}</strong><small>valid solids</small></div>
        <div><strong>{len(summary['new_operator_families_needed_by_holdouts'])}</strong><small>new holdout operators</small></div>
      </div>
    </section>
    <section class="parts">{records}</section>
  </main>
</body>
</html>
"""
    gallery_path = output / "gallery.html"
    gallery_path.write_text(html, encoding="utf-8")
    previews = []
    for record in summary["records"]:
        part_id = record["part_id"]
        manifest_path = output / part_id / f"{part_id}.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        svg_name = manifest.get("artifacts", {}).get("svg")
        if svg_name:
            previews.append(
                f'<figure><img src="{escape(part_id)}/{escape(svg_name)}" '
                f'alt="{escape(manifest["title"])}"><figcaption>{escape(part_id)}</figcaption></figure>'
            )
    contact_sheet = f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #050708; color: #edf5f5; font: 12px ui-monospace, monospace; }}
main {{ display: grid; width: 1600px; height: 1000px; grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(3, minmax(0, 1fr)); gap: 14px; padding: 18px; }}
figure {{ display: grid; min-width: 0; grid-template-rows: minmax(0, 1fr) 24px; margin: 0; border: 1px solid #314047; background: #fff; }}
img {{ display: block; width: 100%; height: 100%; object-fit: contain; }}
figcaption {{ display: grid; place-items: center start; background: #0b1013; padding: 0 8px; color: #9bdbe3; }}
</style></head><body><main>{''.join(previews)}</main></body></html>"""
    (output / "contact-sheet.html").write_text(contact_sheet, encoding="utf-8")
    return gallery_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output",
        nargs="?",
        default="artifacts/engineering-geometry-basis-20260831",
    )
    args = parser.parse_args()
    gallery = build_gallery(ROOT / args.output)
    print(gallery)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

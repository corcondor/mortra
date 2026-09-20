"""Reading the alphabet out of raster images, with the fragment deciding the geometry.

The question this answers is the blunt one: can MORTRA read letters, without
anything that already knows what a letter looks like. No neural network, no
OpenCV, no tesseract, no font file, no template of a glyph image anywhere. The
input is a grid of black and white cells. The output is a letter.

What the run measures, and why each part is here:

* **accuracy** on held-out sizes, stroke widths, positions, two pen shapes and a
  ragged edge -- none of which the twenty-six reference descriptions were built
  from;
* **a second style**, `NARROW`, whose letters have different proportions and
  which no reference is ever built from. This is the experiment that matters.
  A description made of coordinates cannot survive it; a description made of
  relations can, and the two numbers are reported side by side;
* **the frame ablation**. The fragment's relations are invariant under every
  similarity, rotations included, so relations among a glyph's own strokes
  cannot tell N from Z. Orientation comes from relations against the
  normalising box. Removing them shows exactly that, and the collision it
  produces is named;
* **the structure-only ablation**, which is the part that is counted rather
  than decided: holes, corners, strokes, degrees;
* **the exact-match rate**: how often the recovered description equals the
  reference outright, rather than merely being nearest to it.

    python scripts/run_alphabet_reading.py --output reports/alphabet
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction as F
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_alphabet as alphabet
from math_os_prototype import geometry_raster as raster
from math_os_prototype import geometry_reading as reading


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# ---------------------------------------------------------------------------
# The images the reader is shown
# ---------------------------------------------------------------------------

CONDITIONS = [
    # name,            style,     height, radius,  pen,      speckle, origin
    ("roman-48-round", "ROMAN", 48, F(3, 2), "round", 0, (3, 3)),
    ("roman-72-round", "ROMAN", 72, F(5, 2), "round", 0, (7, 4)),
    ("roman-96-bold", "ROMAN", 96, F(4), "round", 0, (2, 9)),
    ("roman-36-hairline", "ROMAN", 36, F(1), "round", 0, (2, 2)),
    ("roman-72-square-pen", "ROMAN", 72, F(5, 2), "square", 0, (4, 6)),
    ("roman-72-ragged-1-in-16", "ROMAN", 72, F(5, 2), "round", 16, (4, 4)),
    ("roman-72-ragged-1-in-8", "ROMAN", 72, F(5, 2), "round", 8, (4, 4)),
    ("roman-72-ragged-1-in-4", "ROMAN", 72, F(5, 2), "round", 4, (4, 4)),
    ("narrow-48-round", "NARROW", 48, F(3, 2), "round", 0, (3, 3)),
    ("narrow-72-round", "NARROW", 72, F(5, 2), "round", 0, (7, 4)),
    ("narrow-96-bold", "NARROW", 96, F(4), "round", 0, (2, 9)),
    ("narrow-72-square-pen", "NARROW", 72, F(5, 2), "square", 0, (4, 6)),
    ("narrow-72-ragged-1-in-8", "NARROW", 72, F(5, 2), "round", 8, (4, 4)),
]

READERS = ("relations", "relations_without_the_frame", "structure_only", "coordinates")


def picture(letter, style, height, radius, pen, speckle, origin):
    """One image, drawn from a definition and then handed over as cells alone."""
    strokes = (alphabet.ROMAN if style == "ROMAN" else alphabet.NARROW)[letter]
    bitmap = alphabet.draw(strokes, height=height, radius=radius, at=origin,
                           pen=pen)
    if speckle:
        bitmap = raster.speckle(bitmap, seed=height+len(letter), rate=speckle)
    return bitmap


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def evaluate(shelves, grid=1):
    """Every condition, every letter, every reader, from one recovery per image."""
    rows, failures = [], []
    predictions = {name: Counter() for name in READERS}
    exact = Counter()
    for name, style, height, radius, pen, speckle, origin in CONDITIONS:
        started = time.perf_counter()
        scores = Counter()
        letters = alphabet.ROMAN if style == "ROMAN" else alphabet.NARROW
        for letter in letters:
            bitmap = picture(letter, style, height, radius, pen, speckle, origin)
            try:
                glyph = reading.recover(bitmap, grid=grid)
            except Exception as trouble:                       # a refusal is a result
                failures.append({"condition": name, "letter": letter,
                                 "refused": str(trouble)})
                continue
            answers = {
                "relations": reading.description(glyph),
                "relations_without_the_frame": reading.description(glyph, frame=False),
                "structure_only": reading.description(glyph, use_relations=False),
                "coordinates": alphabet.coordinate_template(glyph),
            }
            for reader in READERS:
                shelf = shelves[reader]
                mine = answers[reader]
                ranked = sorted(((reading.agreement(mine, other)
                                  if reader != "coordinates"
                                  else _jaccard(mine, other), other_letter)
                                 for other_letter, other in shelf.items()),
                                key=lambda pair: (-pair[0], pair[1]))
                got = ranked[0][1]
                predictions[reader][got] += 1
                if got == letter:
                    scores[reader] += 1
                else:
                    failures.append({"condition": name, "reader": reader, "letter": letter,
                                     "read_as": got, "score": str(ranked[0][0]),
                                     "runner_up": ranked[1][1] if len(ranked) > 1 else None})
                if reader == "relations" and mine == shelf.get(letter):
                    exact[name] += 1
        rows.append({"condition": name, "style": style, "height": height,
                     "stroke_radius_px": str(radius), "pen": pen,
                     "one_edge_cell_in": speckle or None, "letters": len(letters),
                     "correct": {reader: scores[reader] for reader in READERS},
                     "exact_description_match": exact[name],
                     "seconds": round(time.perf_counter()-started, 1)})
        say("  ".join([f"{name:<22}"]+[f"{reader[:11]} {scores[reader]:2d}/{len(letters)}"
                                       for reader in READERS]))
    return rows, failures, predictions, exact


def _jaccard(left, right):
    union = len(left | right)
    return F(len(left & right), union) if union else F(0)


# ---------------------------------------------------------------------------
# Letters this repository did not draw
# ---------------------------------------------------------------------------

TYPEFACES = [("Arial", r"C:\Windows\Fonts\arial.ttf"),
             ("Consolas", r"C:\Windows\Fonts\consola.ttf"),
             ("Calibri", r"C:\Windows\Fonts\calibri.ttf"),
             ("Times New Roman", r"C:\Windows\Fonts\times.ttf")]


def from_a_typeface(letter, path, size=96):
    """A letter rasterised from a real font file, handed over as cells alone.

    Pillow reads the font and draws the letter; the reader is given the picture
    and nothing else. This is out of scope for the alphabet -- these typefaces
    have curves, and the descriptions were built from straight strokes -- and it
    is here because it is the only test in the run whose letters this repository
    did not draw.
    """
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(path, size)
    image = Image.new("L", (size*2, size*2), 255)
    ImageDraw.Draw(image).text((size//2, size//4), letter, font=font, fill=0)
    pixels = image.load()
    black = {(x, image.height-1-y) for x in range(image.width) for y in range(image.height)
             if pixels[x, y] < 128}                    # one threshold, and it is stated
    if not black:
        return None
    lo_x, lo_y = min(c[0] for c in black)-2, min(c[1] for c in black)-2
    moved = {(c[0]-lo_x, c[1]-lo_y) for c in black}
    return raster.Bitmap(max(c[0] for c in moved)+3, max(c[1] for c in moved)+3, moved)


def typefaces(shelf, output, grid=1):
    """Read A to Z out of real typefaces, and report what came back for each."""
    results = []
    for name, path in TYPEFACES:
        if not Path(path).exists():
            results.append({"typeface": name, "skipped": "the font is not on this machine"})
            continue
        right, answers, shown, got = 0, [], [], []
        for letter in sorted(alphabet.ROMAN):
            bitmap = from_a_typeface(letter, path)
            try:
                answer = reading.read(bitmap, shelf, grid=grid)
                shown.append(bitmap)
                got.append(redraw(answer["glyph"]))
                read_as = answer["letter"]
            except Exception as trouble:               # a refusal is a result
                read_as = "refused: "+str(trouble)[:40]
            right += read_as == letter
            answers.append(read_as if read_as != letter else ".")
        results.append({"typeface": name, "read": f"{right}/26",
                        "answers": "".join(a if len(a) == 1 else "!" for a in answers)})
        if name == "Arial":
            raster.write_png(output/"typeface-arial-as-shown.png",
                             raster.paste(shown, columns=13))
            raster.write_png(output/"typeface-arial-as-recovered.png",
                             raster.paste(got, columns=13), cell=2)
        say(f"  {name:<16} {right:2d}/26  {results[-1]['answers']}")
    return results


# ---------------------------------------------------------------------------
# Pictures
# ---------------------------------------------------------------------------

def redraw(glyph, *, unit=7, radius=F(6, 5)):
    """What was recovered, drawn back out: the strokes the reader ended up with."""
    segments = [((glyph.vertices[a][0]*unit+radius+1, glyph.vertices[a][1]*unit+radius+1),
                 (glyph.vertices[b][0]*unit+radius+1, glyph.vertices[b][1]*unit+radius+1))
                for a, b in glyph.edges]
    if not segments:
        return raster.Bitmap(1, 1)
    width = int(max(max(s[0][0], s[1][0]) for s in segments)+radius+2)
    height = int(max(max(s[0][1], s[1][1]) for s in segments)+radius+2)
    return raster.render(segments, radius, width, height)


def sheets(output, grid=1):
    """Two contact sheets: what the reader was shown, and what it recovered."""
    shown, recovered = [], []
    for letter in alphabet.ROMAN:
        bitmap = picture(letter, "ROMAN", 48, F(3, 2), "round", 0, (3, 3))
        shown.append(bitmap)
        recovered.append(redraw(reading.recover(bitmap, grid=grid)))
    a = raster.paste(shown, columns=13)
    b = raster.paste(recovered, columns=13)
    raster.write_png(output/"alphabet-as-shown.png", a, cell=2)
    raster.write_png(output/"alphabet-as-recovered.png", b, cell=2)
    narrow = [picture(letter, "NARROW", 48, F(3, 2), "round", 0, (3, 3))
              for letter in alphabet.NARROW]
    raster.write_png(output/"alphabet-narrow-as-shown.png",
                     raster.paste(narrow, columns=13), cell=2)
    return ["alphabet-as-shown.png", "alphabet-as-recovered.png",
            "alphabet-narrow-as-shown.png"]


def one_letter(output, letter="R", grid=1):
    """The three stages for a single letter, so the pipeline can be looked at."""
    bitmap = picture(letter, "ROMAN", 72, F(5, 2), "round", 0, (4, 4))
    body = raster.components(bitmap)[0]
    skeleton = raster.Bitmap(bitmap.width, bitmap.height, raster.thin(body))
    glyph = reading.recover(bitmap, grid=grid)
    sheet = raster.paste([bitmap, skeleton, redraw(glyph, unit=13, radius=F(5, 2))],
                         columns=3, gap=8)
    raster.write_png(output/f"stages-{letter}.png", sheet, cell=2)
    return {"file": f"stages-{letter}.png", "letter": letter, "glyph": glyph.summary(),
            "constructions": glyph.notes["constructions"]}


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--grid", type=int, default=1)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    say("building the twenty-six descriptions from the definitions alone")
    shelves = {
        "relations": alphabet.library(grid=arguments.grid),
        "relations_without_the_frame": alphabet.library(grid=arguments.grid, frame=False),
        "structure_only": alphabet.library(grid=arguments.grid, use_relations=False),
        "coordinates": alphabet.template_library(grid=arguments.grid),
    }

    say("reading")
    rows, failures, predictions, exact = evaluate(shelves, grid=arguments.grid)

    totals = {reader: sum(row["correct"][reader] for row in rows) for reader in READERS}
    attempted = sum(row["letters"] for row in rows)
    roman = [row for row in rows if row["style"] == "ROMAN"]
    narrow = [row for row in rows if row["style"] == "NARROW"]

    say("reading letters this repository did not draw")
    fonts = typefaces(shelves["relations"], output, grid=arguments.grid)

    say("drawing the contact sheets")
    pictures = sheets(output, grid=arguments.grid)
    stages = one_letter(output, grid=arguments.grid)

    bare = shelves["relations_without_the_frame"]
    letters = sorted(bare)
    collisions = [f"{first} and {second}"
                  for index, first in enumerate(letters) for second in letters[index+1:]
                  if bare[first] == bare[second]]

    report = {
        "environment": {
            "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                  text=True).stdout.strip(),
            "python": sys.version.split()[0], "platform": platform.platform()},
        "what_this_is": {
            "input": "a bitmap: a grid of black and white cells, and nothing else",
            "output": "a letter of the alphabet",
            "references": "twenty-six descriptions built from the ROMAN stroke definitions. "
                          "No reference is built from any image, and none is built from NARROW",
            "not_used": ["no neural network and no learned parameter of any kind",
                         "no OpenCV: worker/backend/geometry_diagram_grounder.py has a "
                         "cv2.matchTemplate label reader built on a bundled Hershey font, and "
                         "it is not imported here",
                         "no tesseract: math_os_prototype/x_math_analyzer.py calls pytesseract, "
                         "and it is not imported here",
                         "no font file, and no image of a glyph as a template"]},
        "the_alphabet": {
            "shape": "straight strokes only, because a circular arc is not rational and the "
                     "fragment is exact over QQ. B, O and S are polygons",
            "box": "six units tall, left edge at x = 0, integer grid points",
            "styles": {"ROMAN": "the references are built from these definitions",
                       "NARROW": "the same twenty-six letters with different proportions: bars "
                                 "at different heights, bowls recut, widths changed. No "
                                 "reference is ever built from these"}},
        "readers": {
            "relations": "the reader of this work: the multiset of relations of the fragment "
                         "that hold of the recovered strokes, each decided by atom_holds",
            "relations_without_the_frame": "the same, with every relation against the "
                                           "normalising box removed",
            "structure_only": "holes, corners, strokes and degrees -- the counted part alone",
            "coordinates": "the control: the same recovery, the same snap, then the recovered "
                           "corners and strokes compared as coordinates. No predicate decided"},
        "conditions": rows,
        "totals": {reader: f"{totals[reader]}/{attempted}" for reader in READERS},
        "by_style": {
            "ROMAN": {reader: f"{sum(r['correct'][reader] for r in roman)}/"
                              f"{sum(r['letters'] for r in roman)}" for reader in READERS},
            "NARROW": {reader: f"{sum(r['correct'][reader] for r in narrow)}/"
                               f"{sum(r['letters'] for r in narrow)}" for reader in READERS}},
        "exact_description_match": {
            "counts": dict(exact),
            "of": attempted//2 if attempted else 0,
            "means": "how often the recovered description equalled the reference outright. "
                     "Every other decision was made by taking the nearest description, which "
                     "is a nearest-neighbour rule over exactly-decided facts, not a proof"},
        "prediction_histogram": {reader: dict(predictions[reader].most_common())
                                 for reader in READERS},
        "letters_this_repository_did_not_draw": {
            "what": "A to Z rasterised from real font files at 96px and read with the same "
                    "twenty-six descriptions, which were built from straight-stroke "
                    "definitions and from nothing else",
            "out_of_scope": "these typefaces have curves; the alphabet does not. The number "
                            "is reported because the letters are not this repository's",
            "how_the_font_is_used": "Pillow reads the font and draws the letter. The reader "
                                    "is given the cells and never the outline",
            "results": fonts},
        "collisions_without_the_frame": {
            "pairs": collisions,
            "why": "coll, para, perp and cong are invariant under every similarity, rotations "
                   "included, so a description built only from relations among a glyph's own "
                   "strokes cannot tell a letter from a turned copy of it"},
        "failures": failures,
        "pictures": pictures,
        "stages": stages,
        "not_claimed": [
            "MORTRA does not find the ink. Binarisation, connected components, hole counting, "
            "Zhang-Suen thinning, spur pruning and the polyline cut are integer image "
            "processing, and they are what decides where the strokes are",
            "the bounding box, the normalisation and the snap to the lattice are ordering and "
            "rounding, which the equality fragment cannot express. All of the tolerance to "
            "measurement noise lives in the snap",
            "geometry_ink.on_closed_segment, used when the reference arrangement decides "
            "whether a crossing lies on both strokes, is a Python inequality on exact "
            "rationals, not a certified atom",
            "the match is nearest-description, which is a one-nearest-neighbour rule. What is "
            "true is that there are no learned parameters and no training data",
            "coll, para, perp and cong are invariant under every similarity, so relations "
            "among a glyph's own strokes cannot distinguish a letter from a rotated copy. The "
            "frame supplies orientation, and the ablation reports what that is worth",
            "the alphabet is straight-stroke. A typeface with real curves is out of scope for "
            "this round, and nothing here was tested on one",
            "the images are rendered by this repository, except the typeface section. Two pen "
            "shapes, a ragged edge, a second set of proportions and four real fonts widen "
            "that, but no scan and no photograph was read",
            "the typeface numbers are not an OCR benchmark. They are letters drawn by someone "
            "else, read by descriptions of a straight-stroke alphabet, and they are reported "
            "because they are the only letters here this repository did not draw"],
        "total_seconds": round(time.perf_counter()-started, 1),
    }
    (output/"result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    say(f"relations {report['totals']['relations']}  "
        f"coordinates {report['totals']['coordinates']}")
    say(f"ROMAN {report['by_style']['ROMAN']}")
    say(f"NARROW {report['by_style']['NARROW']}")
    say(f"wrote {output/'result.json'}")


if __name__ == "__main__":
    main()

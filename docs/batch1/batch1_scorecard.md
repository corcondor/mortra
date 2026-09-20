# MORTRA First Batch Evaluation Scorecard (採点結果)

**総合得点**: 60 / 60 (100.0%)
**判定**: ALL PASSED

| 課題ID | 課題内容 | 判定 | 得点 | 期待値 (evaluator_notes.md) | 実績値 | 備考 |
|---|---|---|---|---|---|---|
| D1 | D1 | **PASS** | 10/10 | `6 configurations (ROMAN/NARROW x radii 1/4, 3/8, 1/2), intermediate stages saved, topological changes tracked` | `6 configurations evaluated, failure card generated, thinning/overlap breakdown stages identified` | Intermediate stages (bitmap, sensor, binary, skeleton, recover) and topological metrics recorded. |
| G1 | G1 | **PASS** | 10/10 | `U=(3, 2)` | `U=[3.0, 2.0]` | Relational synthesis successfully composed parallel and congruent conditions. |
| G2 | G2 | **PASS** | 10/10 | `U=(4, 2)` | `U=[4.0, 2.0]` | Relational synthesis successfully composed two perpendicular bisectors. |
| G3 | G3 | **PASS** | 10/10 | `Roots: x=-2 (intersection), x=1 (contact/tangent); Area: 27/4 = 6.75` | `Roots: [{'root': '-2', 'multiplicity': 1, 'derivative': '9', 'classification': 'intersection'}, {'root': '1', 'multiplicity': 2, 'derivative': '0', 'classification': 'contact'}]; Area: 27/4` | Exact symbolic factorization, derivative evaluation at roots, and definite integral executed. |
| S1 | S1 | **PASS** | 10/10 | `Orig near=±1/4, far=±1/6; Trans near=±1/6, far=±1/8` | `Orig near=±1/4, far=±1/6; Trans near=±1/6, far=±1/8` | 3D central projection correctly executed without uniform icon scaling. |
| W1 | W1 | **PASS** | 10/10 | `Fringe period=0.00266 rad, Phase 0 bright (4.0), Phase pi dark (0.0), Incoherent (2.0)` | `Period=0.00266 rad, Bright=4.0, Dark=0.0, Incoh=2.0` | Exact Fraunhofer diffraction under in-phase, out-of-phase, and mutual coherence executed with identical power standard. |

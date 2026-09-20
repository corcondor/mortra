# MORTRA Second Batch Evaluation Scorecard (採点結果)

**総合得点**: 40 / 40 (100.0%)
**判定**: ALL PASSED

| 課題ID | 課題内容 | 判定 | 得点 | 期待値 | 実績値 | 備考 |
|---|---|---|---|---|---|---|
| S2 | S2 | **PASS** | 10/10 | `Area = 64/9 (~7.1111), Umbra overlap computed` | `Area = 7.1111, Overlap = 1.7778` | Exact analytical perspective projection and area match. |
| W2 | W2 | **PASS** | 10/10 | `rc = 0.4256 mm, Low-pass & High-pass filtered images, Inversion & Power conservation` | `rc = 0.4256 mm, Inversion Err = 8.8e-33, Power Ratio = 1.000000` | 4f optical system accurately simulated with inverted output and exact power conservation. |
| W3 | W3 | **PASS** | 10/10 | `Single phase hologram with sharp ring at 8mm, triangle at 12mm, 3-depth evaluation` | `Defocus separation pass: True, Ring C=17.4, Tri C=19.3` | Multi-plane WGS phase retrieval demonstrated clear depth separation and wave optics consistency. |
| R1 | R1 | **PASS** | 10/10 | `Directional light Case A vs Case B separately, multi-resolution stippling & coverage evaluation` | `Case A dots=16000 (corr=0.97), Case B dots=16000 (corr=0.95)` | Directional light comparison completed with high stipple-to-shading correlation. |

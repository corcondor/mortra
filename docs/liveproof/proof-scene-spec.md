# Proof Scene 仕様

## 何であるか

LiveProof は証明動画ではない。

> 証明・式・図・説明・カメラが、同じ意味グラフの異なる射影である。

図が「たまたま横に置いてある」状態をやめる。これがこれまでの不自然さの正体だった。

## 一段の構造

```
Beat
  claim            この段で主張すること
  premises         使った根拠
  certificate      どう確かめたか
  focus            注目する意味ID
  visual action    図に何を足すか / 何を光らせるか
  formula action   何を書くか
  narration        人が読む一行
  camera           どこから見るか
  timing           秒 または スクロール位置
```

**証明の1段 = 図の1段 = 文の1段。** 三つが同じ Beat から出るので、配置を人が決める余地がない。

## 経路を変えると全部が再構成される

証明 DAG は複数の経路を保つ。経路を選び直すと、

```
diagram / formula / explanation / camera / animation
```

がすべて再コンパイルされる。「座標ではなく幾何的に説明して」は、
別の生成ではなく経路の選択になる。

## 実装

| ファイル | 役割 |
|---|---|
| `lib/proof-scene.ts` | 証明 DAG → Beat 列。前向き推論・相異条件・座標での数値検証 |
| `lib/mortra/vision/visual-ir.ts` | 表示の意味。Three.js / SVG を知らない |
| `lib/mortra/world/world-types.ts` | 一つの意味状態から成果物が派生する |
| `app/proof/page.tsx` | Beat を再生。1080×1920 の書き出しに対応 |
| `app/api/frame/route.ts` | canvas → PNG。動画化の配管 |

## 守る規則

- **図を単独で生成する機能を作らない。** 図は必ず証明の段から出す
- 表示要素は必ず semantic ID を持つ。持たない要素は `auditScene` が落とす
- 証明済みでないものを証明済みに見せない。`certificateBadge` に状態を出す
- 骨組み（三角形の三辺）は証明の段ではない。最初から立てておく

## 測る

```
proof_diagram_sync_rate           主張のある段のうち、図が対応した割合
cross_representation_consistency  表現をまたいで同じ意味を追えた割合
```

実装は `visual-ir.ts` の同名の関数。

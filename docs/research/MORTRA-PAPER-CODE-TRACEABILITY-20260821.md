# MORTRA 論文・公式コード・実装対応監査

日付: 2026-08-21

## 目的

論文を取得したこと、論文の考え方を参考にしたこと、公式コードを実行したこと、
MORTRA の採点経路へ接続したこと、論文スコアを再現したことを区別する。
この区別をしない限り、実装の不足も得点差の原因も特定できない。

## 監査結果

| 系統 | 一次資料の核 | MORTRA の現状 | 判定 |
|---|---|---|---|
| AlphaGeometry | DD+AR が証明グラフを閉じ、LM が補助構成を提案 | 公式 checkout はあるが、公式 DDAR/LM は現行採点経路に未接続 | 参照のみ |
| Newclid/Yuclid | DD と AR、native proof replay | `yuclid_native_verifier.py` が公式実行系を直接使用 | native 接続済み |
| FormalGeo | GDL、前向き hypergraph、後向き AND/OR goal decomposition | 公式2.2.2を別processで実行し、JGEX構成DAGと型付きgoal frontierをJSON交換 | native bridge接続済み（得点増は未確認） |
| GCLC | Area、Wu、Groebner、証明 TeX | executable と Newclid bridge を直接実行 | native bridge 接続済み |
| HAGeo | 数値 incidence で補助点を選ぶ六つの候補族、`N=6` の軌道、Pass@K | 六候補族と N/K 軌道を独立再構成。公式 full code は未公開 | 独立再構成 |
| Sheaf-ADMM | overlapping local views と sheaf 制約下の ADMM 合意 | MORTRA 用に独立適応したが、公式学習器と論文タスクは未再現 | 部分適応 |

## HAGeo の論文仕様と実装差

論文が明記する補助点候補は次の六族である。

1. 三本以上の直線が交わる点。
2. 直線と円を合わせて三対象以上が交わる点。
3. 中点が別の直線または円上にある場合。
4. 点対称点が別の直線または円上にある場合。
5. 垂足が別の直線上にある場合。
6. 無作為構成。

MORTRA の `numerical_incidence_auxiliary.py` は 1--5 と、既存点が複数 locus に乗る
場合を実装している。無作為候補は探索 policy 側に存在する。ただし HAGeo 論文の
IMO-30 `K=4096`、HAGeo-409 `K=2048/8192` と同一計算量ではない。また公式 full code
が公開されていないため、候補分布、数値閾値、DDAR 最適化を同一にした完全再現とは呼ばない。

## 現在主張できる数値

- HAGeo-409 から固定した89問に対する認証済み証明集合の和: **53/89 = 59.55%**。
- IMO-AG-30 の開発 portfolio union: **25/30 = 83.33%**。
- Newclid/Yuclid all-AR の同一30問 baseline: **17/30**。

`53/89` と `25/30` は単一 solver の一回の Pass@K ではない。複数の native 証明書を
問題名で重複除去した能力集合である。また繰り返し開発に使ったため、今後これを未見汎化値と
呼ばない。HAGeo 論文の70.2%とも直接比較しない。

## 得点差の原因

1. AlphaGeometry、AutoGPS、Euclean などは clone または設計参考で、採点経路へ入っていない。
   FormalGeoは今回runtime接続したが、生成した代数義務のNewclid/GCLC replayが未完了である。
2. HAGeo は論文規模の K に達しておらず、公式候補分布と DDAR 高速化も未取得である。
3. Newclid と GCLC は接続済みだが、中間義務を交換する共通形式は一部だけである。
4. MMT/Sheaf-ADMM は事実輸送を増やしたが、未知補助構成を供給せず、固定難例で追加正答0だった。
5. 同じ89問を反復開発に用いたため、認証済み能力下限と未見汎化を分離する新しい frozen split が必要である。

## 実装上の是正

`audit_research_integrations.py` は、checkout、実行接続、独立再構成、論文方法、
benchmark artifact を別々に記録する。artifact が存在しない source について、スコア再現済みと
扱わない。これにより「論文を読んだ」「コードを置いた」「採点経路へ接続した」「得点が上がった」
を機械的に混同しない。

## 次の実装順

1. FormalGeoの `Eq` frontierをNewclid/GCLCの実行可能な距離多項式へ可逆変換する。
2. JGEXからFormalGeoへの未対応constructorを増やし、固定未見cohortでelaboration率を測る。
3. HAGeo paper-spec policyと現行policyを、同一N/K・同一seed・同一Yuclidで比較する。
4. 新しいfrozen cohortを一度だけ評価し、portfolio能力と未見改善を分離する。

## 一次資料

- HAGeo: https://arxiv.org/abs/2512.00097
- AlphaGeometry: https://github.com/google-deepmind/alphageometry
- Newclid: https://github.com/Newclid/Newclid
- FormalGeo: https://github.com/FormalGeo/FormalGeo
- GCLC: https://github.com/janicicpredrag/gclc
- Sheaf-ADMM: https://github.com/SakanaAI/sheaf-admm

# MORTRA 公開ベータのUI・配信・SEO方針

## UI

参考: https://x.com/L_go_mrk/status/2087505627535053281?s=20

AI-native UIの参考例にある Thinking、Task Rows、Flowchart、Streaming Text を、
MORTRAでは次のように置き換える。

- Thinking: 非公開の思考文ではなく、実行した射、未解決義務、検証結果を表示する。
- Task Rows: 意味解析、型形成、探索、証明、検証の進捗を表示する。
- Flowchart: 証明DAGと、どのbackendがどの義務を閉じたかを表示する。
- Result: 問題、図、解答、証明書を一つの `ProblemArtifact` として表示する。

## プレローンチ運用

参考: https://x.com/L_go_mrk/status/2087502859793277333?s=20 / https://early.tools

early.toolsのカード構造から、公開時に最低限必要な情報を採用する。

- 一文で分かる用途
- Public Beta / Freeなどの利用状態
- 実際に操作できるデモ
- 更新日と変更履歴
- 再現可能な代表ベンチマーク
- 提出用の短い動画とOG画像

登録や掲載依頼は自動実行しない。公開ページ、デモ、OG画像、説明文が揃ってから行う。

## 実装から説明を生成する

参考: https://codewiki.google/ および
https://developers.googleblog.com/ja/introducing-code-wiki-accelerating-your-code-understanding/

Code Wikiの重要点は、説明を一度書いて放置せず、リポジトリ更新に追従し、説明から
定義ファイルへ戻れることである。MORTRAでは次を目標にする。

```text
typed IR / morphism / verifier source
  -> API schema
  -> research page
  -> interactive proof graph
  -> exact source link
```

数値や能力表は、対応するテスト成果物とコミットを失った時点で公開ページから外す。

## SEOとSNS

参考: https://x.com/askOkara/status/2089366669613531602?s=20

チャネルごとの施策を混ぜず、次を個別に測る。

- 検索: `数学AI`, `記号推論`, `数学問題生成`, `自動作問`, `幾何証明`, `増減表`
- X: 15秒前後の実演からサイト遷移まで
- 研究記事: 問題、方法、結果、失敗、再現手順を一記事にする
- 製品ページ: Try MORTRAの開始率、完了率、成果物表示率

現在の製品実装には canonical URL、sitemap、robots、SoftwareApplication構造化データ、
OG画像を含める。自動投稿や外部アカウント操作は、投稿内容と公開権限を確認した別工程にする。

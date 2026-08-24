# MORTRA 自律融合の継続実行と可視化 2026-08-20

## 原理

融合生成は、既存Atlasに該当familyがないことを失敗条件にしない。二つ以上の親問題を
固定端点として字句・構文解析から型付き意味IRへ持ち上げ、有限の型付き中間射を探索する。
ただし、型検査だけ通った候補と、backendで証明された公開問題を同じ状態として扱わない。

## 実装

1. APIの90秒内探索で既知の実行経路を探す。
2. 解けなければ`generation_jobs`へ親、frontier、型付き候補、未閉鎖義務を永続化する。
3. GitHub Actionsのresearch sweepとjob-statusのedge resumeが同じjobを次roundへ進める。
4. 再読込時はjob IDへ再接続し、研究候補と探索統計を復元する。
5. UIは`worker_active`, `round`, `search_depth`, `states_checked`,
   `frontier_count`, `unclosed_goals`を表示する。
6. 未検証候補は`RESEARCH CANDIDATE / 検証継続中 / 答え未確定`と表示し、
   検証済み問題へ偽装しない。

初期の既存問題・Atlas読込みにも5秒ごとのheartbeatを追加した。長い同期処理中でも、
停止と処理継続を画面上で区別できる。

## 実ブラウザ検証

親Aに積分の最小化、親Bに整数の整除を入力した。これは既存の単一familyへ直接落ちない
組合せである。

- 90秒の同期探索後、job `633bea09-054b-4c8f-9481-ecc59ced7013`へ移行。
- 再読込後も同じjobへ接続。
- 観測時点: round 1、depth 4、849状態検査、実行可能goal 2、frontier 6。
- 型付き候補`CommonInvariant[IntegralFunctional, Polynomial]`と2本の
  `InvariantProjection`を表示。
- backend証明は未完了であり、公開問題には昇格していない。

ログ全件を毎pollで追加していたためReact keyが衝突し、同じ警告が132件発生する欠陥が
見つかった。remote logを安定IDで重複排除し、trace IDを単調増加させた。修正後の再接続
検証ではconsole error 0件だった。

永続化した探索状態をそのままpoll応答へ載せていたため、849個の型付き項を含む応答が
1,088,161 byteになっていた。DBに完全状態を保持したまま、UI応答ではgoal、件数、最大12件の
frontierだけを返すprojectionへ変更した。同じjobの応答は15,079 byteとなり、約98.6%削減した。
画面に必要なround、depth、849状態、実行可能goal 2、frontier 6は保持される。

## 結果と限界

「Atlasにないため赤字で停止」は解消し、候補、frontier、未閉鎖義務を保存して継続できる。
一方、この入力対では人間向けの成立問題と模範解答までは生成できていない。現段階で
成立したのは、未知構造を捨てずに型付き研究候補として継続し、処理状態を可視化するところまでである。
任意の二問から必ず非自明な検証済み問題を生成できた、という結果ではない。

## 検証

- worker test: 82/82 pass
- MMT/HAGeo関連unit test: 18/18 pass
- Next.js production build: pass
- 実ブラウザ: job再接続、候補表示、telemetry更新、console error 0

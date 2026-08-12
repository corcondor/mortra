# MORTRA

**One structure. Many representations.**

MORTRAは、自然言語・TeX・MathMLを型付き数学構造へ変換し、独自のCAS、記号証明、
不等式、幾何、構造探索backendで検証する数学システムです。証明・発見・作問・図・Web表現は
別々の出力ではなく、同じsemantic stateのprojectionであり、検証済み候補を推論へ戻します。

現在の中心経路は外部の数学AIや外部LLMを必要としません。
AlphaGeometry / AlphaGeometry2は設計研究上の歴史的参考であり、runtime依存ではありません。

## Architecture

```text
                           Reasoning
                               <->
Natural language / TeX -> Typed Semantic State <- Diagram / Data
                         /        |        \
                Discovery    Generation    Experience
                         \        |        /
                          Verification
                               -> Reasoning
```

## Setup

1. Supabaseで`supabase/schema.sql`を実行します。
2. `.env.local.example`を`.env.local`へ複製し、Supabaseの値を設定します。
3. 開発サーバーを起動します。

```powershell
npm install
npm run dev
```

既定URLは`http://localhost:3002`です。

## Required environment

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`

X投稿機能を使う場合だけ、X APIの4変数が必要です。長時間構造探索Workerでは
`SUPABASE_URL`と`SUPABASE_SERVICE_ROLE_KEY`を使います。

## Verification

```powershell
cd worker
npm ci
npm test
npm run build
```

semantic geometry feedback loop:

```powershell
npm run test:visual-loop
npm run experiment:visual-loop
```

benchmarkの正本、測定の分類、現在の未達は`docs/MORTRA-STATE.md`を参照してください。

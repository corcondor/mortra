# MORTRA

**One structure. Many representations.**

MORTRAは、自然言語・TeX・MathMLを型付き数学構造へ変換し、独自のCAS、記号証明、
不等式、幾何、構造探索backendで検証して、証明・説明・図・Web表現へ移す数学システムです。

現在の中心経路は外部の数学AIや外部LLMを必要としません。
AlphaGeometry / AlphaGeometry2は設計研究上の歴史的参考であり、runtime依存ではありません。

## Architecture

```text
Natural language / TeX / MathML
  -> Discourse IR / Problem IR
  -> Semantic Kernel
  -> typed representation routing
  -> MORTRA-owned CAS / proof / inequality / geometry / discovery backends
  -> certificate and verification status
  -> Proof Scene / Visual IR
  -> explanation / diagram / Web / 3D
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

benchmarkの正本、測定の分類、現在の未達は`docs/MORTRA-STATE.md`を参照してください。

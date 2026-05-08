# Math Web

macOS Spotlight × Apple glassmorphism の数学問題ビューア。

## セットアップ

### 1. Supabase プロジェクト作成

1. https://supabase.com → 新規プロジェクト作成
2. SQL Editor で `supabase/schema.sql` を実行
3. Settings → API から URL と anon key をコピー

### 2. 環境変数

```bash
cp .env.local.example .env.local
# .env.local を編集して Supabase / DeepSeek / X API の値を貼り付け
```

### 3. SQLite → Supabase 移行

```bash
pip install supabase python-dotenv
$env:SUPABASE_URL="https://xxx.supabase.co"
$env:SUPABASE_SERVICE_KEY="eyJ..."   # service_role key
python scripts/migrate.py
```

### 4. フロント起動

```bash
cd sakumon-station
npm install
npm run dev
# → http://localhost:3002
```

## 使い方

| 操作 | アクション |
|------|-----------|
| ⌘K / Ctrl+K | 検索バーにフォーカス |
| ↑↓ | カード選択移動 |
| Enter | 詳細シートを開く |
| Esc / 下スワイプ | シートを閉じる |
| チップ | トピック絞り込み |

## デプロイ

```bash
# Vercel に push するだけ
# 環境変数を Vercel Dashboard で設定
vercel --prod
```

必須環境変数:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `DEEPSEEK_API_KEY`
- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

ローカル任意:

- `DEEPSEEK_MODEL`（未設定時は `deepseek-v4-pro`）
- `DEEPSEEK_HEALTH_MODEL`（未設定時は軽量確認用の `deepseek-v4-flash`）
- `DEEPSEEK_MAX_TOKENS`（未設定時は `4000`）
- `X_CONFIG_PATH`（既存のX投稿JSON設定をローカルだけで使う場合）
- `PYTHON_BIN`（SQLite同期などPythonスクリプトをローカルで使う場合。未設定時は `python`）
- `ENABLE_VERCEL_PYTHON_ACTIONS=1`（Vercel で Python と `scripts/*.py` を明示的に使う場合のみ）

画像プレビューは Next.js の `next/og` でPNG生成します。X投稿もNode実装なので、本番ではPythonは不要です。Vercel では `.vercelignore` により `scripts/` と `*.py` を除外しているため、Pythonを使うSQLite同期だけがデフォルトでローカル専用です。

## 今後の拡張 (MVP後)

- [ ] Three.js / React Three Fiber で 3D カードフリップ
- [ ] Supabase Realtime でリアルタイム更新
- [ ] 問題追加/編集画面 (管理者用)
- [ ] X投稿ボタン
- [ ] 全文検索 (Supabase FTS)

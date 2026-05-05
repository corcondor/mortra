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
# .env.local を編集して SUPABASE_URL と ANON_KEY を貼り付け
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
cd math-web
npm install
npm run dev
# → http://localhost:3000
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

## 今後の拡張 (MVP後)

- [ ] Three.js / React Three Fiber で 3D カードフリップ
- [ ] Supabase Realtime でリアルタイム更新
- [ ] 問題追加/編集画面 (管理者用)
- [ ] X投稿ボタン
- [ ] 全文検索 (Supabase FTS)

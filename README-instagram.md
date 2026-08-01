# Instagram / X 自動投稿

## 今どこまでできているか

| | 状態 |
|---|---|
| 動画の書き出し（アームの作図） | ✅ `/robot?export=1` → ffmpeg → 1080×1920 MP4 |
| 公開 URL への設置 | ✅ Supabase Storage の `public-assets`（外部から 200 で取得できることを確認済み） |
| Instagram 投稿スクリプト | ✅ `scripts/instagram-publish.mjs`（3段階の公開フロー実装済み） |
| **Instagram のトークン** | ❌ **本人の操作が要る**（下の手順） |
| X 投稿 | ✅ `app/api/post/route.ts` に実装済み・認証情報も設定済み |

トークンさえ入れば、コマンド1本で投稿が飛ぶ状態。

---

## Instagram を自動投稿できるようにする手順

Instagram には**公式の自動投稿 API がある**（Content Publishing API）。
非公式なブラウザ操作は規約違反かつ BAN リスクがあるので使わない。

### 1. アカウントをプロアカウントにする

Instagram アプリ → 設定 → アカウントの種類とツール →
**プロアカウントに切り替える**（ビジネス or クリエイター）。

> API で投稿できるのはプロアカウントだけ。個人アカウントでは不可。

### 2. Facebook ページと連携する

Instagram アプリ → 設定 → シェアと連携 → Facebook →
ページを作って連携する（ページは新規で構わない）。

### 3. Meta の App を作る

https://developers.facebook.com/apps/ → アプリを作成 → 「ビジネス」

作ったアプリに **Instagram Graph API** を追加し、
以下の権限を付ける:

```
instagram_basic
instagram_content_publish
pages_show_list
pages_read_engagement
```

### 4. アクセストークンと IG ユーザー ID を取る

Graph API Explorer（https://developers.facebook.com/tools/explorer/）で
上の権限を選んでトークンを発行し、

```
GET /me/accounts                     → ページ ID がわかる
GET /{page-id}?fields=instagram_business_account  → IG ユーザー ID がわかる
```

短期トークンは1時間で切れるので、**長期トークン（60日）**に交換する:

```
GET /oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={app-id}
  &client_secret={app-secret}
  &fb_exchange_token={短期トークン}
```

### 5. .env.local に入れる

```
IG_ACCESS_TOKEN=（長期トークン）
IG_USER_ID=（IG ユーザー ID）
```

> 値をここに書かないこと。`.env.local` は git 管理外。

---

## 投稿する

```bash
# 1. 動画を公開ストレージへ
node scripts/upload-public-asset.mjs export/video/robot_ninepoint_reel.mp4

# 2. 出た公開URLを渡して投稿
node scripts/instagram-publish.mjs \
  --video "https://.../robot_ninepoint_reel.mp4" \
  --caption "$(cat export/video/CAPTIONS.md | sed -n '/案 A/,/^```$/p')"
```

`--dry` を付けると認証情報の確認だけして投稿しない。

---

## 守らないと失敗する制約

動画（リール）:
- **9:16**（1080×1920）
- **5〜90秒**
- **H.264 の MP4**、音声があれば AAC
- URL が**外部から取得できる**こと

> 書き出している MP4 は 1080×1920 / 30秒 / H.264 なので条件を満たす。

その他:
- 1 アカウント **24時間で 25 投稿**まで（リール・ストーリー込み）
- 動画の処理に 30秒〜数分。`status_code` が `FINISHED` になるまで待つ必要がある
- 形式が違うと **error code 24 で黙って失敗**する

---

## 定期投稿にする

GitHub Actions で回せる。`sakumon-station` には既に Supabase の
シークレットが入っているので、`IG_ACCESS_TOKEN` と `IG_USER_ID` を
足すだけでよい。

長期トークンは 60 日で切れるので、更新も自動化するなら
`GET /oauth/access_token?grant_type=fb_exchange_token` を月1で叩く。

---

## 出典

- [Instagram Reels API Publishing Guide (2026)](https://postproxy.dev/blog/instagram-reels-api-publishing-guide/)
- [Instagram Graph API: Complete Developer Guide for 2026](https://elfsight.com/blog/instagram-graph-api-complete-developer-guide-for-2026/)
- [Instagram Graph APIで自動投稿（旅アトリーチ）](https://tabiato.co.jp/biz/blog/instagram-api-content-publishing/)
- [Instagramリール動画の自動投稿（自動化は金曜日！）](https://cenleaf.com/blog/instagram-reel-auto-post-dm/)

#!/usr/bin/env python3
"""
X (Twitter) 投稿スクリプト
使い方: python post_to_x.py --text "問題文" [--image-path path.png]
"""
import sys, os, json, argparse
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CONFIG_PATH = "C:/Users/81808/.openclaw/workspace/youtube/config.json"

def _strip_latex_dollars(text: str) -> str:
    """
    LaTeX の $ デリミタを除去する。
    X (Twitter) は $SYMBOL をキャッシュタグと解釈して 403 を返すため。
    数式自体（\frac, \pmod など）はそのまま残す。
    """
    import re
    # $$ ... $$ → 中身だけ
    text = re.sub(r'\$\$([\s\S]*?)\$\$', r'\1', text)
    # $ ... $ → 中身だけ
    text = re.sub(r'\$((?:[^$\\]|\\.)*?)\$', r'\1', text)
    # \[ ... \] → 中身だけ
    text = re.sub(r'\\\[([\s\S]*?)\\\]', r'\1', text)
    # \( ... \) → 中身だけ
    text = re.sub(r'\\\(([\s\S]*?)\\\)', r'\1', text)
    return text.strip()

def post(text: str, image_path: str | None = None) -> dict:
    with open(CONFIG_PATH, encoding='utf-8') as f:
        cfg = json.load(f)
    x = cfg['x_api']

    try:
        import tweepy
    except ImportError:
        return {"ok": False, "error": "tweepy がインストールされていません: pip install tweepy"}

    client = tweepy.Client(
        consumer_key=x['consumer_key'],
        consumer_secret=x['consumer_secret'],
        access_token=x['access_token'],
        access_token_secret=x['access_token_secret'],
    )

    media_ids = None
    if image_path and os.path.exists(image_path):
        auth = tweepy.OAuth1UserHandler(
            x['consumer_key'], x['consumer_secret'],
            x['access_token'], x['access_token_secret'],
        )
        api_v1 = tweepy.API(auth)
        media  = api_v1.media_upload(image_path)
        media_ids = [media.media_id]

    # $ をキャッシュタグと誤認識させないためにデリミタを除去
    safe_text = _strip_latex_dollars(text)
    resp     = client.create_tweet(text=safe_text, media_ids=media_ids)
    tweet_id = resp.data['id']
    url      = f"https://x.com/i/web/status/{tweet_id}"
    return {"ok": True, "tweet_id": tweet_id, "url": url}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--text',       required=True)
    parser.add_argument('--image-path', default=None)
    args = parser.parse_args()

    result = post(args.text, args.image_path)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result['ok'] else 1)

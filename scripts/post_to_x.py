#!/usr/bin/env python3
"""MORTRA の検証済み問題を X へ投稿する。"""
import argparse
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local')


def _load_env_file(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, encoding='utf-8') as source:
        for line in source:
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or '=' not in stripped:
                continue
            key, value = stripped.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))


def _credentials() -> dict:
    _load_env_file(ENV_PATH)
    aliases = {
        'consumer_key': ('X_API_KEY', 'TWITTER_CONSUMER_KEY'),
        'consumer_secret': ('X_API_SECRET', 'TWITTER_CONSUMER_SECRET'),
        'access_token': ('X_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN'),
        'access_token_secret': ('X_ACCESS_TOKEN_SECRET', 'TWITTER_ACCESS_TOKEN_SECRET'),
    }
    credentials = {
        name: next((os.environ.get(key) for key in keys if os.environ.get(key)), None)
        for name, keys in aliases.items()
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise RuntimeError(f".env.local に X の認証情報が不足しています: {', '.join(missing)}")
    return credentials

def _strip_latex_dollars(text: str) -> str:
    r"""
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


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_publication_manifest(manifest_path: str, image_paths: list[str]) -> dict:
    absolute_manifest = os.path.abspath(manifest_path)
    if not os.path.isfile(absolute_manifest):
        raise RuntimeError(f"投稿マニフェストが見つかりません: {absolute_manifest}")

    with open(absolute_manifest, encoding='utf-8') as source:
        manifest = json.load(source)

    if manifest.get('schema') != 3:
        raise RuntimeError('投稿マニフェストの schema が3ではありません')
    replay = manifest.get('replayEvidence') or {}
    if replay.get('status') != 'accepted' or replay.get('errors'):
        raise RuntimeError('再生証明が accepted ではありません')
    if replay.get('card_id') != manifest.get('cardId'):
        raise RuntimeError('再生証明と投稿カードのIDが一致しません')

    manifest_dir = os.path.dirname(absolute_manifest)
    expected_outputs: dict[str, str] = {}
    for output in manifest.get('outputs') or []:
        output_path = output.get('path')
        expected_sha = output.get('sha256')
        if not output_path or not expected_sha:
            continue
        if not os.path.isabs(output_path):
            output_path = os.path.join(manifest_dir, output_path)
        expected_outputs[os.path.normcase(os.path.abspath(output_path))] = expected_sha.lower()

    verified_images = []
    for image_path in image_paths:
        absolute_image = os.path.abspath(image_path)
        key = os.path.normcase(absolute_image)
        expected_sha = expected_outputs.get(key)
        if not expected_sha:
            raise RuntimeError(f"画像が投稿マニフェストにありません: {absolute_image}")
        actual_sha = _sha256_file(absolute_image)
        if actual_sha.lower() != expected_sha:
            raise RuntimeError(
                f"画像のSHA-256が一致しません: {absolute_image} "
                f"(expected={expected_sha}, actual={actual_sha})"
            )
        verified_images.append({'path': absolute_image, 'sha256': actual_sha})

    return {
        'path': absolute_manifest,
        'card_id': manifest.get('cardId'),
        'replay_sha256': replay.get('replay_sha256'),
        'verified_images': verified_images,
    }

def post(
    text: str,
    image_paths: list[str],
    publish: bool = False,
    expected_account: str = 'MORTRA_AI',
    manifest_path: str | None = None,
) -> dict:
    publication_manifest = None
    if manifest_path:
        try:
            publication_manifest = _validate_publication_manifest(manifest_path, image_paths)
        except (OSError, ValueError, RuntimeError) as error:
            return {"ok": False, "error": str(error)}

    try:
        x = _credentials()
    except RuntimeError as error:
        return {"ok": False, "error": str(error)}

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

    safe_text = _strip_latex_dollars(text)
    if not safe_text:
        return {"ok": False, "error": "投稿本文が空です"}
    if len(image_paths) > 4:
        return {"ok": False, "error": "X に添付できる画像は4枚までです"}

    normalized_paths: list[str] = []
    for image_path in image_paths:
        absolute = os.path.abspath(image_path)
        if not os.path.isfile(absolute):
            return {"ok": False, "error": f"画像が見つかりません: {absolute}"}
        if os.path.splitext(absolute)[1].lower() not in {'.png', '.jpg', '.jpeg', '.webp'}:
            return {"ok": False, "error": f"未対応の画像形式です: {absolute}"}
        normalized_paths.append(absolute)

    try:
        me = client.get_me(user_auth=True)
        account = {
            "id": str(me.data.id),
            "username": getattr(me.data, 'username', None),
            "name": getattr(me.data, 'name', None),
        }
    except Exception as error:
        return {"ok": False, "error": f"X アカウントを確認できません: {error}"}

    actual_username = str(account.get('username') or '')
    if actual_username.casefold() != expected_account.lstrip('@').casefold():
        return {
            "ok": False,
            "error": f"投稿先が @{expected_account.lstrip('@')} ではなく @{actual_username} です",
            "account": account,
        }

    if not publish:
        return {
            "ok": True,
            "dry_run": True,
            "account": account,
            "text": safe_text,
            "text_length": len(safe_text),
            "images": normalized_paths,
            "publication_manifest": publication_manifest,
        }

    media_ids = None
    if normalized_paths:
        auth = tweepy.OAuth1UserHandler(
            x['consumer_key'], x['consumer_secret'],
            x['access_token'], x['access_token_secret'],
        )
        api_v1 = tweepy.API(auth)
        media_ids = [api_v1.media_upload(path).media_id for path in normalized_paths]

    resp     = client.create_tweet(text=safe_text, media_ids=media_ids)
    tweet_id = resp.data['id']
    url      = f"https://x.com/i/web/status/{tweet_id}"
    return {
        "ok": True,
        "tweet_id": tweet_id,
        "url": url,
        "account": account,
        "publication_manifest": publication_manifest,
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--text', required=True)
    parser.add_argument('--image-path', action='append', default=[])
    parser.add_argument('--publish', action='store_true', help='実際に投稿する。省略時は検査のみ。')
    parser.add_argument('--expected-account', default=os.environ.get('X_EXPECTED_USERNAME', 'MORTRA_AI'))
    parser.add_argument('--manifest', help='生成時のSHA-256と再生証明を含む投稿マニフェスト。')
    args = parser.parse_args()

    result = post(
        args.text,
        args.image_path,
        publish=args.publish,
        expected_account=args.expected_account,
        manifest_path=args.manifest,
    )
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result['ok'] else 1)

# -*- coding: utf-8 -*-
"""背景に流す動画を Pexels から探して assets/backgrounds/ に置く。

    python -m src.backdrop --list "cat"          # 縦の候補を見る
    python -m src.backdrop --list "dog" --any    # 向きを問わず見る
    python -m src.backdrop --get 12345           # 取得する
    python -m src.backdrop --show                # いま持っている素材と出所

**どれを使うかは人間が決める。** このモジュールは検索と取得だけを担う
(いらすとやの `src/fetch.py` と同じ役割分担)。

出所とライセンスは必ず `manifest.json` に残す。動画ファイル自体は git に
入れない(第三者の素材で、かつ大きい)ので、**記録だけがリポジトリに残る**。
`/publish` はこの manifest を読んでクレジットを書く。

Pexels を選んだ理由: 動画検索で `orientation=portrait` が使えて縦素材を
直接探せること、`user.name` / `user.url` が返るので作者を明記できること。
Pixabay は動画では orientation が効かない(画像のみ)。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from . import config

ENDPOINT = "https://api.pexels.com/v1/videos/search"
LICENSE = "Pexels License (商用可・表示義務なし)"
# 上限を超えて叩かないための保険。候補は目で選ぶので多くても見きれない
PER_PAGE = 15


class BackdropError(Exception):
    pass


@dataclass
class Clip:
    id: int
    page: str
    author: str
    author_url: str
    duration: int
    width: int
    height: int
    files: list[dict]

    @property
    def portrait(self) -> bool:
        return self.height > self.width


def _key() -> str:
    key = config.env("PEXELS_API_KEY")
    if not key:
        raise BackdropError(
            "PEXELS_API_KEY が見つかりません。\n"
            "  https://www.pexels.com/api/ でキーを取得し、\n"
            f"  {config.ROOT / '.env'} に PEXELS_API_KEY=… の1行を足してください。"
        )
    return key


def search(query: str, portrait: bool = True) -> list[Clip]:
    params = {"query": query, "per_page": str(PER_PAGE)}
    if portrait:
        params["orientation"] = "portrait"
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": _key()})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise BackdropError("PEXELS_API_KEY が受け付けられませんでした(401)")
        if exc.code == 429:
            raise BackdropError("Pexels の利用上限に達しました(429)。時間をおいてください")
        raise BackdropError(f"Pexels への問い合わせに失敗しました: {exc}")
    except urllib.error.URLError as exc:
        raise BackdropError(f"Pexels に接続できません: {exc.reason}")

    clips = []
    for hit in data.get("videos", []):
        user = hit.get("user") or {}
        clips.append(Clip(
            id=hit["id"], page=hit.get("url", ""),
            author=user.get("name", "") or "unknown", author_url=user.get("url", ""),
            duration=hit.get("duration", 0),
            width=hit.get("width", 0), height=hit.get("height", 0),
            files=[f for f in hit.get("video_files", [])
                   if f.get("file_type") == "video/mp4" and f.get("link")],
        ))
    return clips


def by_id(video_id: int, query: str) -> Clip:
    """--get で指定されたIDを、直前の検索語で引き直して見つける。

    Pexels に単体取得の動画エンドポイントがないので検索から拾う。
    """
    for portrait in (True, False):
        for clip in search(query, portrait):
            if clip.id == video_id:
                return clip
    raise BackdropError(f"id={video_id} が '{query}' の候補に見つかりません")


def pick_file(clip: Clip) -> dict:
    """拡大せずに 1080x1920 を埋められる、いちばん小さいファイルを選ぶ。

    大きすぎるファイルは変換も保存も無駄になる。足りなければ一番大きいものを
    使う(その場合は拡大されるので少し眠くなる)。
    """
    if not clip.files:
        raise BackdropError(f"id={clip.id} に mp4 がありません")
    ordered = sorted(clip.files, key=lambda f: f.get("width", 0) * f.get("height", 0))
    for file in ordered:
        w, h = file.get("width") or 0, file.get("height") or 0
        if w >= config.WIDTH and h >= config.HEIGHT:
            return file
    return ordered[-1]


# --------------------------------------------------------------------- 保存


def load_manifest() -> dict:
    if config.BACKGROUND_MANIFEST.exists():
        return json.loads(config.BACKGROUND_MANIFEST.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    config.BACKGROUND_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    config.BACKGROUND_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def store(clip: Clip, query: str) -> str:
    file = pick_file(clip)
    filename = f"pexels_{clip.id}.mp4"
    target = config.BACKGROUND_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(file["link"], headers={"Authorization": _key()})
    with urllib.request.urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())

    manifest = load_manifest()
    manifest[filename] = {
        "source": "Pexels",
        "id": clip.id,
        "license": LICENSE,
        # 表示義務はないが、規約が「可能なら作者を明記する」としているので入れる
        "credit": f"Video by {clip.author} on Pexels",
        "page": clip.page,
        "author_url": clip.author_url,
        "query": query,
        "size": f"{file.get('width')}x{file.get('height')}",
        "duration": clip.duration,
    }
    save_manifest(manifest)
    return filename


# --------------------------------------------------------------------- 表示


def print_candidates(clips: list[Clip]) -> None:
    print("%-9s %-6s %-11s %-5s %s" % ("id", "尺", "大きさ", "向き", "作者"))
    print("-" * 74)
    for clip in clips:
        file = pick_file(clip) if clip.files else {}
        print("%-9s %-6s %-11s %-5s %s"
              % (clip.id, f"{clip.duration}s",
                 f"{file.get('width', '?')}x{file.get('height', '?')}",
                 "縦" if clip.portrait else "横", clip.author))
    print("\n落ち着いた映像を選ぶこと。動きが速いと文字が読みにくくなる。")


def print_owned() -> None:
    manifest = load_manifest()
    if not config.BACKGROUNDS:
        print("背景素材がありません")
        return
    print("%-28s %-12s %s" % ("ファイル", "出所", "クレジット / 備考"))
    print("-" * 78)
    for path in config.BACKGROUNDS:
        entry = manifest.get(path.name)
        if entry is None:
            # 出所の分からない素材が混ざると /publish で書けない
            print("%-28s %-12s %s" % (path.name, "不明", "manifest に記録がない"))
            continue
        print("%-28s %-12s %s" % (path.name, entry.get("source", ""),
                                  entry.get("credit") or entry.get("license", "")))
    print("\n合計 %d 本" % len(config.BACKGROUNDS))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", metavar="QUERY", help="候補を一覧する")
    parser.add_argument("--any", action="store_true", help="縦だけでなく横の素材も見る")
    parser.add_argument("--get", type=int, metavar="ID", help="取得する")
    parser.add_argument("--query", help="--get のときの検索語(--list と同じものを渡す)")
    parser.add_argument("--show", action="store_true", help="持っている素材と出所を見る")
    args = parser.parse_args(argv)

    try:
        if args.show:
            print_owned()
            return 0

        if args.list:
            clips = search(args.list, portrait=not args.any)
            if not clips:
                print(f"'{args.list}' の候補が見つかりません"
                      + ("。--any で横の素材も探せます" if not args.any else ""))
                return 0
            print_candidates(clips)
            print(f'\npython -m src.backdrop --get <id> --query "{args.list}"')
            return 0

        if args.get:
            if not args.query:
                raise BackdropError('--query に --list で使った検索語を渡してください')
            clip = by_id(args.get, args.query)
            filename = store(clip, args.query)
            print(f"{filename} を置きました: {config.BACKGROUND_DIR}")
            print(f"  {clip.page}")
            print(f"  Video by {clip.author} on Pexels / {LICENSE}")
            return 0

        parser.print_help()
        return 1
    except BackdropError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

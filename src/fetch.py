# -*- coding: utf-8 -*-
"""イラストを探して assets/images/ と manifest.json に入れる。

どの絵を使うかの判断は人間 (または Claude Code) が行う前提で、
このモジュールは検索と取得の手順だけを担う。

    python -m src.fetch --list "タコ"                  # 候補を見る
    python -m src.fetch --get "タコ" --pick 2 --slot 0 # 3件目を0項目目に入れる

いらすとやは Blogger 上にあるので、サイトの HTML を解析せずに
Blogger が公開しているフィードで検索できる。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from PIL import Image

from . import config

FEED = "https://www.irasutoya.com/feeds/posts/default"
UA = {"User-Agent": "Mozilla/5.0 (compatible; zatsugaku-pipeline/0.1)"}
THROTTLE = 1.0          # 連続アクセスの間隔(秒)


@dataclass
class Candidate:
    title: str
    page: str
    image: str


def search(query: str, limit: int = 8) -> list[Candidate]:
    url = FEED + "?" + urllib.parse.urlencode(
        {"q": query, "alt": "json", "max-results": limit}
    )
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as response:
        feed = json.loads(response.read().decode("utf-8"))

    out: list[Candidate] = []
    for entry in feed.get("feed", {}).get("entry", []):
        content = entry.get("content", {}).get("$t", "")
        images = re.findall(r'https://blogger\.googleusercontent\.com/[^"\']+?\.(?:png|jpg|jpeg)',
                            content)
        if not images:
            continue
        page = next((l["href"] for l in entry.get("link", []) if l.get("rel") == "alternate"), "")
        out.append(Candidate(title=entry["title"]["$t"], page=page, image=images[0]))
    return out


def download(candidate: Candidate) -> Image.Image:
    # Blogger のサムネイルは /sNNN/ でサイズが決まる。大きい版を要求する
    url = re.sub(r"/s\d+(-c)?/", "/s800/", candidate.image)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as response:
        image = Image.open(io.BytesIO(response.read()))
        image.load()
    return image.convert("RGBA")


def load_manifest() -> dict:
    if config.MANIFEST.exists():
        return json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    config.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    config.MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def store(candidate: Candidate, slot: int, name: str | None = None) -> str:
    """画像を保存し、manifest に登録する。ファイル名を返す。"""
    image = download(candidate)
    filename = f"{slot:02d}_{name or 'image'}.png"
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    image.save(config.IMAGES_DIR / filename)

    manifest = load_manifest()
    manifest[str(slot)] = {
        "file": filename,
        "source": "いらすとや",
        # いらすとやは表示義務がないので attribution は null。
        # CC BY 系を使うときだけ「作者 / ライセンス」を入れる。
        "attribution": None,
        "title": candidate.title,
        "url": candidate.page,
    }
    save_manifest(manifest)
    return filename


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", metavar="QUERY", help="候補を一覧する")
    parser.add_argument("--get", metavar="QUERY", help="取得する")
    parser.add_argument("--pick", type=int, default=0, help="--get で使う候補の番号")
    parser.add_argument("--slot", type=int, help="台本の何項目目に入れるか (0始まり)")
    parser.add_argument("--name", help="保存するファイル名の一部")
    args = parser.parse_args(argv)

    if args.list:
        for i, candidate in enumerate(search(args.list)):
            print(f"[{i}] {candidate.title}")
            print(f"     {candidate.page}")
        return 0

    if args.get:
        if args.slot is None:
            raise SystemExit("--slot を指定してください")
        candidates = search(args.get)
        if not candidates:
            raise SystemExit(f"'{args.get}' の候補が見つかりません")
        if args.pick >= len(candidates):
            raise SystemExit(f"候補は {len(candidates)} 件です")
        time.sleep(THROTTLE)
        filename = store(candidates[args.pick], args.slot, args.name)
        print(f"slot {args.slot} <- {candidates[args.pick].title}  ({filename})")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""レイアウトを詰めるための静止画1枚。音声合成も動画エンコードも通さない。

    python -m src.preview            # 1項目目
    python -m src.preview --item 3   # 3項目目
    python -m src.preview --title    # タイトルカード

表示タイミングは無視して、全要素が出た状態を描く。
out/preview.png と、セーフエリアを重ねた out/preview_guide.png を書き出す。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

from . import config, layout


def load_script() -> dict:
    if not config.SCRIPT_JSON.exists():
        raise SystemExit(f"台本がありません: {config.SCRIPT_JSON}")
    return json.loads(config.SCRIPT_JSON.read_text(encoding="utf-8"))


def load_manifest() -> dict:
    if not config.MANIFEST.exists():
        return {}
    return json.loads(config.MANIFEST.read_text(encoding="utf-8"))


def illustration_for(index: int, manifest: dict) -> tuple[Image.Image | None, str | None]:
    entry = manifest.get(str(index))
    if not entry:
        return None, None
    path = config.IMAGES_DIR / entry["file"]
    if not path.exists():
        print(f"警告: 画像がありません: {path}", file=sys.stderr)
        return None, entry.get("attribution")
    return Image.open(path).convert("RGBA"), entry.get("attribution")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--item", type=int, default=1, help="台本の何項目目か (1始まり)")
    parser.add_argument("--title", action="store_true", help="タイトルカードを描く")
    parser.add_argument("--no-punch", action="store_true", help="オチを出す前の状態を描く")
    parser.add_argument("--no-bg", action="store_true", help="背景動画を敷かず単色で描く")
    args = parser.parse_args(argv)

    script = load_script()

    background = None if args.no_bg else layout.background_frame(0 if args.title else args.item - 1)

    if args.title:
        image = layout.render_title(script["title"], background=background)
        label = "タイトルカード"
    else:
        items = script.get("items") or []
        if not 1 <= args.item <= len(items):
            raise SystemExit(f"--item は 1〜{len(items)} で指定してください")
        item = items[args.item - 1]
        illustration, attribution = illustration_for(args.item - 1, load_manifest())
        image = layout.render_item(
            setup=item["setup"],
            punch=None if args.no_punch else item["punch"],
            illustration=illustration,
            attribution=attribution,
            background=background,
        )
        label = f"{args.item}項目目: {item['setup']} / {item['punch']}"

    config.OUT_DIR.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(config.OUT_DIR / "preview.png")
    layout.with_safe_area(image).convert("RGB").save(config.OUT_DIR / "preview_guide.png")

    print(f"{label}")
    print(f"  {config.OUT_DIR / 'preview.png'}")
    print(f"  {config.OUT_DIR / 'preview_guide.png'} (セーフエリア重ね)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

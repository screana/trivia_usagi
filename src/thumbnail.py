# -*- coding: utf-8 -*-
"""サムネイルを作る。

    python -m src.thumbnail                 # out/thumbnail.png
    python -m src.thumbnail --item 3        # 3項目目で作る
    python -m src.thumbnail --expression 困り
    python -m src.thumbnail --no-mask       # 伏せ字を出さない

**一番引きのある項目**の振りだけを出して、オチは伏せる。何が答えなのか気になる状態で
止めるのが狙い。うさぎは動画より大きく置く。

描画は layout.py の部品を使う。文字の折り返しやフチの出方を動画と揃えるため。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

from . import config, layout


class ThumbnailError(Exception):
    pass


def load_script() -> dict:
    if not config.SCRIPT_JSON.exists():
        raise ThumbnailError(f"台本がありません: {config.SCRIPT_JSON}")
    return json.loads(config.SCRIPT_JSON.read_text(encoding="utf-8"))


def illustration_for(index: int):
    if not config.MANIFEST.exists():
        return None
    entry = json.loads(config.MANIFEST.read_text(encoding="utf-8")).get(str(index))
    if not entry:
        return None
    path = config.IMAGES_DIR / entry["file"]
    return Image.open(path).convert("RGBA") if path.exists() else None


def mascot(expression: str) -> Image.Image | None:
    """表情付きの立ち絵。無ければ PSD から作る。"""
    path = config.TACHIE_DIR / f"{expression}.png"
    if not path.exists():
        from . import tachie

        if expression not in config.EXPRESSIONS:
            raise ThumbnailError(
                f"表情 '{expression}' は未定義です。"
                f"使えるのは {', '.join(config.EXPRESSIONS)}"
            )
        tachie.save(config.EXPRESSIONS[expression], path)

    image = Image.open(path).convert("RGBA")
    image = image.crop(image.getbbox())
    if config.MASCOT_FLIP:
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
    height = config.THUMB_MASCOT_HEIGHT
    return image.resize((max(1, int(image.width * height / image.height)), height), Image.LANCZOS)


def render(item: dict, index: int, expression: str, mask: bool) -> Image.Image:
    background = layout.background_frame(index)

    # ベールは動画より薄くして、背景の写真を少し見せる
    original = config.SCRIM_ALPHA
    config.SCRIM_ALPHA = config.THUMB_SCRIM_ALPHA
    try:
        canvas = layout.base(background)
    finally:
        config.SCRIM_ALPHA = original

    rabbit = mascot(expression)
    if rabbit is not None:
        canvas.alpha_composite(
            rabbit, (config.THUMB_MASCOT_X, config.THUMB_MASCOT_BOTTOM - rabbit.height)
        )

    setup = layout.text_block(
        item["setup"], config.THUMB_SETUP_SIZE, fill=config.TEXT, stroke=config.TEXT_STROKE,
        stroke_width=config.STROKE_WIDTH + 3, max_width=config.TEXT_MAX_WIDTH,
        line_spacing=config.LINE_SPACING,
    )
    canvas.alpha_composite(
        setup, ((canvas.width - setup.width) // 2, config.THUMB_SETUP_BOTTOM - setup.height)
    )

    illustration = illustration_for(index)
    if illustration is not None:
        circle = layout.circular(illustration, config.THUMB_CIRCLE_DIAMETER)
        canvas.alpha_composite(
            circle,
            ((canvas.width - circle.width) // 2,
             config.THUMB_CIRCLE_CENTER_Y - circle.height // 2),
        )

    if mask and config.THUMB_MASK_TEXT:
        block = layout.text_block(
            config.THUMB_MASK_TEXT, config.THUMB_MASK_SIZE, fill=config.THUMB_MASK_COLOR,
            stroke=config.TEXT_STROKE, stroke_width=config.STROKE_WIDTH + 8,
            max_width=config.TEXT_MAX_WIDTH, line_spacing=0,
        )
        canvas.alpha_composite(
            block, ((canvas.width - block.width) // 2, config.THUMB_MASK_Y)
        )

    return canvas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--item", type=int, help="使う項目 (1始まり)。既定は config.THUMB_ITEM")
    parser.add_argument("--expression", default=config.THUMB_EXPRESSION,
                        help="うさぎの表情")
    parser.add_argument("--no-mask", action="store_true", help="伏せ字を出さない")
    parser.add_argument("-o", "--out", type=Path)
    args = parser.parse_args(argv)

    try:
        script = load_script()
        items = script["items"]
        index = (args.item - 1) if args.item else (config.THUMB_ITEM - 1)
        if not 0 <= index < len(items):
            raise ThumbnailError(f"--item は 1〜{len(items)} で指定してください")

        image = render(items[index], index, args.expression, not args.no_mask)
        out = args.out or (config.OUT_DIR / "thumbnail.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(out)
        layout.with_safe_area(image).convert("RGB").save(
            out.with_name(out.stem + "_guide.png")
        )
        print(f"{index + 1}項目目「{items[index]['setup']}」/ 表情 {args.expression}")
        print(f"  {out}")
        print(f"  {out.with_name(out.stem + '_guide.png')} (セーフエリア重ね)")
        return 0
    except ThumbnailError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

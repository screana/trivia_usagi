# -*- coding: utf-8 -*-
"""画面の描画。preview と build の両方がここを呼ぶ。

プレビューで見た絵と本番の絵がズレないよう、描画ロジックはここにしか持たない。
座標・サイズ・色は config.py にある。
"""
from __future__ import annotations

import functools
import random
from pathlib import Path

import budoux
from PIL import Image, ImageDraw, ImageFont

from . import config

# BudouX(Google製)で文節の切れ目を出し、その位置でだけ折り返す。
# 文字単位で折ると「メスのほ / うがおいしい」のように読みにくく切れるため。
_PARSER = budoux.load_default_japanese_parser()


@functools.lru_cache(maxsize=8)
def load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(config.FONT_PATH, size, index=config.FONT_INDEX)
    except OSError:
        for path, index in config.FONT_FALLBACKS:
            if Path(path).exists():
                return ImageFont.truetype(path, size, index=index)
        raise


def wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """文節の切れ目を候補に、max_width に収まるよう折り返す。

    台本側の明示的な改行(\\n)は必ず尊重する。
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for chunk in _PARSER.parse(paragraph):
            candidate = current + chunk
            if current and font.getlength(candidate) > max_width:
                lines.append(current)
                current = chunk
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines or [""]


def text_block(text: str, size: int, *, fill: str, stroke: str | None,
               stroke_width: int, max_width: int, line_spacing: int) -> Image.Image:
    """中央揃えのテキストを、必要な大きさの RGBA 画像として返す。"""
    font = load_font(size)
    lines = wrap(text, font, max_width)
    ascent, descent = font.getmetrics()
    line_height = ascent + descent
    pad = stroke_width + 4

    width = int(max(font.getlength(line) for line in lines)) + pad * 2
    height = line_height * len(lines) + line_spacing * (len(lines) - 1) + pad * 2

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text(
            (width // 2, pad + i * (line_height + line_spacing)),
            line, font=font, fill=fill, anchor="ma",
            stroke_width=stroke_width, stroke_fill=stroke or fill,
        )
    return image


def circular(image: Image.Image, diameter: int) -> Image.Image:
    """イラストを円に収める。下地を白で塗ってから中央に置く。

    透過素材でも白背景素材でも同じ見え方になるようにするため、円を先に描く。
    """
    canvas = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)
    canvas.paste(Image.new("RGBA", (diameter, diameter), config.CIRCLE_FILL), (0, 0), mask)

    inner = int(diameter * 0.82)          # 円の縁に触れないよう少し内側に置く
    fitted = image.copy()
    fitted.thumbnail((inner, inner), Image.LANCZOS)
    canvas.alpha_composite(fitted, ((diameter - fitted.width) // 2, (diameter - fitted.height) // 2))

    out = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    out.paste(canvas, (0, 0), mask)
    return out


@functools.lru_cache(maxsize=1)
def _mascot() -> Image.Image | None:
    if not config.MASCOT.exists():
        return None
    image = Image.open(config.MASCOT).convert("RGBA")
    image = image.crop(image.getbbox())
    if config.MASCOT_FLIP:
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
    height = config.MASCOT_HEIGHT
    width = max(1, int(image.width * height / image.height))
    return image.resize((width, height), Image.LANCZOS)


def background_order(count: int):
    """背景クリップを何番目の項目に割り当てるかを決める。

    順番に使うと並びが読めてしまうのでシャッフルする。素材より項目が多いときは
    一巡ごとに切り直し、**隣り合う項目が同じクリップにならない**ようにする
    (同じ映像が続くと切り替わったように見えないため)。

    毎回変わると書き出しを見比べられないので、種は config に固定してある。
    """
    if not config.BACKGROUNDS:
        return [None] * count

    rng = random.Random(config.BG_SHUFFLE_SEED)
    order: list = []
    while len(order) < count:
        deck = list(config.BACKGROUNDS)
        rng.shuffle(deck)
        if order and len(deck) > 1 and deck[0] == order[-1]:
            deck.append(deck.pop(0))
        order.extend(deck)
    return order[:count]


def background_path(index: int):
    """項目番号(0始まり)に対して使う背景クリップ。"""
    return background_order(index + 1)[index]


def background_frame(index: int, seconds: float = 2.0) -> Image.Image | None:
    """背景クリップから1コマ取り出す。プレビューを実際の見え方に近づけるため。"""
    import subprocess

    import imageio_ffmpeg
    import numpy as np

    path = background_path(index)
    if path is None:
        return None
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-ss", str(seconds), "-i", str(path),
        "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    raw = subprocess.run(command, capture_output=True).stdout
    if not raw:
        return None
    # 素材は 1920x1080 固定。取り出したバイト数から高さを割り出す
    width = 1920
    height = len(raw) // (width * 3)
    return Image.fromarray(np.frombuffer(raw[: width * height * 3], dtype=np.uint8)
                           .reshape(height, width, 3))


def fit_cover(image: Image.Image) -> Image.Image:
    """画面いっぱいになるよう拡大して中央を切り出す。素材は16:9なので左右が落ちる。"""
    ratio = max(config.WIDTH / image.width, config.HEIGHT / image.height)
    scaled = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
                          Image.LANCZOS)
    left = (scaled.width - config.WIDTH) // 2
    top = (scaled.height - config.HEIGHT) // 2
    return scaled.crop((left, top, left + config.WIDTH, top + config.HEIGHT))


def _scrim() -> Image.Image | None:
    """背景を抜くための白いベール。黒文字+白フチだけでは映像の上で読みにくい。"""
    alpha = int(round(255 * config.SCRIM_ALPHA))
    if alpha <= 0:
        return None
    return Image.new("RGBA", (config.WIDTH, config.HEIGHT), config.SCRIM_COLOR + (alpha,))


def base(background: Image.Image | None = None, *, overlay: bool = False) -> Image.Image:
    """下地を作る。

    overlay=True なら透明な下地にベールだけ敷いて返す。動画に重ねる用。
    こうすると build は「動画の上にこの1枚を合成するだけ」で済み、
    プレビューと本番で描画ロジックが分かれない。
    """
    if overlay:
        canvas = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    elif background is None:
        return Image.new("RGBA", (config.WIDTH, config.HEIGHT), config.BG)
    else:
        canvas = fit_cover(background.convert("RGBA"))

    scrim = _scrim()
    if scrim is not None:
        canvas.alpha_composite(scrim)
    return canvas


def paste_mascot(canvas: Image.Image) -> None:
    """中国うさぎをタイトルから最後まで左下に出す。"""
    mascot = _mascot()
    if mascot is not None:
        canvas.alpha_composite(mascot, (config.MASCOT_X, config.MASCOT_BOTTOM - mascot.height))


def _centered(canvas: Image.Image, block: Image.Image, top: int) -> None:
    canvas.alpha_composite(block, ((canvas.width - block.width) // 2, top))


def _centered_bottom(canvas: Image.Image, block: Image.Image, bottom: int) -> None:
    """下端を合わせて置く。行数が増えても下に伸びないので、
    振りが2行になったときに円へ食い込むのを防げる。"""
    canvas.alpha_composite(block, ((canvas.width - block.width) // 2, bottom - block.height))


def render_title(title: str, background: Image.Image | None = None,
                 *, overlay: bool = False) -> Image.Image:
    canvas = base(background, overlay=overlay)
    paste_mascot(canvas)
    _centered(canvas, text_block(
        title, config.TITLE_SIZE, fill=config.TEXT, stroke=config.TEXT_STROKE,
        stroke_width=config.STROKE_WIDTH + 2, max_width=config.TEXT_MAX_WIDTH,
        line_spacing=config.LINE_SPACING,
    ), config.TITLE_Y)
    return canvas


def render_item(setup: str, punch: str | None, illustration: Image.Image | None,
                attribution: str | None, background: Image.Image | None = None,
                *, overlay: bool = False) -> Image.Image:
    """1項目の画面。punch が None なら振りだけの状態を描く。

    出典表記の有無で他の要素の位置は変えない(座標は固定)。
    """
    canvas = base(background, overlay=overlay)
    paste_mascot(canvas)

    _centered_bottom(canvas, text_block(
        setup, config.FONT_SIZE, fill=config.TEXT, stroke=config.TEXT_STROKE,
        stroke_width=config.STROKE_WIDTH, max_width=config.TEXT_MAX_WIDTH,
        line_spacing=config.LINE_SPACING,
    ), config.SETUP_BOTTOM)

    if illustration is not None:
        circle = circular(illustration, config.CIRCLE_DIAMETER)
        canvas.alpha_composite(
            circle,
            ((canvas.width - circle.width) // 2, config.CIRCLE_CENTER_Y - circle.height // 2),
        )

    if attribution:
        _centered(canvas, text_block(
            attribution, config.ATTRIBUTION_SIZE, fill=config.ATTRIBUTION_COLOR,
            stroke=None, stroke_width=0, max_width=config.TEXT_MAX_WIDTH,
            line_spacing=6,
        ), config.ATTRIBUTION_Y)

    if punch:
        _centered(canvas, text_block(
            punch, config.FONT_SIZE, fill=config.TEXT, stroke=config.TEXT_STROKE,
            stroke_width=config.STROKE_WIDTH, max_width=config.TEXT_MAX_WIDTH,
            line_spacing=config.LINE_SPACING,
        ), config.PUNCH_Y)

    return canvas


def with_safe_area(image: Image.Image) -> Image.Image:
    """セーフエリアのガイド線を重ねた版。/review でのはみ出し確認用。"""
    out = image.copy()
    draw = ImageDraw.Draw(out, "RGBA")
    fill = (255, 0, 102, 60)
    draw.rectangle((0, 0, out.width, config.SAFE_TOP), fill=fill)
    draw.rectangle((0, out.height - config.SAFE_BOTTOM, out.width, out.height), fill=fill)
    draw.rectangle((0, 0, config.SAFE_SIDE, out.height), fill=fill)
    draw.rectangle((out.width - config.SAFE_SIDE, 0, out.width, out.height), fill=fill)
    draw.rectangle(
        (config.SAFE_SIDE, config.SAFE_TOP,
         out.width - config.SAFE_SIDE, out.height - config.SAFE_BOTTOM),
        outline=config.GUIDE_COLOR, width=4,
    )
    return out

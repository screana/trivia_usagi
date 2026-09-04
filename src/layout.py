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


def mascot_path(expression: str | None):
    """表情名から立ち絵のパスを返す。無ければ PSD から作る。"""
    if not expression:
        return config.MASCOT if config.MASCOT.exists() else None
    path = config.TACHIE_DIR / f"{expression}.png"
    if not path.exists():
        from . import tachie

        if expression not in config.EXPRESSIONS:
            raise ValueError(
                f"表情 '{expression}' は未定義です。使えるのは {', '.join(config.EXPRESSIONS)}"
            )
        tachie.save(config.EXPRESSIONS[expression], path)
    return path


@functools.lru_cache(maxsize=8)
def _mascot(expression: str | None = None) -> Image.Image | None:
    path = mascot_path(expression)
    if path is None:
        return None
    image = Image.open(path).convert("RGBA")
    # 切り抜きは表情によらず同じ位置にする。表情ごとの bbox で切ると
    # 切り替わりで立ち絵が跳ねる(いまの素材はすべて一致しているが、
    # 記号を足した表情を増やしたときに崩れないよう固定しておく)
    image = image.crop(config.MASCOT_CROP)
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
    import io
    import subprocess

    import imageio_ffmpeg

    path = background_path(index)
    if path is None:
        return None
    # PNG で受け取る。生バイト列だと解像度を別途知る必要があり、素材の縦横が
    # 変わったとき(縦の素材を混ぜたときなど)に静かに崩れる
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-ss", str(seconds), "-i", str(path),
        "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-",
    ]
    raw = subprocess.run(command, capture_output=True).stdout
    if not raw:
        return None
    return Image.open(io.BytesIO(raw)).convert("RGB")


def fit_cover(image: Image.Image) -> Image.Image:
    """画面いっぱいになるよう拡大して中央を切り出す。横長の素材は左右が落ちる。"""
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


@functools.lru_cache(maxsize=1)
def _promo_icon() -> Image.Image | None:
    """アプリのアイコン。角を丸めてアプリらしく見せる。"""
    if not config.PROMO_ICON.exists():
        return None
    size = config.PROMO_ICON_SIZE
    icon = Image.open(config.PROMO_ICON).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=config.PROMO_ICON_RADIUS, fill=255
    )
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(icon, (0, 0), mask)
    return out


def paste_promo(canvas: Image.Image) -> None:
    """立ち絵の右の空きにアイコンと一言を置く。

    オチの下、立ち絵の横の帯は他に使い道がないので、ここに宣伝を入れる。
    セーフエリアの内側に収めているので、アプリのUIには隠れない。
    """
    if not config.PROMO_SHOW:
        return

    icon = _promo_icon()
    x = config.PROMO_X
    if icon is not None:
        canvas.alpha_composite(icon, (x, config.PROMO_CENTER_Y - icon.height // 2))
        x += icon.width + config.PROMO_GAP

    text = text_block(
        config.PROMO_TEXT, config.PROMO_TEXT_SIZE, fill=config.TEXT,
        stroke=config.TEXT_STROKE, stroke_width=config.STROKE_WIDTH - 1,
        max_width=config.WIDTH - config.SAFE_SIDE - x, line_spacing=0,
    )
    canvas.alpha_composite(text, (x, config.PROMO_CENTER_Y - text.height // 2))


def paste_mascot(canvas: Image.Image, expression: str | None = None) -> None:
    """中国うさぎをタイトルから最後まで左下に出す。"""
    mascot = _mascot(expression)
    if mascot is not None:
        canvas.alpha_composite(mascot, (config.MASCOT_X, config.MASCOT_BOTTOM - mascot.height))


def _centered(canvas: Image.Image, block: Image.Image, top: int) -> None:
    canvas.alpha_composite(block, ((canvas.width - block.width) // 2, top))


def _centered_bottom(canvas: Image.Image, block: Image.Image, bottom: int) -> None:
    """下端を合わせて置く。行数が増えても下に伸びないので、
    振りが2行になったときに円へ食い込むのを防げる。"""
    canvas.alpha_composite(block, ((canvas.width - block.width) // 2, bottom - block.height))


def render_title(title: str, background: Image.Image | None = None,
                 *, overlay: bool = False, expression: str | None = None) -> Image.Image:
    canvas = base(background, overlay=overlay)
    paste_mascot(canvas, expression)
    paste_promo(canvas)
    _centered(canvas, text_block(
        title, config.TITLE_SIZE, fill=config.TEXT, stroke=config.TEXT_STROKE,
        stroke_width=config.STROKE_WIDTH + 2, max_width=config.TEXT_MAX_WIDTH,
        line_spacing=config.LINE_SPACING,
    ), config.TITLE_Y)
    return canvas


def render_item(setup: str, punch: str | None, illustration: Image.Image | None,
                attribution: str | None, background: Image.Image | None = None,
                *, overlay: bool = False, expression: str | None = None) -> Image.Image:
    """1項目の画面。punch が None なら振りだけの状態を描く。

    出典表記の有無で他の要素の位置は変えない(座標は固定)。
    """
    canvas = base(background, overlay=overlay)
    paste_mascot(canvas, expression)
    paste_promo(canvas)

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


def with_youtube_ui(image: Image.Image) -> Image.Image:
    """Shorts のUIを模した目隠しを重ねる。何が隠れるかを見るためのもの。

    本物のUI画像は Google の著作物なので使わず、位置と大きさだけを写した
    自前のモックを描いている。アイコンの形は似せていない(目的は遮蔽の確認)。
    寸法はセーフエリアの根拠に使った各プラットフォームのガイドに合わせてある。
    """
    out = image.convert("RGBA")
    w, h = out.size
    # 半透明を重ねるので、別レイヤに描いてから合成する。
    # ImageDraw.Draw(im, "RGBA") は合成ではなく上書きになり、帯が真っ黒になる
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    ink = (255, 255, 255, 235)
    shade = (0, 0, 0, 90)

    # 上下の暗がり(実際のUIも文字を読ませるため陰を敷いている)
    draw.rectangle((0, 0, w, 190), fill=(0, 0, 0, 60))
    draw.rectangle((0, h - 430, w, h), fill=shade)

    # 右の操作ボタン列。いいね/よくないね/コメント/共有/リミックス/音源
    cx = w - 66
    for i, cy in enumerate(range(h - 900, h - 240, 132)):
        if i == 5:                                  # 音源だけ角丸の四角
            draw.rounded_rectangle((cx - 38, cy - 38, cx + 38, cy + 38), radius=10,
                                   outline=ink, width=5)
        else:
            draw.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), outline=ink, width=5)
        if i < 4:                                   # 数字が入る位置
            draw.rounded_rectangle((cx - 28, cy + 44, cx + 28, cy + 60), radius=8, fill=ink)

    # 左下のチャンネル情報と説明文
    draw.ellipse((40, h - 386, 116, h - 310), outline=ink, width=5)      # アイコン
    draw.rounded_rectangle((130, h - 366, 420, h - 334), radius=14, fill=ink)  # @名前
    draw.rounded_rectangle((436, h - 372, 596, h - 328), radius=22,
                           outline=ink, width=5)                        # 登録ボタン
    for i, y in enumerate((h - 288, h - 240)):                          # 説明文2行
        draw.rounded_rectangle((40, y, 40 + (760 if i == 0 else 520), y + 30),
                               radius=12, fill=(255, 255, 255, 200))

    # 再生バー
    draw.rounded_rectangle((40, h - 176, w - 40, h - 166), radius=5, fill=(255, 255, 255, 110))
    draw.rounded_rectangle((40, h - 176, 470, h - 166), radius=5, fill=ink)

    # モックであることを明示する
    font = load_font(26)
    draw.text((40, 44), "※ Shorts のUIを模した確認用の重ね絵(本物ではありません)",
              font=font, fill=(255, 255, 255, 220),
              stroke_width=3, stroke_fill=(0, 0, 0, 180))

    out.alpha_composite(layer)
    return out


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

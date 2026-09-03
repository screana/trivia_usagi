# -*- coding: utf-8 -*-
"""座標・サイズ・色・速度をすべてここに置く。他のファイルに数値を書かない。

ここの値は初期値であって確定仕様ではない。preview.py で見ながら動かす前提。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------- 出力

WIDTH = 1080
HEIGHT = 1920
FPS = 30

SCRIPT_JSON = ROOT / "script.json"
IMAGES_DIR = ROOT / "assets" / "images"
MANIFEST = IMAGES_DIR / "manifest.json"
OUT_DIR = ROOT / "out"
AUDIO_DIR = OUT_DIR / "audio"

# 立ち絵は第三者の配布素材なので、リポジトリの外を参照する
MASCOT = ROOT.parent / "VOICEBOX" / "素材" / "うさぎ" / "中国うさぎ立ち絵素材2_0000.png"
BGM = ROOT / "assets" / "bgm.mp3"          # 無ければ BGM なしで書き出す

# --------------------------------------------------------------------- 色

BG = "#EFEFEF"
TEXT = "#111111"
TEXT_STROKE = "#FFFFFF"
CIRCLE_FILL = "#FFFFFF"        # イラストを載せる円の下地
ATTRIBUTION_COLOR = "#6B6B6B"
GUIDE_COLOR = "#FF0066"        # セーフエリアのガイド線(preview_guide のみ)

# --------------------------------------------------------------------- フォント

# BIZ UDPGothic Bold は単体ファイルではなく ttc の中にある。
# index=0 は等幅の BIZ UDGothic なので、プロポーショナルの index=1 を使う。
FONT_PATH = "C:/Windows/Fonts/BIZ-UDGothicB.ttc"
FONT_INDEX = 1
FONT_FALLBACKS = [
    ("C:/Windows/Fonts/YuGothB.ttc", 0),
    ("C:/Windows/Fonts/meiryob.ttc", 0),
]

FONT_SIZE = 85                 # 振り・オチ共通
STROKE_WIDTH = 7
LINE_SPACING = 16

# --------------------------------------------------------------------- レイアウト

# セーフエリア。ここに要素を置かない
SAFE_TOP = 200
SAFE_BOTTOM = 400
SAFE_SIDE = 120

TEXT_MAX_WIDTH = WIDTH - SAFE_SIDE * 2 - 40

SETUP_Y = 240                  # 振りテキストのブロック上端
CIRCLE_CENTER_Y = 700          # イラストの円の中心
CIRCLE_DIAMETER = 560
ATTRIBUTION_Y = 1000           # 出典表記のブロック上端(出す場合のみ)
ATTRIBUTION_SIZE = 30
PUNCH_Y = 1090                 # オチテキストのブロック上端

MASCOT_X = 90                 # 立ち絵の左端
MASCOT_BOTTOM = 1790           # 立ち絵の下端
MASCOT_HEIGHT = 420

TITLE_SIZE = 105
TITLE_Y = 620

# --------------------------------------------------------------------- 音声

SPEAKER_NAME = "中国うさぎ"     # style_id は /speakers から名前で解決する
SPEAKER_STYLE = "ノーマル"
SPEED_SCALE = 1.1
VOICEVOX_HOST = "http://127.0.0.1:50021"

# --------------------------------------------------------------------- 尺

TITLE_DURATION = 2.0           # タイトルカード
REVEAL_GAP = 0.5               # 振りを読み終えてからオチを出すまでの溜め
ITEM_GAP = 0.4                 # 項目と項目のあいだの無音
TAIL = 0.6                     # 最後の余韻

BGM_VOLUME = 0.12
BGM_DUCK = 0.45                # 読み上げ中の BGM 音量倍率

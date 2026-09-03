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
# 背景素材を縦型に変換したもの。毎回変換すると書き出しが数倍遅くなるので貯める
BG_CACHE = OUT_DIR / "bg"

# 立ち絵は第三者の配布素材なので、リポジトリの外を参照する
TACHIE_DIR = ROOT.parent / "VOICEBOX" / "素材" / "うさぎ"
TACHIE_PSD = TACHIE_DIR / "psd" / "中国うさぎ立ち絵素材2.0.psd"
MASCOT = TACHIE_DIR / "中国うさぎ立ち絵素材2_0000.png"
# BGM。曲名を /publish のクレジットに使うので、置かれたファイル名のまま扱う
_BGM_FILES = sorted((ROOT / "assets").glob("*.mp3"))
BGM = _BGM_FILES[0] if _BGM_FILES else ROOT / "assets" / "bgm.mp3"
ENDCARD = ROOT / "assets" / "endcard.mp4"
# 背景に流す動画。順に使い、足りなければ先頭に戻る
BACKGROUNDS = sorted((ROOT / "assets").glob("AdobeStock_*.mov"))
# 背景の並び順を決める種。変えると割り当てが変わる。固定なのは書き出しを
# 見比べられるようにするため
BG_SHUFFLE_SEED = 7

# --------------------------------------------------------------------- 色

BG = "#EFEFEF"                 # 背景動画を使わないときの下地
# 背景動画の上に敷く白いベール。黒文字+白フチだけでは映像の上で読みにくい
SCRIM_COLOR = (255, 255, 255)
SCRIM_ALPHA = 0.62             # 0=そのまま 1=真っ白
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

SETUP_BOTTOM = 410             # 振りテキストのブロック"下端"。
                               # 行数が増えても円に食い込まないよう下端で揃える
CIRCLE_CENTER_Y = 770          # イラストの円の中心
CIRCLE_DIAMETER = 560
ATTRIBUTION_Y = 1060           # 出典表記のブロック上端(出す場合のみ)
ATTRIBUTION_SIZE = 30
PUNCH_Y = 1150                 # オチテキストのブロック上端

MASCOT_X = 150                 # 立ち絵の左端
MASCOT_BOTTOM = 1790           # 立ち絵の下端
MASCOT_HEIGHT = 420
MASCOT_FLIP = True             # 左右反転。画面の内側(右)を向かせる

TITLE_SIZE = 105
TITLE_Y = 620

# --------------------------------------------------------------------- サムネイル

# 最後の項目の振りだけを出し、オチは伏せる。うさぎを大きめに置く
THUMB_ITEM = -1                # 使う項目。-1 で最後
THUMB_EXPRESSION = "驚き"       # うさぎの表情 (config.EXPRESSIONS の名前)
THUMB_SETUP_BOTTOM = 470       # 振りのブロック下端
THUMB_SETUP_SIZE = 110
THUMB_CIRCLE_CENTER_Y = 760
THUMB_CIRCLE_DIAMETER = 540
THUMB_MASK_TEXT = "？"          # オチの代わりに出す文字。空にすると何も出さない
THUMB_MASK_SIZE = 260
THUMB_MASK_Y = 1060            # 伏せ字のブロック上端
THUMB_MASK_COLOR = "#E0243C"
THUMB_MASCOT_X = -30
THUMB_MASCOT_BOTTOM = 1900
THUMB_MASCOT_HEIGHT = 900      # 動画より大きく出す。サムネはうさぎが主役
THUMB_SCRIM_ALPHA = 0.55       # 動画より少し薄くして写真を見せる

# 表情の組み合わせ。src/tachie.py が PSD から書き出す。
# 選べる名前は `python -m src.tachie --list` で見られる。
# 衣装は既定(巫女服)のまま。顔まわりだけを切り替えている。
# 基本の姿勢。配布されている中立PNGと同じポーズ(いなば抱え + 右腕を横に)。
# 表情差分を混ぜても体が揃うようにここで固定している
BASE_POSE = {"左腕": "いなば抱え", "右腕": "横"}

EXPRESSIONS = {
    "通常":   {**BASE_POSE, "目": "基本目セット", "口": "ん",     "眉": "普通眉"},
    "笑顔":   {**BASE_POSE, "目": "にっこり",    "口": "あは",   "眉": "普通眉"},
    "驚き":   {**BASE_POSE, "目": "◯◯",        "口": "わあ",   "眉": "上がり眉", "記号など": "汗"},
    "困り":   {**BASE_POSE, "目": "ジト目",      "口": "うへー", "眉": "困り眉",   "記号など": "汗"},
    "得意":   {**BASE_POSE, "目": "なごみ目",    "口": "にやり", "眉": "普通眉"},
    "感心":   {**BASE_POSE, "目": "うっとり",    "口": "ほほえみ", "眉": "普通眉"},
}

# --------------------------------------------------------------------- 音声

SPEAKER_NAME = "中国うさぎ"     # style_id は /speakers から名前で解決する
SPEAKER_STYLE = "ノーマル"
SPEED_SCALE = 1.1
VOICEVOX_HOST = "http://127.0.0.1:50021"

# --------------------------------------------------------------------- 尺

TITLE_DURATION = 2.0           # タイトルカード
REVEAL_GAP = 0.9               # 振りを読み終えてからオチを出すまでの溜め
ITEM_GAP = 1.0                 # 項目と項目のあいだの無音
TAIL = 0.6                     # 最後の余韻

BGM_VOLUME = 0.12
BGM_DUCK = 0.45                # 読み上げ中の BGM 音量倍率

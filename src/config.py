# -*- coding: utf-8 -*-
"""座標・サイズ・色・速度をすべてここに置く。他のファイルに数値を書かない。

ここの値は初期値であって確定仕様ではない。preview.py で見ながら動かす前提。
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env(name: str) -> str | None:
    """.env から値を1つ読む。環境変数が優先。

    APIキーや接続文字列が入るので、**呼び出し側は中身を表示しないこと。**
    """
    value = os.environ.get(name)
    if value:
        return value
    path = ROOT / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith(f"{name}=") and not line.startswith("#"):
            return line.split("=", 1)[1].strip().strip("'\"")
    return None

# --------------------------------------------------------------------- 出力

WIDTH = 1080
HEIGHT = 1920
FPS = 30

# 1本の動画 = 1つの回。台本・記録・素材・成果物は episodes/001/ にまとまる。
# 個々のパスは src/episode.py が持つ(回ごとに変わるので config には置けない)
EPISODES_DIR = ROOT / "episodes"

# 回に属さないもの置き場。使い捨てのプレビューと、全回で使い回すキャッシュ
OUT_DIR = ROOT / "out"
CACHE_DIR = OUT_DIR / "cache"
# 背景素材を縦型に変換したもの。毎回変換すると書き出しが数倍遅くなるので貯める。
# 素材は回によらず同じなので、回の外に置いて使い回す
BG_CACHE = CACHE_DIR / "bg"

# 立ち絵は第三者の配布素材なので、リポジトリの外を参照する
TACHIE_DIR = ROOT.parent / "VOICEBOX" / "素材" / "うさぎ"
TACHIE_PSD = TACHIE_DIR / "psd" / "中国うさぎ立ち絵素材2.0.psd"
MASCOT = TACHIE_DIR / "中国うさぎ立ち絵素材2_0000.png"
# BGM。曲名を /publish のクレジットに使うので、置かれたファイル名のまま扱う
_BGM_FILES = sorted((ROOT / "assets").glob("*.mp3"))
BGM = _BGM_FILES[0] if _BGM_FILES else ROOT / "assets" / "bgm.mp3"
ENDCARD = ROOT / "assets" / "endcard.mp4"
# 背景に流す動画。順に使い、足りなければ先頭に戻る。
# 出所とライセンスは manifest.json に残す(第三者の素材なので必須)
BACKGROUND_DIR = ROOT / "assets" / "backgrounds"
BACKGROUND_MANIFEST = BACKGROUND_DIR / "manifest.json"
BACKGROUNDS = sorted(p for p in BACKGROUND_DIR.glob("*")
                     if p.suffix.lower() in (".mp4", ".mov", ".webm"))
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
# 立ち絵の切り抜き位置。表情を切り替えても位置がズレないよう固定する
MASCOT_CROP = (175, 185, 935, 1863)
# オチが出た瞬間にうさぎの顔を変える。振りのあいだは MASCOT_EXPRESSION
MASCOT_EXPRESSION = "通常"
MASCOT_EXPRESSION_PUNCH = "驚き"

TITLE_SIZE = 105
TITLE_Y = 620

# 立ち絵の右の空きに置くアプリの宣伝。安全域(x 370-960 / y 1370-1520)に収める
PROMO_SHOW = True
PROMO_ICON = ROOT / "assets" / "icon.png"
PROMO_TEXT = "毎日雑学 で検索！"
PROMO_X = 372                  # アイコンの左端
PROMO_CENTER_Y = 1445          # アイコンと文字の中心
PROMO_ICON_SIZE = 96
PROMO_ICON_RADIUS = 22         # アプリアイコンらしく角を丸める
PROMO_GAP = 22                 # アイコンと文字のあいだ
PROMO_TEXT_SIZE = 46

# --------------------------------------------------------------------- サムネイル

# 選んだ項目の振りだけを出し、オチは伏せる。うさぎを大きめに置く
THUMB_ITEM = 6                 # 使う項目(1始まり)。一番引きのある雑学を選ぶ。
                               # 機械的に決められないので、都度考えて書き換える
THUMB_EXPRESSION = "驚き"       # うさぎの表情 (config.EXPRESSIONS の名前)
THUMB_SETUP_BOTTOM = 470       # 振りのブロック下端
THUMB_SETUP_SIZE = 92
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

# --------------------------------------------------------------------- 写真投稿

# TikTokの写真投稿(カルーセル)用。表紙1枚 + 雑学1件ずつ7枚 = 8枚。
# 描画だけはブラウザに任せる。アプリ「毎日雑学」の見た目をCSSでそのまま書けて、
# 手描きより短く済むため。Windows標準のEdgeを使い、新しい依存は足さない
BROWSERS = [
    Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
]

# 下から300pxはキャプションやボタンが乗る。動画(SAFE_BOTTOM)より浅いのは
# 写真投稿のほうがUIの占有が小さいため
PHOTO_SAFE_BOTTOM = 300
PHOTO_MARGIN = 54              # 画面の左右と上の余白

# 色はアプリから写した(constants/Colors.ts, components/TriviaCard.tsx)。
# アプリの装飾(浮かぶ「?」・キラキラ・電球の丸・見出し下の帯)は載せない。
# 2件並べた版で試したところ画面がうるさく、読ませたい文字が負けた
PHOTO_BG = "#FFFFFF"
PHOTO_CARD = "#FFFFFF"
PHOTO_BORDER = "#EEEEEE"
PHOTO_PRIMARY = "#E60012"      # カテゴリバッジ
PHOTO_TEXT = "#1A1A1A"         # オチ
PHOTO_SUB = "#888888"          # 振りと補足
PHOTO_RULE = "#F0F0F0"         # オチと補足のあいだの線
PHOTO_PAGER = "#BBBBBB"

PHOTO_CARD_RADIUS = 96
PHOTO_CARD_BORDER = 8

# 動画と同じ書体で揃える。FONT_PATH の中身(BIZ UDPGothic)を家族名で指す
PHOTO_FONT = '"BIZ UDPGothic", "Yu Gothic UI", "Meiryo", sans-serif'

PHOTO_ART_HEIGHT = 440
PHOTO_CAT_SIZE = 30
PHOTO_SETUP_SIZE = 42
PHOTO_PUNCH_SIZE = 88
PHOTO_NOTE_SIZE = 34
PHOTO_PAGER_SIZE = 30
# 補足が長い項目は素だと溢れるので、収まるまで補足→振り→オチの順に縮める。
# その下限。ここまで縮めても入らなければ切れたまま出す(見れば分かる)
PHOTO_NOTE_MIN = 24
PHOTO_SETUP_MIN = 24
PHOTO_PUNCH_MIN = 60

# 表紙。カードを使わず、大きい文字とイラスト1点だけ。
# 「N選」の N は台本の項目数から入る
PHOTO_COVER_LEAD = "誰かに話したくなる"
PHOTO_COVER_BIG = "面白い"
PHOTO_COVER_WORD = "雑学"      # ここだけ PHOTO_PRIMARY で出す
PHOTO_COVER_LEAD_SIZE = 62
PHOTO_COVER_BIG_SIZE = 190
PHOTO_COVER_ART_HEIGHT = 460

# --------------------------------------------------------------------- 音声

SPEAKER_NAME = "中国うさぎ"     # style_id は /speakers から名前で解決する
SPEAKER_STYLE = "ノーマル"
SPEED_SCALE = 1.1
VOICEVOX_HOST = "http://127.0.0.1:50021"

# --------------------------------------------------------------------- 尺

# エンドカードでうさぎに言わせる一言。
# 読み終わりがエンドカードの終わりに来るように置くので、ロゴと文字が出る
# タイミングに「更新中」が重なる。エンドカードを差し替えても自動で合う。
ENDCARD_VOICE = "毎日雑学更新中！"
ENDCARD_VOICE_TAIL = 0.12      # 読み終わりからエンドカード終端までの余白

TITLE_DURATION = 2.0           # タイトルカード
REVEAL_GAP = 0.9               # 振りを読み終えてからオチを出すまでの溜め
ITEM_GAP = 1.0                 # 項目と項目のあいだの無音
TAIL = 0.6                     # 最後の余韻

BGM_VOLUME = 0.12
BGM_DUCK = 0.45                # 読み上げ中の BGM 音量倍率
BGM_FADE_IN = 1.2
# エンドカードには自前の音が入っているので、その手前で BGM を終わらせる
BGM_FADE_OUT = 1.5

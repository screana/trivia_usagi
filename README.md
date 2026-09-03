# 雑学ショート動画 生成パイプライン

台本(テキストのみ)から、縦型1080x1920の雑学ショート動画を作る。
開発方針は [DEVELOPMENT.md](DEVELOPMENT.md) にある。

**通しで動画が出るところまで完成。** タイトル + 雑学7項目 + エンドカード、BGM付き。

## 使い方

```bash
pip install -r requirements.txt

python -m src.preview              # 1項目目を out/preview.png に
python -m src.preview --item 3     # 3項目目
python -m src.preview --title      # タイトルカード
python -m src.preview --no-punch   # オチを出す前の状態
```

音声(VOICEVOX を起動しておくこと):

```bash
python -m src.voice --check   # 読みをカタカナで確認(音声は作らない)
python -m src.voice           # out/audio/ に 01_setup.wav 等を生成
python -m src.voice --force   # 変わっていなくても作り直す
```

動画:

```bash
python -m src.build --item 3     # 3項目目だけ
python -m src.build --item 2-4   # 範囲。項目間の間を見るとき用(16秒で約2分)
python -m src.build              # 通し (44秒で約4.5分)
python -m src.build --no-endcard
```

`out/preview.png` と、セーフエリアを重ねた `out/preview_guide.png` が出る。
1秒ほどで終わるので、レイアウトはこれを見ながら詰める。

イラストの収集:

```bash
python -m src.fetch --list "タコ"                        # 候補を見る
python -m src.fetch --get "タコ" --pick 2 --slot 0 --name octopus
```

## スラッシュコマンド

`.claude/commands/` に定義してある。

| コマンド | 役割 |
| --- | --- |
| `/script <ジャンル>` | 台本生成。候補を20個出して1件ずつ裏取りしてから7個に絞る |
| `/images` | 各項目に合うイラストを探して manifest.json を作る |
| `/review [項目]` | プレビューを実際に見てレイアウトの事故を潰す |
| `/voicecheck` | 読み上げの読みをカタカナで検証(音声を作る前に) |
| `/publish` | 概要欄・タイトル案・ハッシュタグを作る |

## ファイル構成

```
script.json           # 台本のみ。画像・話者・速度は書かない
assets/
  images/
    manifest.json     # /images が生成。これだけ git 管理
out/
  preview.png
  preview_guide.png   # セーフエリアを重ねた版
src/
  config.py           # 座標・色・フォント・速度をすべてここに
  layout.py           # 描画。preview と build で共用
  preview.py          # 静止画1枚
  voice.py            # VOICEVOX。読みの検証もここ
  tachie.py           # 立ち絵PSDから表情差分を書き出す
  build.py            # 動画の組み立て
  fetch.py            # いらすとやからイラストを取得
```

`assets/` に手で置くもの(いずれも git 管理外):

| ファイル | 用途 |
| --- | --- |
| `endcard.mp4` | 末尾に付けるエンドカード動画 |
| `bgm.mp3` | BGM |
| `AdobeStock_*.mov` | 背景に流す動画。項目ごとに順番に使う |
| `*.mp3` | BGM。最初の1本を使う(曲名はクレジットに使うのでそのまま置く) |

中国うさぎの立ち絵は**リポジトリの外**(`../VOICEBOX/素材/うさぎ/`)を参照している。
再配布不可の素材をうっかりコミットしないため。パスは `config.MASCOT`。

## 実装前に調べた結果

方針書の「実装前に必ず調べる」に従って調べたもの。判断の記録。

| 対象 | 調べたもの | 判断 |
| --- | --- | --- |
| 日本語の折り返し | **budoux** (Google製 / PyPI v0.9.1 / 2026-08 更新) | **採用**。文節で切れるので「メスのほ/うが」のような不自然な改行が消える |
| VOICEVOX クライアント | voicevox-client (PyPI v1.1.0 / 2025-08 更新) | **不採用**。audio_query と synthesis しか包んでおらず、必要な `/speakers`(名前→style_id解決)と `/accent_phrases`(voicecheck用)が無い。async専用な点も噛み合わない |
| 音声処理・ダッキング | pydub (最終リリース 2021-03) | **不採用**。5年更新が止まっている。numpy で足りる範囲 |
| テキストの縁取り | Pillow の `stroke_width` | **採用**。自前で描かない |
| PSD の読み書き | **psd-tools** (PyPI v1.19.0 / 2026-09 更新) | **採用**。PSDTool 互換の素材をそのまま扱える。pytoshop(2018年で更新停止)は書き込み用途で今回は不要 |
| いらすとや検索 | Blogger の公開フィード | **採用**。サイトのHTMLを解析せずにキーワード検索できる |
| 円形マスク | Pillow の `ImageDraw.ellipse` + `paste(mask)` | **採用**。ライブラリ不要 |

## 環境で確認したこと

- **BIZ UDPGothic Bold は単体ファイルではない。** `BIZ-UDGothicB.ttc` の
  `index=1` にある(index=0 は等幅の BIZ UDGothic)
- 中国うさぎ = ノーマル61 / おどろき62 / こわがり63 / へろへろ64。
  ただし方針どおり **ID はハードコードせず `/speakers` から名前で解決する**
- Python 3.12.10(方針書は3.11。支障なし)

## クレジット

VOICEVOX はクレジット表記が必須。動画内には出さず**概要欄**に記載する
(`/publish` が自動で含める)。

```
VOICEVOX:中国うさぎ
```

中国うさぎには共通規約とは別にキャラクター個別の利用規約がある。
立ち絵に公式イラストを使っているので、**収益化前にガイドラインを確認すること**。

いらすとやは商用利用でも1つの制作物に20点までが無償。1本7点なら範囲内。

## これから

1. ~~`preview.py` — 静止画1枚でレイアウトを詰める~~
2. ~~`voice.py` — VOICEVOX で音声生成~~
3. ~~`build.py` — 1項目だけ動画化してタイミングを詰める~~
4. ~~通しで7項目 + タイトル + BGM + エンドカード~~ ← いまここ

残っているのは `/script`(裏取り込みの台本生成)と `/publish` の実行、
それと間の取り方の調整。

## 方針書からの変更

DEVELOPMENT.md の確定事項からの差分。利用者の判断で変わったもの。

- **締めなし → エンドカード動画あり。** `assets/endcard.mp4` (4.06秒)
- **背景は単色 → 動画を流す。** `layout.base()` に背景のコマを渡すと、その上に
  白いベール(`SCRIM_ALPHA`)を敷いてから要素を重ねる。プレビューも既定で
  背景付きになる(`--no-bg` で単色)
- **1項目の流れを3段階から2段階に。** 「振り → イラスト → オチ」ではなく
  **振りとイラストを同時に出して、溜めてからオチ**
- **背景動画は項目ごとにランダムな別クリップ** (`BG_SHUFFLE_SEED`)。
  隣り合う項目は同じ映像にならない
- **立ち絵は左右反転して右寄せ** (`MASCOT_FLIP`)。画面の内側を向かせるため
- **振りは下端基準** (`SETUP_BOTTOM`)。上端基準だと2行になったとき円に食い込むため

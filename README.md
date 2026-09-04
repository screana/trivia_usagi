# 雑学ショート動画 生成パイプライン

台本(テキストのみ)から、縦型1080x1920の雑学ショート動画を作る。
開発方針は [DEVELOPMENT.md](DEVELOPMENT.md) にある。

**通しで動画が出るところまで完成。** タイトル + 雑学7項目 + エンドカード、BGM付き。

## 回(エピソード)

**1本の動画 = 1つの回。** 台本・記録・イラスト・音声・成果物は
`episodes/001/` の下にまとまっている。

```bash
python -m src.episode                    # 回の一覧と、そろっていないものを見る
python -m src.episode --new "タイトル"   # 次の番号で回を作る
```

どのコマンドも**既定は番号が一番大きい回**。過去回を触るときだけ `--ep 1` を付ける。

```
episodes/
  001/
    script.json      台本のみ                    [git 管理]
    record.json      使った雑学のIDと hee、公開情報 [git 管理]
    publish.md       概要欄                      [git 管理]
    images/          イラスト + manifest.json     [manifest だけ git 管理]
    audio/           読み上げ wav + ledger + mix  [管理外]
    video.mp4        成果物                      [管理外]
    thumbnail.png    成果物                      [管理外]
```

**なぜ回ごとに分けるか。** 以前は台本も動画も固定の名前だったので、2本目を作ると
1本目が黙って消えた。回の中で閉じていれば過去回をそのまま見に行けるし、
あとから作り直せる。

**なぜ記録を台本の隣に置くか。** 使用済みの雑学を別ファイル(`used_trivia.json`)で
持っていたときは、記録し忘れると静かにズレて、次回また同じ雑学が候補に出た。
同じディレクトリに置けば、`python -m src.episode` の一覧に「記録 0/7」と出る。

**`record.json` に hee を写し取っているのは**、`hee_count` が時間とともに増えて
いくため。採用した時点の値が残っていないと、あとから「なぜこれを選んだのか」を
たどれない。

## 使い方

```bash
pip install -r requirements.txt

python -m src.preview              # 1項目目を out/preview.png に
python -m src.preview --item 3     # 3項目目
python -m src.preview --title      # タイトルカード
python -m src.preview --no-punch   # オチを出す前の状態
python -m src.preview --ui        # ShortsのUIを重ねた版も出す
python -m src.preview --ep 1      # 過去回で描く
```

音声(VOICEVOX を起動しておくこと):

```bash
python -m src.voice --check   # 読みをカタカナで確認(音声は作らない)
python -m src.voice           # 回の audio/ に 01_setup.wav 等を生成
python -m src.voice --force   # 変わっていなくても作り直す
```

動画:

```bash
python -m src.build --item 3     # 3項目目だけ
python -m src.build --item 2-4   # 範囲。項目間の間を見るとき用(16秒で約2分)
python -m src.build              # 通し (44秒で約4.5分)
python -m src.build --no-endcard
```

通しは回の `video.mp4` に出る。`--item` を付けた抜粋は確認用なので
`out/video_item3.mp4` に出て、回のディレクトリを汚さない。

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
| `/script [件数]` | 回を作り、DBから雑学を選んで台本を組む |
| `/images` | 各項目に合うイラストを探して manifest.json を作る |
| `/review [項目]` | プレビューを実際に見てレイアウトの事故を潰す |
| `/voicecheck` | 読み上げの読みをカタカナで検証(音声を作る前に) |
| `/thumbnail [項目] [表情]` | サムネイルを作る。振りだけ出してオチは伏せる |
| `/publish` | 概要欄・タイトル案・ハッシュタグを作る |

## ファイル構成

```
episodes/             # 回ごとの一式(上の「回」を参照)
.env                  # DBの接続文字列(git管理外)
out/                  # 回に属さないもの。すべて git 管理外
  preview.png         # 確認用。毎回上書きされる
  preview_guide.png   # セーフエリアを重ねた版
  preview_ui.png      # ShortsのUIを模した重ね絵(--ui のとき)
  thumbnail_guide.png
  video_item3.mp4     # --item で出した抜粋
  cache/bg/           # 背景の縦型変換。素材は回によらず同じなので使い回す
src/
  config.py           # 座標・色・フォント・速度をすべてここに
  episode.py          # 回の解決とパス、記録の読み書き
  layout.py           # 描画。preview と build で共用
  preview.py          # 静止画1枚
  voice.py            # VOICEVOX。読みの検証もここ
  trivia.py           # DBから雑学の候補を取る(読み取り専用)
  tachie.py           # 立ち絵PSDから表情差分を書き出す
  thumbnail.py        # サムネイル
  build.py            # 動画の組み立て
  fetch.py            # いらすとやからイラストを取得
AGENTS.md             # エージェント向けの作業指示。新しいセッションが最初に読む
DEVELOPMENT.md        # 開発方針
```

回ごとに変わるパスは `src/episode.py` が持つ。`config.py` は座標や色など
**回によらない値だけ**を持つ。

`assets/` に手で置くもの(いずれも git 管理外):

| ファイル | 用途 |
| --- | --- |
| `endcard.mp4` | 末尾に付けるエンドカード動画。尺は実ファイルから読むので長さは自由 |
| `AdobeStock_*.mov` | 背景に流す動画。項目ごとにランダムな1本を使う |
| `*.mp3` | BGM。最初の1本を使う(曲名はクレジットに使うのでそのまま置く) |

中国うさぎの立ち絵と PSD は**リポジトリの外**(`../VOICEBOX/素材/うさぎ/`)を参照している。
第三者の配布素材をうっかりコミットしないため。パスは `config.TACHIE_DIR`。

## 雑学の選定

台本の素材はアプリのデータベース(Neon / Postgres)から持ってくる。
**元データは裏取り済み**なので、web検索での事実確認はしない。

```bash
python -m src.trivia --list 20 --full   # 未使用の上位を見る
python -m src.trivia --show 112 16      # 指定IDの全文
python -m src.trivia --mark 112 67 …    # 回の記録に書く(台本と同じ順に並べる)
python -m src.trivia --used             # これまでの回で使ったもの
```

`--mark` に渡すIDの並びは**台本の項目の並びと同じにする**。1番目のIDが1項目目、
という対応で `record.json` に入る。hee_count・category・DBの題は自動で写し取る。

`hee_count` はアプリ内で「へぇ」ボタンが押された**強さの合計**(1人あたり1〜10)。
実際の反応が数字で残っているので、面白さの推測より当てになる。

### 接続

`.env` に読み取り専用の接続文字列を1行だけ置く(**git管理外**)。

```
TRIVIA_DATABASE_URL=postgresql://video_ro:…@ep-….neon.tech/neondb?sslmode=require
```

`src/trivia.py` は **SELECT しか実行しない**。使用済みの記録は DB ではなく
回の `record.json` に残す。

### Neon 側の設定でつまずいた点

- **コンソールから作ったロールは `neon_superuser` を継承する。** 読み取り専用に
  したいなら SQL で `CREATE ROLE` する必要がある
- **`ALTER DEFAULT PRIVILEGES` は実行者が作るテーブルにしか効かない。**
  アプリのテーブルは別のオーナーが作っているので `FOR ROLE <オーナー>` が要る
- **`trivia` は RLS が有効。** SELECT を許すポリシーが `app_user` 限定だったため、
  権限を付けても0件に見えた。`ALTER POLICY trivia_select_all ON public.trivia
  TO app_user, video_ro;` で解決

### 採用の順番

**`hee_count` の高い順**。ただし古い雑学ほど票が積み上がっていて、
id と hee_count の相関は **-0.65**(ID帯ごとの平均は 60.7 → 20.5 と3倍の開き)。
単純な降順だと古いものから消費される。

いまは在庫が306件あるので当面それでよい。**新しいものばかり残るようになったら**、
ID帯ごとの相対評価(各帯の中での順位で選ぶ)に切り替える。

`trivia_hees` は RLS で見えないため、投票人数で割った「1人あたりの強さ」は
出せない。必要になったら集計ビューを作って `video_ro` に開ける。

## 画面の作り

1項目は2枚の画面でできている。**振りとイラストを同時に出す → 溜めてオチを足す。**
オチが出るのは振りを読み終えてから(`REVEAL_GAP` の 0.9 秒)。

**オチと同時にうさぎの顔が変わる**(`MASCOT_EXPRESSION` → `MASCOT_EXPRESSION_PUNCH`)。
表情は PSD から作ったものを使う。切り抜き位置を `MASCOT_CROP` で固定してあるので、
表情を変えても体は1ピクセルも動かない(表情ごとの外接矩形で切ると、記号を足した
表情を混ぜたときに立ち絵が跳ねる)。

画面は `layout.py` が**透過1枚**として作り、背景動画に重ねるだけにしている。
プレビューと本番で描画ロジックが分かれないようにするため。

**振りは下端基準**(`SETUP_BOTTOM`)。上端基準だと2行になったとき下に伸びて
中央の円に食い込む。下端で揃えれば行数が変わっても円との間隔は一定になる。

**立ち絵の右の空きにアプリの宣伝を置いている**(`PROMO_*`)。角を丸めたアイコンと
「毎日雑学 で検索！」。オチの下・立ち絵の横は他に使い道がないので使う。
セーフエリアの内側に収めてあり、余白は右67px・下27px・立ち絵から32px・
オチから37px。文言を長くすると右にはみ出すので、変えたら `--item` を何個か
書き出して確認する。

### 背景動画

素材は 1920x1080 の横長なので、中央を切り出して縦型にしている。左右がかなり
落ちるので、被写体が中央にある素材を選ぶこと。

映像の上に黒文字を置くと読みにくいので、**白いベールを一枚敷いている**
(`SCRIM_ALPHA`、既定 0.62)。4本すべてのクリップで 0/35/50/62/75% を書き出して
比べ、いちばん暗いクリップでも安定して読める 62% にした。

**背景は1項目につき1本を通しで流す。** 画面が切り替わるたびにクリップを取り直すと
頭出しに戻り、止まったり動いたりして見える(`Scene` 単位で同じクリップの続きを
切り出している)。割り当てはシャッフルし(`BG_SHUFFLE_SEED`)、隣り合う項目が
同じ映像にならないようにしている。

### 実際の見え方を確かめる

```bash
python -m src.preview --item 1 --ui
```

`out/preview_ui.png` に、Shorts のUIを模した重ね絵が出る。何が隠れるかを
セーフエリアの枠より具体的に確認できる。

**本物のUI画像は使っていない。** Google の著作物なので、位置と大きさだけを
写した自前のモックを描いている(`layout.with_youtube_ui`)。アイコンの形は
似せていない。目的は遮蔽の確認なので、それで足りる。

**引っかかったところ:** `ImageDraw.Draw(im, "RGBA")` は半透明を**合成せず上書き**
する。帯が真っ黒になって「全部隠れる」ように見えてしまった。別レイヤに描いて
`alpha_composite` する必要がある。

## 立ち絵の表情差分

配布素材の PSD から表情を組み立てて書き出せる(readme に「改変・加工しての
利用も可能」と明記されているのを確認済み)。

```bash
python -m src.tachie --list                       # 選べるパーツを見る
python -m src.tachie --all-presets                # config の表情を全部作る
python -m src.tachie --make 目=にっこり 口=あは -o smile.png
```

素材は PSDTool 向けの命名規則(`*` は同じグループで1つだけ表示、`!` は常に表示)
に従っているので、それに合わせて表示を切り替えてから合成する。選べるのは
**口19種 / 目9種 / 眉4種 / 顔色5種 / 記号5種 / 腕は左右5種ずつ**。
**衣装は既定(巫女服)のまま触らない。**

表情の組み合わせは `config.EXPRESSIONS`。体の姿勢は `BASE_POSE` で固定していて、
配布されている中立PNGと同じ(いなば抱え + 右腕を横に)。表情を変えても体がズレない。

**引っかかったところ:** `psd.composite()` はそのままだと PSD に保存された
合成済みプレビュー(RGB・アルファなし)を返すことがあり、背景が黒く潰れた PNG が
できる。`force=True` でレイヤーから組み直させる必要がある。
腕のグループは「衣装差分」と「巫女服」の下に同名で2つあるので、両方に同じ選択を
当てないと食い違う。

## サムネイル

```bash
python -m src.thumbnail                    # 回の thumbnail.png
python -m src.thumbnail --item 3
python -m src.thumbnail --expression 困り
python -m src.thumbnail --no-mask          # 伏せ字を出さない
```

**一番引きのある項目の振りだけを出して、オチは「？」で伏せる。** 答えが気になる
状態で止めるのが狙い。うさぎは動画より大きく置いて主役にしている(高さ900px)。

どの項目を使うかは `config.THUMB_ITEM`(1始まり)。機械的に決められないので
台本を読み比べて選ぶ。選び方の目安は `.claude/commands/thumbnail.md` にある。
**振りは台本の文言をそのまま使う。釣るために書き換えない。**

描画は `layout.py` の部品を使い回している。文字の折り返しやフチの出方を動画と
揃えるため。ベールは動画より薄く(0.55)して背景の写真を少し見せている。

## 音声

読み上げ・BGM・エンドカードの音を numpy で1本の wav にまとめてから moviepy に
渡す。どこで何が鳴るかが1か所で読める。

BGM は読み上げ中だけ `BGM_DUCK` まで下げ、**エンドカードの手前で終わらせる**。
エンドカードには自前の音が入っているので、重ねると両方の音楽がぶつかって濁る。

エンドカードでは `ENDCARD_VOICE`(「毎日雑学更新中！」)をうさぎに言わせる。
**読み終わりがエンドカードの終端に来るように置く**ので、「更新中」がロゴと文字の
出るタイミングに重なる。エンドカードを差し替えても長さを測り直して合わせる。

## 速さのために自前にしたところ

書き出しは最初 5.4 秒の動画に 69 秒かかっていた。計測して2つ直した。

- **背景素材を先に縦型へ変換して貯める**(`vertical_cache`)。元素材は 49Mbps の
  1920x1080 で、毎フレーム切り出して拡大するのが重かった
- **アルファ合成を自前で書いた**(`_blend`)。moviepy の `CompositeVideoClip` でも
  同じ絵になるが、マスク処理が1フレーム 190ms かかっていた。整数演算で直に
  重ねると 80ms 台になる(出力が moviepy と丸め誤差1以内で一致することを確認済み)

## 調整したいとき

| やりたいこと | 触る場所(すべて `src/config.py`) |
| --- | --- |
| 文字の大きさ・位置 | `FONT_SIZE` / `SETUP_BOTTOM` / `PUNCH_Y` |
| イラストの円 | `CIRCLE_CENTER_Y` / `CIRCLE_DIAMETER` |
| うさぎの位置・大きさ | `MASCOT_X` / `MASCOT_BOTTOM` / `MASCOT_HEIGHT` |
| うさぎの表情 | `MASCOT_EXPRESSION`(振り) / `MASCOT_EXPRESSION_PUNCH`(オチ) |
| アプリの宣伝 | `PROMO_TEXT` / `PROMO_X` / `PROMO_CENTER_Y` / `PROMO_SHOW` |
| 間の取り方 | `REVEAL_GAP`(振り→オチ) / `ITEM_GAP`(項目間) |
| 背景の見え方 | `SCRIM_ALPHA` / `BG_SHUFFLE_SEED` |
| BGM | `BGM_VOLUME` / `BGM_DUCK` / `BGM_FADE_OUT` |
| サムネイル | `THUMB_*` |

レイアウトを詰めるときは `python -m src.preview` が1秒以内で終わるので、
これを見ながら回す。動画を回して座標を探さない。

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

残っているのは `/publish` の実行と効果音。

## 方針書からの変更

DEVELOPMENT.md の確定事項からの差分。利用者の判断で変わったもの。

- **締めなし → エンドカード動画あり。** `assets/endcard.mp4`(尺は実ファイルから読む)
- **サムネイル生成を追加。** 方針書では未実装扱いだった
- **立ち絵の表情差分を PSD から生成できるようにした**
- **背景は単色 → 動画を流す。** `layout.base()` に背景のコマを渡すと、その上に
  白いベール(`SCRIM_ALPHA`)を敷いてから要素を重ねる。プレビューも既定で
  背景付きになる(`--no-bg` で単色)
- **1項目の流れを3段階から2段階に。** 「振り → イラスト → オチ」ではなく
  **振りとイラストを同時に出して、溜めてからオチ**
- **背景動画は項目ごとにランダムな別クリップ** (`BG_SHUFFLE_SEED`)。
  隣り合う項目は同じ映像にならない
- **立ち絵は左右反転して右寄せ** (`MASCOT_FLIP`)。画面の内側を向かせるため
- **振りは下端基準** (`SETUP_BOTTOM`)。上端基準だと2行になったとき円に食い込むため

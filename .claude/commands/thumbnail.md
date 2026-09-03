---
description: サムネイルを作る。最後の項目の振りだけを出してオチは伏せる
argument-hint: [項目番号] [表情]
---

サムネイルを作って、**実際に見て**確認する。

```bash
python -m src.thumbnail                      # 最後の項目で作る
python -m src.thumbnail --item 3             # 項目を指定
python -m src.thumbnail --expression 困り     # うさぎの表情を変える
python -m src.thumbnail --no-mask            # 伏せ字を出さない
```

書き出したら `out/thumbnail_guide.png` を Read ツールで開いて確認する。

## 狙い

**振りだけを出して、オチは伏せる。** 何が答えなのか気になる状態で止める。
うさぎは動画より大きく置いて主役にする。

## 見る観点

- 振りの文字が小さくないか。サムネは一覧で小さく表示される
- うさぎの表情が内容と合っているか(驚き / 困り / 得意 など)
- イラストとうさぎ、伏せ字が重なって潰れていないか
- 下部はアプリのUIに隠れるので、大事な要素を置かない

## 表情を変えるとき

使える表情は `config.EXPRESSIONS` にある。無ければ PSD から作られる
(`python -m src.tachie --list` で選べるパーツが見られる)。

新しい表情を足すなら `config.EXPRESSIONS` に組み合わせを追加する。
体の姿勢は `BASE_POSE` で固定してあるので、顔まわりだけ指定すればよい。

## 直すとき

数値は `src/config.py` の `THUMB_*` だけを触る。

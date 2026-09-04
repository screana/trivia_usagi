---
description: 台本の各項目に合うイラストを探して回の images/ と manifest.json を作る
---

台本の各項目に合うイラストを用意する。対象は既定で一番新しい回。

## 優先順位

1. **いらすとや** — 絵柄が揃うのでまずここを探す
2. パブリックドメイン / CC0
3. CC BY 系(表示が必要。`attribution` に「作者 / ライセンス」を入れる)

**ライセンスが不明な画像は使わない。**

## 手順

項目ごとに、内容に合う検索語を自分で考えて候補を見る。

```bash
python -m src.fetch --list "タコ"
```

候補のタイトルを読んで、**その項目のオチに合うものを選ぶ**。
たとえば「タコはメスのほうがおいしい」なら食べ物として描かれたタコを選ぶ。
キャラクター化されたものや、別の文脈のもの(受験応援のタコ等)は避ける。

決めたら取得する。`--slot` は台本の何項目目か(0始まり)。

```bash
python -m src.fetch --get "タコ" --pick 2 --slot 0 --name octopus
```

`episodes/NNN/images/manifest.json` は `src/fetch.py` が書く。いらすとやは表示義務がないので
`attribution` は `null` になる。

## いらすとや以外を使うとき

`episodes/NNN/images/` に手で置いて、同じ場所の `manifest.json` に追記する。

```json
"3": {
  "file": "03_banana.jpg",
  "source": "Wikimedia Commons",
  "attribution": "作者名 / CC BY-SA 4.0",
  "url": "https://..."
}
```

`attribution` が `null` でなければ、イラストの直下にその文字列が小さく表示される。
リンクは動画内に入らないので、`url` は概要欄用に必ず残す。

## 注意

いらすとやは商用利用でも**1つの制作物に20点までが無償**。1本7点なら範囲内。
「1制作物」の解釈(動画1本かチャンネル全体か)は収益化前に確認すること。

## 終わったら

`python -m src.preview --item N` で各項目を描いて、円の中でイラストが
小さすぎないか、内容が合っているかを目で見て確認する。

# -*- coding: utf-8 -*-
"""写真版の組み立てが壊れていないか見る。

    python test_photo.py

DBもブラウザも使わない。折り返し候補の入れ方と、8枚の組み立てだけを確かめる。
ここが黙って壊れると、出来たPNGを1枚ずつ見るまで気づけない。
"""
from src import config, photo


def test_breaks():
    # 台本の明示的な改行は必ず <br> として残る
    assert photo.breaks("あ\nい") == "あ<br>い"

    # 文節の切れ目にだけ折り返し候補が入る。文節の途中には入らない
    marked = photo.breaks("ネギトロの由来にはネギもトロも関係ない")
    assert "<wbr>" in marked
    assert marked.replace("<wbr>", "") == "ネギトロの由来にはネギもトロも関係ない"

    # HTMLとして危ない文字は逃がす
    assert photo.breaks("<b>&") == "&lt;b&gt;&amp;"


def test_slides():
    items = [{"hee": i, "category": "科学", "setup": "振り", "punch": "オチ",
              "note": "補足", "image": None} for i in range(photo.CARDS)]
    built = photo.slides(items)
    assert len(built) == photo.COUNT

    # 表紙は「N選」を項目数から出し、カードを使わない
    assert f"{photo.CARDS}選" in built[0]
    assert "class=\"card\"" not in built[0]

    # 中身はページ番号が 2 から始まる(1枚目は表紙)
    assert f"2 / {photo.COUNT}" in built[1]
    assert f"{photo.COUNT} / {photo.COUNT}" in built[-1]

    # 画像が無い項目でも落ちず、img を出さない
    assert "<img" not in built[1]


def test_stylesheet_uses_config():
    css = photo.stylesheet()
    assert config.PHOTO_PRIMARY in css
    assert f"height:{config.HEIGHT}px" in css
    # セーフエリアの目安は本番のページには出さない
    assert ".guide" in css and "class='guide'" not in photo.page("x")


if __name__ == "__main__":
    test_breaks()
    test_slides()
    test_stylesheet_uses_config()
    print("ok")

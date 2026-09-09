# -*- coding: utf-8 -*-
"""TikTokの写真投稿(カルーセル)用の8枚を作る。

    python -m src.photo             # episodes/001/photos/01.png … 08.png
    python -m src.photo --ep 1      # 過去回で作る
    python -m src.photo --html      # HTMLだけ作る(レイアウトを詰めるとき)

**動画と同じ回・同じ素材から作る。** 雑学は選び直さない。振りとオチは台本
(`script.json`)、補足はDBの `content`、イラストは回の `images/` をそのまま使う。

**描画だけはブラウザに任せる。** アプリ「毎日雑学」の見た目(角丸・影・バッジ)は
CSSで書けば数行で済み、PILで描くと同じ絵を出すのに何倍もかかる。Windows標準の
Edgeをヘッドレスで叩くので、新しい依存は増えない。

**折り返しは動画と同じ。** layout.phrases() で文節に割り、その境目にだけ `<wbr>` を
置く。ブラウザ任せだと「来ていると思わ / れがちですが」のように文節の途中で切れる。

出所の記録は動画と共通(`images/manifest.json`)。`/publish` がそこからクレジットを
書くので、写真側で新しく持つものは無い。
"""
from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config, episode, layout, trivia


class PhotoError(Exception):
    pass


COUNT = 8          # 表紙1枚 + 雑学7件
CARDS = COUNT - 1


# --------------------------------------------------------------------- 材料


def collect(ep) -> list[dict]:
    """回から8枚分の材料を集める。台本・記録・マニフェスト・DBを1つに並べる。"""
    script = episode.load_script(ep)
    items = script.get("items") or []
    if len(items) != CARDS:
        raise PhotoError(f"台本の項目が {len(items)} 件です。写真版は {CARDS} 件で作ります")

    record = episode.load_record(ep).get("items") or []
    if len(record) != len(items):
        raise PhotoError(
            f"記録が {len(record)} 件で台本と合いません。\n"
            f"  python -m src.trivia --mark … で回の記録を先に揃えてください"
        )

    ids = [r["id"] for r in record]
    notes = {r["id"]: (r["content"] or "") for r in trivia.by_ids(ids)}
    manifest = episode.load_manifest(ep)

    out = []
    for i, (item, marked) in enumerate(zip(items, record)):
        entry = manifest.get(str(i)) or {}
        image = ep.images / entry["file"] if entry.get("file") else None
        if image is not None and not image.exists():
            # マニフェストは追跡するが画像は追跡しないので、別のマシンで作った回では起こる
            print(f"警告: 画像がありません: {image}", file=sys.stderr)
            image = None
        out.append({
            "hee": marked.get("hee") or 0,
            "category": marked.get("category") or "雑学",
            "setup": item["setup"],
            "punch": item["punch"],
            "note": notes.get(marked["id"], ""),
            "image": image,
        })
    return out


# --------------------------------------------------------------------- 描く


def breaks(text: str) -> str:
    """折り返してよい位置にだけ <wbr> を置く。台本の改行は <br> として残す。

    CSS の word-break:keep-all と組みで、ここ以外では折れなくなる。
    """
    return "<br>".join(
        "<wbr>".join(html.escape(chunk) for chunk in layout.phrases(line))
        for line in text.split("\n")
    )


def stylesheet() -> str:
    c = config
    return f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#333;font-family:{c.PHOTO_FONT}}}
img{{display:block}}
.slide{{
  position:relative;width:{c.WIDTH}px;height:{c.HEIGHT}px;background:{c.PHOTO_BG};
  padding:{c.PHOTO_MARGIN}px {c.PHOTO_MARGIN}px calc({c.PHOTO_MARGIN}px + {c.PHOTO_SAFE_BOTTOM}px);
  display:flex;flex-direction:column;margin:0 auto 24px;overflow:hidden;
}}
/* min-height:0 が要る。flexの既定(auto)だとカードが中身に押し広げられて、
   溢れを検知できないまま画面からはみ出す */
.card{{
  flex:1;min-height:0;background:{c.PHOTO_CARD};
  border:{c.PHOTO_CARD_BORDER}px solid {c.PHOTO_BORDER};border-radius:{c.PHOTO_CARD_RADIUS}px;
  padding:44px 56px;display:flex;flex-direction:column;box-shadow:0 14px 24px rgba(0,0,0,.06);
}}
.cat{{align-self:flex-start;background:{c.PHOTO_PRIMARY};color:#fff;font-weight:bold;
  font-size:{c.PHOTO_CAT_SIZE}px;letter-spacing:2px;padding:12px 34px;border-radius:60px;
  flex:0 0 auto}}
.body{{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;
  align-items:center;justify-content:center;text-align:center}}
/* <wbr> を置いた位置でだけ折る。1行に収まらない文節だけは例外的に途中で折らせる */
.setup,.punch,.note{{word-break:keep-all;overflow-wrap:anywhere}}
/* イラストは縮ませない。min-height:0 の下では縦に潰れる */
.art{{flex:0 0 auto;height:{c.PHOTO_ART_HEIGHT}px;width:auto;object-fit:contain;
  margin-bottom:34px}}
.setup{{font-size:{c.PHOTO_SETUP_SIZE}px;font-weight:600;color:{c.PHOTO_SUB};
  line-height:1.6;margin-bottom:22px}}
.punch{{font-size:{c.PHOTO_PUNCH_SIZE}px;font-weight:900;color:{c.PHOTO_TEXT};line-height:1.3}}
.note{{font-size:{c.PHOTO_NOTE_SIZE}px;font-weight:600;color:{c.PHOTO_SUB};line-height:1.75;
  margin-top:44px;padding-top:40px;border-top:4px solid {c.PHOTO_RULE}}}
.pager{{position:absolute;left:0;right:0;bottom:calc({c.PHOTO_SAFE_BOTTOM}px + 8px);
  text-align:center;font-size:{c.PHOTO_PAGER_SIZE}px;font-weight:bold;color:{c.PHOTO_PAGER}}}
/* 表紙。カードを使わず、大きい文字とイラスト1点だけ */
.cover{{justify-content:center;align-items:center;text-align:center}}
.cover .lead{{font-size:{c.PHOTO_COVER_LEAD_SIZE}px;font-weight:900;color:{c.PHOTO_SUB};
  letter-spacing:2px}}
.cover .big{{font-size:{c.PHOTO_COVER_BIG_SIZE}px;font-weight:900;color:{c.PHOTO_TEXT};
  line-height:1.12;letter-spacing:4px;margin-top:12px}}
.cover .big em{{font-style:normal;color:{c.PHOTO_PRIMARY}}}
.cover .art{{height:{c.PHOTO_COVER_ART_HEIGHT}px;margin-top:70px}}
/* セーフエリアの目安。確認用のプレビューにしか出さない */
.guide .slide::after{{content:"";position:absolute;left:0;right:0;bottom:0;
  height:{c.PHOTO_SAFE_BOTTOM}px;border-top:4px dashed rgba(230,0,18,.5);
  background:rgba(230,0,18,.06)}}
"""


def fitter() -> str:
    """縦に収まらない項目を、収まるまで縮める。

    justify-content:center だと scrollHeight が溢れを拾わないので、
    子の実高さを足して測る。
    """
    c = config
    return f"""<script>
const used = (body) => [...body.children].reduce(
  (h, el) => h + el.offsetHeight + parseFloat(getComputedStyle(el).marginBottom || 0), 0);
const shrink = (body, el, from, min) => {{
  if (!el) return;
  for (let size = from; size > min && used(body) > body.clientHeight; size--) {{
    el.style.fontSize = size + 'px';
  }}
}};
for (const body of document.querySelectorAll('.card .body')) {{
  shrink(body, body.querySelector('.note'), {c.PHOTO_NOTE_SIZE}, {c.PHOTO_NOTE_MIN});
  shrink(body, body.querySelector('.setup'), {c.PHOTO_SETUP_SIZE}, {c.PHOTO_SETUP_MIN});
  shrink(body, body.querySelector('.punch'), {c.PHOTO_PUNCH_SIZE}, {c.PHOTO_PUNCH_MIN});
}}
</script>"""


def art(image: Path | None, cls: str = "art") -> str:
    # 絶対URIで指す。HTMLをどこに置いても壊れない
    return f'<img class="{cls}" src="{image.as_uri()}" alt="">' if image else ""


def cover_slide(items: list[dict]) -> str:
    c = config
    best = max(items, key=lambda x: x["hee"])
    return f"""<div class="slide cover">
  <div class="lead">{html.escape(c.PHOTO_COVER_LEAD)}</div>
  <div class="big">{html.escape(c.PHOTO_COVER_BIG)}<br>"""\
        f"""<em>{html.escape(c.PHOTO_COVER_WORD)}</em>{len(items)}選</div>
  {art(best["image"])}
</div>"""


def card_slide(item: dict, page: int) -> str:
    return f"""<div class="slide">
  <div class="card">
    <div class="cat">{html.escape(item['category'])}</div>
    <div class="body">
      {art(item["image"])}
      <div class="setup">{breaks(item['setup'])}</div>
      <div class="punch">{breaks(item['punch'])}</div>
      <div class="note">{breaks(item['note'])}</div>
    </div>
  </div>
  <div class="pager">{page} / {COUNT}</div>
</div>"""


def slides(items: list[dict]) -> list[str]:
    return [cover_slide(items)] + [card_slide(it, n + 2) for n, it in enumerate(items)]


def page(body: str, *, guide: bool = False) -> str:
    cls = " class='guide'" if guide else ""
    return (f"<meta charset='utf-8'>\n<style>{stylesheet()}</style>\n"
            f"<body{cls}>\n{body}\n{fitter()}\n")


# --------------------------------------------------------------------- 撮る


def browser() -> Path:
    for path in config.BROWSERS:
        if path.exists():
            return path
    raise PhotoError(
        "ヘッドレスで使えるブラウザが見つかりません。\n"
        "  Microsoft Edge か Chrome を入れるか、config.BROWSERS にパスを足してください"
    )


def await_file(out: Path, timeout: float = 60.0) -> None:
    """PNGが書き終わるまで待つ。

    **Edgeは起動したプロセスが終了したあとにPNGを書く。** 起動を待っただけでは
    まだファイルが無く、直後に見に行くと「書き出せていない」と誤判定する。
    大きさが変わらなくなった時点を書き終わりとみなす。
    """
    deadline = time.monotonic() + timeout
    size = -1
    while time.monotonic() < deadline:
        if out.exists():
            current = out.stat().st_size
            if current > 0 and current == size:
                return
            size = current
        time.sleep(0.2)
    raise PhotoError(
        f"ブラウザが {timeout:.0f} 秒で書き出しませんでした: {out}\n"
        f"  {config.BROWSERS[0].name} を単体で起動できるか確かめてください"
    )


def shoot(exe: Path, source: Path, out: Path, profile: Path) -> None:
    """1枚をPNGにする。

    `--user-data-dir` を分けないと起動中のEdgeに相乗りして、何も書かずに終了する。
    """
    out.unlink(missing_ok=True)
    subprocess.run(
        [str(exe), "--headless=new", "--disable-gpu", "--no-first-run",
         f"--user-data-dir={profile}", "--hide-scrollbars",
         "--virtual-time-budget=4000",
         f"--window-size={config.WIDTH},{config.HEIGHT}",
         f"--screenshot={out}", source.as_uri()],
        check=False, capture_output=True,
    )
    await_file(out)


def render(ep, *, shots: bool = True) -> list[Path]:
    items = collect(ep)
    pages = slides(items)

    ep.photos.mkdir(parents=True, exist_ok=True)
    sources = []
    for i, slide in enumerate(pages, start=1):
        source = ep.photos / ("%02d.html" % i)
        source.write_text(page(slide), encoding="utf-8")
        sources.append(source)

    # 確認用の1枚もの。全部が縦に並び、セーフエリアの目安が乗る。
    # 使い捨てなので回のディレクトリではなく out/ に置く
    config.OUT_DIR.mkdir(parents=True, exist_ok=True)
    (config.OUT_DIR / "photo_preview.html").write_text(
        page("\n".join(pages), guide=True), encoding="utf-8")

    if not shots:
        return []

    exe = browser()
    written = []
    # TemporaryDirectory は使えない。**Edgeは終了後もプロファイルを掴んでいることがあり**、
    # 後片付けが PermissionError で落ちる。8枚とも正しく書けているのに
    # コマンドが異常終了して見える。消せなければ諦める(OSがいずれ片付ける)
    tmp = Path(tempfile.mkdtemp(prefix="photo-"))
    try:
        for i, source in enumerate(sources, start=1):
            out = ep.photos / ("%02d.png" % i)
            shoot(exe, source, out, tmp / ("p%02d" % i))
            written.append(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return written


# --------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--html", action="store_true",
                        help="PNGを書かず、HTMLとプレビューだけ作る")
    episode.add_argument(parser)
    args = parser.parse_args(argv)

    try:
        ep = episode.resolve(args.ep)
        written = render(ep, shots=not args.html)
        preview = config.OUT_DIR / "photo_preview.html"
        print(f"回 {ep} / {ep.title()}")
        if written:
            print(f"  {ep.photos} に {len(written)} 枚")
        else:
            print(f"  {ep.photos} にHTMLだけ書きました")
        print(f"  {preview} (全{COUNT}枚 + セーフエリアの目安)")
        return 0
    except (PhotoError, episode.EpisodeError, trivia.TriviaError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

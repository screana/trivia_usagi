# -*- coding: utf-8 -*-
"""1本の動画 = 1つの「回」。episodes/001/ の下に台本・記録・素材・成果物をまとめる。

    python -m src.episode                     # 回の一覧
    python -m src.episode --new "タイトル"    # 次の番号で作る

**なぜ回ごとにディレクトリを分けるか。** 以前は台本も動画も固定の名前だったので、
2本目を作ると1本目が黙って消えた。回の中で閉じていれば過去回をそのまま見に行けるし、
あとから作り直せる。

**なぜ記録を台本の隣に置くか。** 使用済みの雑学を別ファイル(used_trivia.json)に
持っていたときは、記録し忘れると静かにズレた。同じディレクトリに置けば、
台本があって記録がない状態が一目でわかる。

既定はいつも**番号が一番大きい回**。過去回を触るときだけ `--ep 1` を付ける。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import config

NAME = re.compile(r"^\d{3}$")


class EpisodeError(Exception):
    pass


@dataclass(frozen=True)
class Episode:
    number: int
    dir: Path

    # 台本と記録。この2つだけが git に入る
    @property
    def script(self) -> Path:
        return self.dir / "script.json"

    @property
    def record(self) -> Path:
        return self.dir / "record.json"

    # 素材と成果物。台本から作り直せるので追跡しない
    @property
    def images(self) -> Path:
        return self.dir / "images"

    @property
    def manifest(self) -> Path:
        return self.images / "manifest.json"

    @property
    def audio(self) -> Path:
        return self.dir / "audio"

    @property
    def mix(self) -> Path:
        return self.audio / "mix.wav"

    @property
    def video(self) -> Path:
        return self.dir / "video.mp4"

    @property
    def thumbnail(self) -> Path:
        return self.dir / "thumbnail.png"

    @property
    def photos(self) -> Path:
        return self.dir / "photos"

    @property
    def publish(self) -> Path:
        return self.dir / "publish.md"

    def title(self) -> str:
        if self.script.exists():
            return json.loads(self.script.read_text(encoding="utf-8")).get("title", "")
        return ""

    def __str__(self) -> str:
        return "%03d" % self.number


# --------------------------------------------------------------------- 探す


def episodes() -> list[Episode]:
    if not config.EPISODES_DIR.exists():
        return []
    found = [Episode(int(p.name), p)
             for p in config.EPISODES_DIR.iterdir() if p.is_dir() and NAME.match(p.name)]
    return sorted(found, key=lambda e: e.number)


def latest() -> Episode | None:
    found = episodes()
    return found[-1] if found else None


_FETCHED = False


def check_fresh() -> None:
    """remote に手元より新しいコミットがあれば止める。

    **手順書に「先に git pull」と書いても飛ばされる。** 飛ばした結果は静かで、
    回の既定は「手元で番号が一番大きい回」なので**古い回で作ってしまう**し、
    台本が更新されていれば**更新前の振り・オチ**で作る。件数も回番号も辻褄が
    合うため、どのチェックにも引っかからない。実際に第5回が remote にあるのに
    004 で作りかけた。

    **remote を見に行けないときは素通りする**(オフライン・upstream 無し)。
    確認できないことを理由に作業を止めるほうが困る。
    """
    global _FETCHED
    if _FETCHED:
        return
    _FETCHED = True
    try:
        # ponytail: 毎回 fetch する。遅くて邪魔になったら、最終 fetch 時刻を見て間引く
        subprocess.run(["git", "fetch", "--quiet"], cwd=config.ROOT,
                       check=True, capture_output=True, timeout=30)
        behind = subprocess.run(["git", "rev-list", "--count", "HEAD..@{u}"],
                                cwd=config.ROOT, check=True, capture_output=True,
                                text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return
    if behind.isdigit() and int(behind) > 0:
        raise EpisodeError(
            f"remote に手元より新しいコミットが {behind} 件あります。\n"
            f"  git pull してから、もう一度実行してください\n"
            f"  pull せずに進めると、古い回や更新前の台本で作ります(エラーになりません)"
        )


def resolve(number: int | None = None) -> Episode:
    """--ep の値から回を決める。指定がなければ一番新しい回。"""
    check_fresh()
    if number is None:
        found = latest()
        if found is None:
            raise EpisodeError(
                "回がまだありません。\n"
                '  python -m src.episode --new "タイトル" で作ってください'
            )
        return found
    target = Episode(number, config.EPISODES_DIR / ("%03d" % number))
    if not target.dir.exists():
        have = ", ".join(str(e) for e in episodes()) or "なし"
        raise EpisodeError(f"回 {target} がありません (ある回: {have})")
    return target


def create(title: str) -> Episode:
    check_fresh()          # 番号を取り合わないよう、作る前にも見る
    number = (latest().number + 1) if latest() else 1
    target = Episode(number, config.EPISODES_DIR / ("%03d" % number))
    target.dir.mkdir(parents=True)
    write_json(target.script, {"title": title, "items": []})
    write_json(target.record, {"episode": number, "created": date.today().isoformat(),
                               "published": None, "url": None, "items": []})
    return target


def add_argument(parser: argparse.ArgumentParser) -> None:
    """どのコマンドでも同じ書き方で回を指定できるようにする。"""
    parser.add_argument("--ep", type=int, metavar="N",
                        help="対象の回 (既定: 一番新しい回)")


# --------------------------------------------------------------------- 読み書き


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_script(ep: Episode) -> dict:
    if not ep.script.exists():
        raise EpisodeError(f"台本がありません: {ep.script}")
    return json.loads(ep.script.read_text(encoding="utf-8"))


def load_manifest(ep: Episode) -> dict:
    if not ep.manifest.exists():
        return {}
    return json.loads(ep.manifest.read_text(encoding="utf-8"))


def load_record(ep: Episode) -> dict:
    if not ep.record.exists():
        return {"episode": ep.number, "created": None, "published": None,
                "url": None, "items": []}
    return json.loads(ep.record.read_text(encoding="utf-8"))


def save_record(ep: Episode, record: dict) -> None:
    write_json(ep.record, record)


def used_ids() -> set[int]:
    """これまでの回で使った雑学のID。候補から外すために使う。"""
    ids: set[int] = set()
    for ep in episodes():
        for item in load_record(ep).get("items", []):
            if item.get("id") is not None:
                ids.add(int(item["id"]))
    return ids


# --------------------------------------------------------------------- 一覧


def describe(ep: Episode) -> str:
    record = load_record(ep)
    script = json.loads(ep.script.read_text(encoding="utf-8")) if ep.script.exists() else {}
    items = script.get("items") or []
    marked = [i for i in record.get("items", []) if i.get("id") is not None]

    state = []
    if len(marked) != len(items) or not items:
        # 記録漏れは静かに効いてくる(次回また同じ雑学が候補に出る)ので目立たせる
        state.append("記録 %d/%d" % (len(marked), len(items)))
    for label, path in (("動画", ep.video), ("サムネ", ep.thumbnail), ("概要", ep.publish)):
        if not path.exists():
            state.append(f"{label}なし")
    if record.get("published"):
        state.append("公開 " + record["published"])

    return "%-4s %-11s %-26s %s" % (ep, record.get("created") or "", ep.title(),
                                    " / ".join(state) if state else "そろっている")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--new", metavar="TITLE", help="次の番号で回を作る")
    args = parser.parse_args(argv)

    if args.new:
        ep = create(args.new)
        print(f"回 {ep} を作りました: {ep.dir}")
        print(f"  台本: {ep.script}")
        print(f"  記録: {ep.record}")
        return 0

    found = episodes()
    if not found:
        print('回がまだありません。python -m src.episode --new "タイトル" で作ってください')
        return 0
    print("%-4s %-11s %-26s %s" % ("回", "作成日", "タイトル", "状態"))
    print("-" * 78)
    for ep in found:
        print(describe(ep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

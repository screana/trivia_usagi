# -*- coding: utf-8 -*-
"""アプリのデータベースから雑学の候補を持ってくる。読み取りのみ。

    python -m src.trivia --list 20        # 未使用の上位20件を見る
    python -m src.trivia --show 112 16    # 指定IDの全文を見る
    python -m src.trivia --used           # 使用済みの一覧
    python -m src.trivia --mark 112 16 …  # 台本の順に並べて回の記録に書く

`hee_count` はアプリ内で「へぇ」ボタンが押された強さの合計(1人あたり1〜10)。
実際の反応が数字で残っているので、面白さの目安として素直に使える。

**採用は hee_count の高い順**。ただし古い雑学ほど票が積み上がっていて
(id と hee_count の相関 -0.65)、単純な降順だと古いものに偏る。
在庫が減って偏りが問題になったら、ID帯ごとの相対評価に切り替える。

接続情報は .env の TRIVIA_DATABASE_URL。読み取り専用ロールで繋ぐ前提で、
このモジュールは SELECT しか実行しない。使用済みの記録は DB ではなく
回のディレクトリの record.json に残す(episodes/001/record.json)。
"""
from __future__ import annotations

import argparse
import os
import sys

from . import config, episode


class TriviaError(Exception):
    pass


def database_url() -> str:
    url = os.environ.get("TRIVIA_DATABASE_URL")
    if url:
        return url
    env = config.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("TRIVIA_DATABASE_URL=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise TriviaError(
        "TRIVIA_DATABASE_URL が見つかりません。\n"
        f"  {env} に読み取り専用の接続文字列を1行で書いてください。"
    )


def connect():
    import psycopg

    try:
        return psycopg.connect(database_url(), connect_timeout=20)
    except psycopg.Error as exc:
        raise TriviaError(f"データベースに接続できません: {str(exc).strip().splitlines()[0]}")


# --------------------------------------------------------------------- 使用済み


def mark_used(ep, ids: list[int]) -> list[dict]:
    """使った雑学を回の記録に書く。IDは**台本の項目と同じ順**に並べること。

    hee_count は時間とともに増えるので、採用した時点の値をここで写し取る。
    あとから「なぜこれを選んだのか」を見るのに要る。
    """
    rows = {row["id"]: row for row in by_ids(ids)}
    missing = [i for i in ids if i not in rows]
    if missing:
        raise TriviaError("DBに無いID: %s" % ", ".join(str(i) for i in missing))

    record = episode.load_record(ep)
    record["items"] = [
        {"id": i, "hee": rows[i]["hee_count"], "category": rows[i]["category"],
         "title": rows[i]["title"]}
        for i in ids
    ]
    episode.save_record(ep, record)

    items = episode.load_script(ep).get("items") or []
    if len(items) != len(ids):
        print("注意: 台本は %d 項目、記録は %d 件です。順番と数を合わせてください"
              % (len(items), len(ids)), file=sys.stderr)
    return record["items"]


# --------------------------------------------------------------------- 取得


FIELDS = "id, hee_count, category, title, content, explanation, source"


def candidates(limit: int, exclude: set[int]) -> list[dict]:
    """未使用のものを hee_count の高い順に返す。"""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {FIELDS} FROM public.trivia
            WHERE NOT (id = ANY(%s))
            ORDER BY hee_count DESC NULLS LAST, id
            LIMIT %s
            """,
            (sorted(exclude) or [0], limit),
        )
        names = [d.name for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def by_ids(ids: list[int]) -> list[dict]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {FIELDS} FROM public.trivia WHERE id = ANY(%s) ORDER BY hee_count DESC",
                    (ids,))
        names = [d.name for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


# --------------------------------------------------------------------- 表示


def print_brief(rows: list[dict]) -> None:
    print("%-5s %-5s %-10s %s" % ("id", "hee", "分類", "タイトル"))
    print("-" * 82)
    for r in rows:
        print("%-5s %-5s %-10s %s"
              % (r["id"], r["hee_count"], (r["category"] or "")[:10], r["title"]))


def print_full(rows: list[dict]) -> None:
    for r in rows:
        print("\n--- id=%s  hee=%s  [%s] ---" % (r["id"], r["hee_count"], r["category"] or ""))
        print("  題  :", r["title"])
        print("  本文:", (r["content"] or "").replace("\n", " "))
        if r["explanation"]:
            print("  補足:", (r["explanation"] or "").replace("\n", " ")[:200])
        if r["source"]:
            print("  出典:", r["source"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", type=int, metavar="N", help="未使用の上位N件を見る")
    parser.add_argument("--full", action="store_true", help="--list で全文も出す")
    parser.add_argument("--show", type=int, nargs="+", metavar="ID", help="指定IDの全文を見る")
    parser.add_argument("--used", action="store_true", help="使用済みの一覧")
    parser.add_argument("--mark", type=int, nargs="+", metavar="ID",
                        help="回の記録に書く。台本の項目と同じ順に並べる")
    episode.add_argument(parser)
    args = parser.parse_args(argv)

    try:
        if args.used:
            eps = episode.episodes()
            if not eps:
                print("まだ何も使っていません")
                return 0
            for ep in eps:
                record = episode.load_record(ep)
                items = record.get("items", [])
                print("回 %s  %s  %s" % (ep, record.get("created") or "", ep.title()))
                for item in items:
                    print("    %-5s hee=%-5s %s" % (item["id"], item.get("hee", ""),
                                                    item.get("title", "")))
                if not items:
                    print("    (記録なし)")
            print("\n合計 %d 件" % len(episode.used_ids()))
            return 0

        if args.mark:
            ep = episode.resolve(args.ep)
            written = mark_used(ep, args.mark)
            print("回 %s の記録に %d 件書きました: %s" % (ep, len(written), ep.record))
            for i, item in enumerate(written, start=1):
                print("  %d. id=%-5s hee=%-5s %s" % (i, item["id"], item["hee"], item["title"]))
            return 0

        if args.show:
            print_full(by_ids(args.show))
            return 0

        if args.list:
            exclude = episode.used_ids()
            rows = candidates(args.list, exclude)
            print("未使用の上位 %d 件 (使用済み %d 件を除外)\n" % (len(rows), len(exclude)))
            print_full(rows) if args.full else print_brief(rows)
            return 0

        parser.print_help()
        return 1
    except (TriviaError, episode.EpisodeError) as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

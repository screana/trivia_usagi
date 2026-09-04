# -*- coding: utf-8 -*-
"""アプリのデータベースから雑学の候補を持ってくる。読み取りのみ。

    python -m src.trivia --list 20        # 未使用の上位20件を見る
    python -m src.trivia --show 112 16    # 指定IDの全文を見る
    python -m src.trivia --used           # 使用済みの一覧
    python -m src.trivia --mark 112 16 …  # 使用済みに記録する

`hee_count` はアプリ内で「へぇ」ボタンが押された強さの合計(1人あたり1〜10)。
実際の反応が数字で残っているので、面白さの目安として素直に使える。

**採用は hee_count の高い順**。ただし古い雑学ほど票が積み上がっていて
(id と hee_count の相関 -0.65)、単純な降順だと古いものに偏る。
在庫が減って偏りが問題になったら、ID帯ごとの相対評価に切り替える。

接続情報は .env の TRIVIA_DATABASE_URL。読み取り専用ロールで繋ぐ前提で、
このモジュールは SELECT しか実行しない。使用済みの記録は DB ではなく
リポジトリ側の used_trivia.json に残す。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from . import config


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


def load_used() -> dict:
    if config.USED_TRIVIA.exists():
        return json.loads(config.USED_TRIVIA.read_text(encoding="utf-8"))
    return {}


def used_ids() -> set[int]:
    return {int(i) for entry in load_used().values() for i in entry["ids"]}


def mark_used(ids: list[int], note: str) -> None:
    used = load_used()
    key = date.today().isoformat()
    # 同じ日に2本作ることもあるので、既にあれば連番を足す
    suffix = 1
    while key in used:
        suffix += 1
        key = f"{date.today().isoformat()}-{suffix}"
    used[key] = {"ids": sorted(ids), "note": note}
    config.USED_TRIVIA.write_text(
        json.dumps(used, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


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
    parser.add_argument("--mark", type=int, nargs="+", metavar="ID", help="使用済みに記録する")
    parser.add_argument("--note", default="", help="--mark に添えるメモ(動画名など)")
    args = parser.parse_args(argv)

    try:
        if args.used:
            used = load_used()
            if not used:
                print("まだ何も使っていません")
                return 0
            for key, entry in sorted(used.items()):
                print("%-14s %-30s %s" % (key, entry.get("note", ""),
                                          ", ".join(str(i) for i in entry["ids"])))
            print("\n合計 %d 件" % len(used_ids()))
            return 0

        if args.mark:
            mark_used(args.mark, args.note)
            print("使用済みに記録しました: %s" % ", ".join(str(i) for i in args.mark))
            print("  %s" % config.USED_TRIVIA)
            return 0

        if args.show:
            print_full(by_ids(args.show))
            return 0

        if args.list:
            exclude = used_ids()
            rows = candidates(args.list, exclude)
            print("未使用の上位 %d 件 (使用済み %d 件を除外)\n" % (len(rows), len(exclude)))
            print_full(rows) if args.full else print_brief(rows)
            return 0

        parser.print_help()
        return 1
    except TriviaError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

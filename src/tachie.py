# -*- coding: utf-8 -*-
"""立ち絵の PSD から表情差分を書き出す。

    python -m src.tachie --list                      # 選べるパーツを見る
    python -m src.tachie --make 目=にっこり 口=あは -o smile.png
    python -m src.tachie --preset smile              # config の定義から作る
    python -m src.tachie --all-presets

素材は PSDTool 向けに作られていて、レイヤー名に規則がある。

    `*` で始まる  … 同じグループの中で1つだけ表示する(ラジオボタン)
    `!` で始まる  … そのグループ自体は常に表示する

この規則にしたがって表示/非表示を切り替えてから合成する。

衣装は既定(巫女服)のまま触らない。顔まわりのパーツだけを対象にしている。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from psd_tools import PSDImage

from . import config

# 触ってよいグループ。衣装差分はここに入れていない
PART_GROUPS = ("顔色", "口", "目", "眉", "記号など", "右腕", "左腕")


class TachieError(Exception):
    pass


def _clean(name: str) -> str:
    """レイヤー名から PSDTool の記号を落とす。"""
    return name.lstrip("!*").split(":")[0]


def open_psd() -> PSDImage:
    if not config.TACHIE_PSD.exists():
        raise TachieError(
            f"PSD がありません: {config.TACHIE_PSD}\n"
            "配布 zip を展開して、このパスに置いてください。"
        )
    return PSDImage.open(config.TACHIE_PSD)


def find_groups(node, name: str) -> list:
    """名前の一致するグループをすべて集める(入れ子も探す)。

    腕は「衣装差分」と「巫女服」の下に同名で2つあるので、両方に同じ選択を
    当てて食い違わないようにする。
    """
    found = []
    for layer in node:
        if not layer.is_group():
            continue
        if _clean(layer.name) == name:
            found.append(layer)
        else:
            found.extend(find_groups(layer, name))
    return found


def parts(psd) -> dict[str, list[str]]:
    """グループごとに選べる名前を集める。"""
    found: dict[str, list[str]] = {}
    for name in PART_GROUPS:
        groups = find_groups(psd, name)
        if not groups:
            continue
        found[name] = [_clean(child.name) for child in groups[0]]
    return found


def apply(psd, selection: dict[str, str]) -> None:
    """選んだパーツだけを表示する。

    `*` 付きは1つだけ表示、記号などは複数同時に出せる(涙+汗など)。
    """
    available = parts(psd)
    for group_name, wanted in selection.items():
        if group_name not in available:
            raise TachieError(
                f"パーツ '{group_name}' はありません。使えるのは {', '.join(available)}"
            )
        chosen = {w.strip() for w in wanted.split("+") if w.strip()}
        unknown = chosen - set(available[group_name])
        if unknown:
            raise TachieError(
                f"{group_name} に {', '.join(unknown)} はありません。\n"
                f"  使えるのは: {', '.join(available[group_name])}"
            )
        # 腕は衣装違いの下に同名グループが複数あるので、全部に同じ選択を当てる
        for child in [c for group in find_groups(psd, group_name) for c in group]:
            name = _clean(child.name)
            if child.name.startswith("*") or group_name == "記号など":
                child.visible = name in chosen
            # `*` も `!` も付かないもの(前髪on目 など)は既定のまま触らない


def render(selection: dict[str, str]) -> "PSDImage":
    psd = open_psd()
    apply(psd, selection)
    # force=True にしないと、PSD に保存された合成済みプレビュー(RGB, アルファなし)
    # が返ることがある。レイヤーから組み直させて透過を保つ
    image = psd.composite(force=True)
    if image is None:
        raise TachieError("合成に失敗しました")
    return image.convert("RGBA")


def save(selection: dict[str, str], out_path: Path) -> Path:
    image = render(selection)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return out_path


def _parse(pairs: list[str]) -> dict[str, str]:
    selection: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise TachieError(f"'{pair}' は パーツ=名前 の形で指定してください")
        key, value = pair.split("=", 1)
        selection[key.strip()] = value.strip()
    return selection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="選べるパーツを一覧する")
    parser.add_argument("--make", nargs="+", metavar="パーツ=名前",
                        help="例: 目=にっこり 口=あは 記号など=汗+涙")
    parser.add_argument("--preset", help="config.EXPRESSIONS の名前で作る")
    parser.add_argument("--all-presets", action="store_true", help="定義済みの表情をすべて作る")
    parser.add_argument("-o", "--out", type=Path, help="出力先")
    args = parser.parse_args(argv)

    try:
        if args.list:
            for group, names in parts(open_psd()).items():
                print(f"{group} ({len(names)}種)")
                print("  " + " / ".join(names))
            print("\n記号などは + でつなげて複数指定できる (例: 記号など=汗+涙)")
            return 0

        if args.all_presets:
            for name, selection in config.EXPRESSIONS.items():
                out = config.TACHIE_DIR / f"{name}.png"
                save(selection, out)
                print(f"  {name} -> {out.name}")
            return 0

        if args.preset:
            if args.preset not in config.EXPRESSIONS:
                raise TachieError(
                    f"表情 '{args.preset}' は未定義です。"
                    f"使えるのは {', '.join(config.EXPRESSIONS)}"
                )
            out = args.out or (config.TACHIE_DIR / f"{args.preset}.png")
            print("書き出し:", save(config.EXPRESSIONS[args.preset], out))
            return 0

        if args.make:
            if not args.out:
                raise TachieError("-o で出力先を指定してください")
            print("書き出し:", save(_parse(args.make), args.out))
            return 0

        parser.print_help()
        return 1
    except TachieError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

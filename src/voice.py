# -*- coding: utf-8 -*-
"""VOICEVOX で読み上げ音声を作る。

    python -m src.voice            # 台本の全テキストを音声にする
    python -m src.voice --check    # 読みをカタカナで確認する(音声は作らない)
    python -m src.voice --force    # 変わっていなくても作り直す

振りとオチは別ファイルにする(`out/audio/01_setup.wav`)。
それぞれの再生時間をそのまま表示タイミングに使うため。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path

from . import config


class VoiceError(Exception):
    pass


# --------------------------------------------------------------------- ENGINE


def _get(path: str, timeout: float = 10.0):
    url = config.VOICEVOX_HOST.rstrip("/") + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise VoiceError(
            f"VOICEVOX ENGINE に接続できません ({config.VOICEVOX_HOST})。\n"
            f"VOICEVOX アプリを起動してから、もう一度実行してください。\n  詳細: {exc}"
        ) from exc


def _post(path: str, params: dict, body: dict | None = None, timeout: float = 60.0):
    url = config.VOICEVOX_HOST.rstrip("/") + path + "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise VoiceError(f"{path} に失敗しました: {exc}") from exc
    except urllib.error.URLError as exc:
        raise VoiceError(f"VOICEVOX ENGINE に接続できません: {exc}") from exc


def engine_version() -> str:
    return _get("/version", timeout=5)


def resolve_style_id(speaker_name: str, style_name: str) -> int:
    """話者名とスタイル名から style_id を引く。

    ID をハードコードしない。ENGINE のバージョンで変わりうるため。
    """
    for speaker in _get("/speakers", timeout=20):
        if speaker["name"] != speaker_name:
            continue
        for style in speaker["styles"]:
            if style["name"] == style_name:
                return int(style["id"])
        available = ", ".join(s["name"] for s in speaker["styles"])
        raise VoiceError(f"{speaker_name} に '{style_name}' はありません。使えるのは {available}")
    raise VoiceError(f"話者 '{speaker_name}' が見つかりません")


def audio_query(text: str, style_id: int) -> dict:
    payload = _post("/audio_query", {"text": text, "speaker": style_id})
    query = json.loads(payload.decode("utf-8"))
    query["speedScale"] = config.SPEED_SCALE
    return query


def reading(query: dict) -> str:
    """audio_query の結果から、読み上げられるカタカナを組み立てる。

    /audio_query は /accent_phrases と同じ accent_phrases を返すうえ、
    合成に渡すクエリそのものなので、ここで見た読みは必ず音声と一致する。
    """
    parts: list[str] = []
    for phrase in query.get("accent_phrases", []):
        parts.append("".join(mora["text"] for mora in phrase["moras"]))
        if phrase.get("pause_mora"):
            parts.append("、")
    return "".join(parts)


def synthesize(query: dict, style_id: int) -> bytes:
    return _post("/synthesis", {"speaker": style_id}, query)


# --------------------------------------------------------------------- 台帳


@dataclass
class Ledger:
    """どの条件で作った音声かを記録し、変わっていなければ作り直さない。"""

    path: Path
    data: dict

    @classmethod
    def load(cls) -> "Ledger":
        path = config.AUDIO_DIR / "ledger.json"
        if path.exists():
            return cls(path, json.loads(path.read_text(encoding="utf-8")))
        return cls(path, {})

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    @staticmethod
    def digest(text: str, style_id: int, version: str) -> str:
        blob = json.dumps(
            {"text": text, "style": style_id, "speed": config.SPEED_SCALE, "engine": version},
            ensure_ascii=False, sort_keys=True,
        )
        return sha1(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------- 本体


def clips(script: dict) -> list[tuple[str, str]]:
    """(ファイル名の元, 読み上げるテキスト) を台本の順に返す。"""
    out: list[tuple[str, str]] = []
    for i, item in enumerate(script["items"], start=1):
        # 表示用の改行は読み上げに含めない
        out.append((f"{i:02d}_setup", item["setup"].replace("\n", "")))
        out.append((f"{i:02d}_punch", item["punch"].replace("\n", "")))
    return out


def load_script() -> dict:
    if not config.SCRIPT_JSON.exists():
        raise VoiceError(f"台本がありません: {config.SCRIPT_JSON}")
    return json.loads(config.SCRIPT_JSON.read_text(encoding="utf-8"))


def check(script: dict, style_id: int) -> int:
    """読みをカタカナで並べる。固有名詞や数字の読み違いをここで見つける。"""
    print(f"{config.SPEAKER_NAME} / {config.SPEAKER_STYLE} (style_id={style_id})")
    print(f"話速 {config.SPEED_SCALE}\n")
    print("%-14s %-26s %s" % ("", "原文", "読み"))
    print("-" * 88)
    for name, text in clips(script):
        print("%-14s %-26s %s" % (name, text, reading(audio_query(text, style_id))))
    print("\n読み違いがあれば、まず台本の表記を変える(「15センチ」→「十五センチ」など)。")
    return 0


def generate(script: dict, style_id: int, force: bool) -> int:
    version = engine_version()
    ledger = Ledger.load()
    config.AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    created = reused = 0
    for name, text in clips(script):
        target = config.AUDIO_DIR / f"{name}.wav"
        digest = Ledger.digest(text, style_id, version)
        if not force and target.exists() and ledger.data.get(name) == digest:
            reused += 1
            continue
        query = audio_query(text, style_id)
        target.write_bytes(synthesize(query, style_id))
        ledger.data[name] = digest
        created += 1
        print(f"  生成 {name}: {text}")

    ledger.save()
    print(f"音声: {created} 件生成 / {reused} 件は変更なしのため再利用")
    print(f"  {config.AUDIO_DIR}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="読みをカタカナで確認する")
    parser.add_argument("--force", action="store_true", help="変わっていなくても作り直す")
    args = parser.parse_args(argv)

    try:
        script = load_script()
        style_id = resolve_style_id(config.SPEAKER_NAME, config.SPEAKER_STYLE)
        if args.check:
            return check(script, style_id)
        return generate(script, style_id, args.force)
    except VoiceError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

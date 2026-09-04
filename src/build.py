# -*- coding: utf-8 -*-
"""動画を組み立てる。

    python -m src.build --item 3     # 3項目目だけ
    python -m src.build --item 2-4   # 範囲。項目間の間を見るとき用
    python -m src.build            # 通し
    python -m src.build --no-endcard

1項目の流れは 振りとイラストを同時に表示・読み上げ → 溜め → オチ表示・読み上げ。
オチが出るのと同時に、うさぎの顔も反応する表情に変わる。
画面は layout.py が透過1枚として作り、背景動画の上に合成するだけにしている
(プレビューと本番で絵がズレないようにするため)。

音声は narration + BGM + エンドカードの音を numpy で1本の wav にまとめてから
渡す。moviepy 側で音を重ねるより、どこに何が鳴るかが読みやすい。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from . import config, layout

SAMPLE_RATE = 24000          # VOICEVOX の出力に合わせる


class BuildError(Exception):
    pass


# --------------------------------------------------------------------- 構成


@dataclass
class Scene:
    """背景クリップ1本ぶん。1項目=1シーンで、その中で画面だけが切り替わる。

    画面ごとに背景を取り直すと毎回頭出しに戻り、止まったり動いたりして見える。
    シーン単位で同じクリップの続きを切り出すことで、項目のあいだ通して流れる。
    """

    background: Path | None
    states: list[tuple[Image.Image, float]]   # (重ねる画像, 表示時間)

    @property
    def duration(self) -> float:
        return sum(duration for _, duration in self.states)


@dataclass
class Cue:
    """音声を鳴らす位置。"""

    path: Path
    start: float


def wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def load_script() -> dict:
    if not config.SCRIPT_JSON.exists():
        raise BuildError(f"台本がありません: {config.SCRIPT_JSON}")
    return json.loads(config.SCRIPT_JSON.read_text(encoding="utf-8"))


def load_manifest() -> dict:
    if not config.MANIFEST.exists():
        return {}
    return json.loads(config.MANIFEST.read_text(encoding="utf-8"))


def illustration_for(index: int, manifest: dict):
    entry = manifest.get(str(index))
    if not entry:
        return None, None
    path = config.IMAGES_DIR / entry["file"]
    if not path.exists():
        raise BuildError(f"画像がありません: {path}")
    return Image.open(path).convert("RGBA"), entry.get("attribution")


def parse_range(spec: str | None) -> tuple[int, int] | None:
    """--item の指定を (最初, 最後) にする。"3" でも "2-4" でも受ける。"""
    if not spec:
        return None
    if "-" in spec:
        first, last = (int(v) for v in spec.split("-", 1))
    else:
        first = last = int(spec)
    return first, last


def plan(script: dict, only: tuple[int, int] | None) -> tuple[list[Scene], list[Cue]]:
    """絵の並びと音の位置を決める。ここだけ読めば構成がわかるようにしてある。"""
    manifest = load_manifest()
    scenes: list[Scene] = []
    cues: list[Cue] = []
    clock = 0.0

    items = list(enumerate(script["items"], start=1))
    if only is not None:
        first, last = only
        items = [(i, item) for i, item in items if first <= i <= last]
        if not items:
            raise BuildError(f"--item {first}-{last} に該当する項目がありません")

    # タイトルと各項目に背景を割り当てる。項目ごとに別のクリップになる
    backgrounds = layout.background_order(len(items) + (0 if only else 1))
    if only is None:
        scenes.append(Scene(backgrounds[0],
                            [(layout.render_title(script["title"], overlay=True,
                                                  expression=config.MASCOT_EXPRESSION),
                              config.TITLE_DURATION)]))
        clock += config.TITLE_DURATION
        backgrounds = backgrounds[1:]

    for (i, item), background in zip(items, backgrounds):
        illustration, attribution = illustration_for(i - 1, manifest)
        setup_wav = config.AUDIO_DIR / f"{i:02d}_setup.wav"
        punch_wav = config.AUDIO_DIR / f"{i:02d}_punch.wav"
        for path in (setup_wav, punch_wav):
            if not path.exists():
                raise BuildError(f"音声がありません: {path}\n  python -m src.voice で作ってください")

        setup_len, punch_len = wav_duration(setup_wav), wav_duration(punch_wav)
        tail = punch_len + (config.ITEM_GAP if i != items[-1][0] else config.TAIL)

        cues.append(Cue(setup_wav, clock))
        cues.append(Cue(punch_wav, clock + setup_len + config.REVEAL_GAP))

        # 振りとイラストは同時に出し、溜めを置いてからオチを足す。
        # オチと同時にうさぎの顔も変える。背景は2枚を通して繋がっている
        scenes.append(Scene(background, [
            (layout.render_item(item["setup"], None, illustration, attribution, overlay=True,
                                expression=config.MASCOT_EXPRESSION),
             setup_len + config.REVEAL_GAP),
            (layout.render_item(item["setup"], item["punch"], illustration, attribution,
                                overlay=True, expression=config.MASCOT_EXPRESSION_PUNCH), tail),
        ]))
        clock += setup_len + config.REVEAL_GAP + tail

    return scenes, cues


# --------------------------------------------------------------------- 音声


def decode(path: Path) -> np.ndarray:
    """任意の音声をモノラル float32 に展開する。mp3 も mp4 の音声も読める。"""
    import imageio_ffmpeg

    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le",
        "-ac", "1", "-ar", str(SAMPLE_RATE), "-",
    ]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        raise BuildError(f"音声を読めませんでした: {path}")
    return np.frombuffer(result.stdout, dtype=np.float32)


def build_audio(cues: list[Cue], total: float, endcard_at: float | None,
                out_path: Path) -> Path:
    length = int(round(total * SAMPLE_RATE))
    track = np.zeros(length, dtype=np.float32)

    for cue in cues:
        samples = decode(cue.path)
        start = int(round(cue.start * SAMPLE_RATE))
        end = min(start + len(samples), length)
        if end > start:
            track[start:end] += samples[: end - start]

    if endcard_at is not None and config.ENDCARD.exists():
        samples = decode(config.ENDCARD)
        start = int(round(endcard_at * SAMPLE_RATE))
        end = min(start + len(samples), length)
        if end > start:
            track[start:end] += samples[: end - start]

        # エンドカードの一言。読み終わりが終端に来るように置くので、
        # ロゴと文字が出るタイミングに「更新中」が重なる
        line = config.AUDIO_DIR / "endcard.wav"
        if config.ENDCARD_VOICE and line.exists():
            voice = decode(line)
            at = total - len(voice) / SAMPLE_RATE - config.ENDCARD_VOICE_TAIL
            start = max(int(round(at * SAMPLE_RATE)), int(round(endcard_at * SAMPLE_RATE)))
            end = min(start + len(voice), length)
            if end > start:
                track[start:end] += voice[: end - start]

    if config.BGM.exists():
        track += _bgm(cues, length, total, endcard_at)

    peak = float(np.abs(track).max())
    if peak > 1.0:
        track /= peak

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((track * 32767.0).astype(np.int16).tobytes())
    return out_path


def _bgm(cues: list[Cue], length: int, total: float,
         endcard_at: float | None = None) -> np.ndarray:
    """BGM を尺に合わせ、読み上げ中だけ音量を下げる。

    エンドカードには自前の音が入っているので、その手前で BGM を切る。
    重ねると両方の音楽がぶつかって濁る。
    """
    samples = decode(config.BGM)
    if len(samples) == 0:
        return np.zeros(length, dtype=np.float32)
    if len(samples) < length:
        samples = np.tile(samples, int(np.ceil(length / len(samples))))
    samples = samples[:length].astype(np.float32).copy() * config.BGM_VOLUME

    # 読み上げの区間だけ下げる。カーブは10ms刻みで作って補間する
    step = 0.01
    blocks = max(1, int(np.ceil(total / step)))
    target = np.ones(blocks, dtype=np.float32)
    for cue in cues:
        i0 = max(0, int(cue.start / step))
        i1 = min(blocks, int(np.ceil((cue.start + wav_duration(cue.path)) / step)))
        target[i0:i1] = config.BGM_DUCK

    smoothed = np.empty_like(target)
    value = float(target[0])
    down, up = np.exp(-step / 0.15), np.exp(-step / 0.5)
    for i, goal in enumerate(target):
        value = goal + (value - goal) * (down if goal < value else up)
        smoothed[i] = value

    positions = np.arange(length, dtype=np.float32) / SAMPLE_RATE / step
    samples *= np.interp(positions, np.arange(blocks, dtype=np.float32),
                         smoothed).astype(np.float32)

    # 頭は静かに入れる
    head = min(int(config.BGM_FADE_IN * SAMPLE_RATE), length)
    if head > 0:
        samples[:head] *= np.linspace(0.0, 1.0, head, dtype=np.float32)

    # エンドカードの手前で終わらせる。無ければ末尾でフェードアウトする
    stop = endcard_at if endcard_at is not None else total
    fade = int(config.BGM_FADE_OUT * SAMPLE_RATE)
    end = min(int(round(stop * SAMPLE_RATE)), length)
    start = max(0, end - fade)
    if end > start:
        samples[start:end] *= np.linspace(1.0, 0.0, end - start, dtype=np.float32)
    samples[end:] = 0.0
    return samples


# --------------------------------------------------------------------- 映像


def _vertical(clip):
    """16:9 の素材を 9:16 に。先に切り出してから拡大する(計算量を減らすため)。"""
    target = clip.h * config.WIDTH / config.HEIGHT
    if clip.w > target:
        clip = clip.cropped(x_center=clip.w / 2, width=round(target))
    return clip.resized((config.WIDTH, config.HEIGHT))


def vertical_cache(path: Path) -> Path:
    """背景素材を 9:16 に変換したものを作り置きする。

    元素材は 1920x1080 の 49Mbps なので、毎フレーム切り出して拡大すると
    書き出しが桁違いに遅くなる。一度だけ ffmpeg で変換して使い回す。
    """
    import imageio_ffmpeg

    config.BG_CACHE.mkdir(parents=True, exist_ok=True)
    cached = config.BG_CACHE / (path.stem + ".mp4")
    if cached.exists() and cached.stat().st_mtime >= path.stat().st_mtime:
        return cached

    print(f"  背景を縦型に変換: {path.name}")
    # 切り出す幅は ffmpeg 側で入力の高さから求めさせる (素材の解像度に依存しない)。
    # 幅を偶数に丸めてから 1080x1920 に拡大する。
    crop = f"crop=trunc(ih*{config.WIDTH}/{config.HEIGHT}/2)*2:ih"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(path),
        "-vf", f"{crop},scale={config.WIDTH}:{config.HEIGHT}",
        "-an", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
        str(cached),
    ]
    if subprocess.run(command).returncode != 0:
        raise BuildError(f"背景の変換に失敗しました: {path}")
    return cached


def _background_clip(path: Path | None, duration: float):
    from moviepy import ColorClip, VideoFileClip

    if path is None:
        return ColorClip((config.WIDTH, config.HEIGHT), color=(239, 239, 239), duration=duration)

    source = VideoFileClip(str(vertical_cache(path))).without_audio()
    if source.duration >= duration:
        return source.subclipped(0, duration)
    # 素材が短ければ繰り返す
    from moviepy import concatenate_videoclips

    times = int(np.ceil(duration / source.duration))
    return concatenate_videoclips([source] * times).subclipped(0, duration)


def _blend(background, overlay: Image.Image):
    """背景の上に透過1枚を重ねる。

    moviepy の CompositeVideoClip でも同じ絵になるが、マスク処理が重く
    1フレーム 190ms かかっていた。整数のアルファ合成を直に書くと 80ms 台に
    なるので、ここだけ自前にしている(出力は moviepy と丸め誤差1以内で一致)。
    """
    from moviepy import VideoClip

    array = np.asarray(overlay)
    rgb = array[..., :3].astype(np.uint16)
    alpha = array[..., 3:4].astype(np.uint16)
    inverse = np.uint16(255) - alpha

    def make_frame(t):
        frame = background.get_frame(t).astype(np.uint16)
        return ((frame * inverse + rgb * alpha) // 255).astype(np.uint8)

    return VideoClip(make_frame, duration=background.duration)


def render(scenes: list[Scene], audio_path: Path, out_path: Path, fps: int,
           endcard: bool) -> None:
    from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips

    segments = []
    # 元クリップの参照を書き出しが終わるまで保持する。手放すと GC されたときに
    # 裏の ffmpeg プロセスが閉じられ、切り出したほうを読む段で
    # 「ハンドルが無効です」で落ちる
    sources = []
    for scene in scenes:
        # 背景はシーンにつき1本。画面が切り替わっても頭出しに戻らないよう、
        # 同じクリップの続きを切り出していく
        source = _background_clip(scene.background, scene.duration)
        sources.append(source)
        offset = 0.0
        for overlay, duration in scene.states:
            part = source.subclipped(offset, offset + duration)
            segments.append(_blend(part, overlay).with_duration(duration))
            offset += duration

    if endcard and config.ENDCARD.exists():
        segments.append(_vertical(VideoFileClip(str(config.ENDCARD)).without_audio()))

    video = concatenate_videoclips(segments)
    track = AudioFileClip(str(audio_path))
    if track.duration > video.duration + 1e-3:
        track = track.subclipped(0, video.duration)
    video = video.with_audio(track).with_fps(fps)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(str(out_path), fps=fps, codec="libx264", audio_codec="aac",
                          preset="medium", threads=4, logger="bar")
    video.close()
    track.close()
    for source in sources:
        source.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--item", help="この項目だけ書き出す。範囲も可 (例: 3 / 2-4)")
    parser.add_argument("--no-endcard", action="store_true", help="エンドカードを付けない")
    parser.add_argument("--fps", type=int, default=config.FPS)
    parser.add_argument("-o", "--out", type=Path)
    args = parser.parse_args(argv)

    try:
        script = load_script()
        selection = parse_range(args.item)
        scenes, cues = plan(script, selection)
    except BuildError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1

    body = sum(scene.duration for scene in scenes)
    endcard = not args.no_endcard and selection is None and config.ENDCARD.exists()
    endcard_len = 0.0
    if endcard:
        from moviepy import VideoFileClip

        with VideoFileClip(str(config.ENDCARD)) as clip:
            endcard_len = clip.duration

    total = body + endcard_len
    print("シーン %d / 本編 %.2fs%s = 合計 %.2fs"
          % (len(scenes), body,
             (" + エンドカード %.2fs" % endcard_len) if endcard else "", total))
    # どの素材を使ったかを出す。差し替えたのに反映されていない、を防ぐため
    print("  BGM         : %s" % (config.BGM.name if config.BGM.exists() else "なし"))
    print("  エンドカード: %s" % (f"{config.ENDCARD.name} ({endcard_len:.2f}s)"
                                  if endcard else "なし"))

    audio_path = build_audio(cues, total, body if endcard else None,
                             config.MIX_WAV)
    suffix = f"_item{args.item}" if args.item else ""
    out = args.out or (config.OUT_DIR / f"video{suffix}.mp4")

    started = time.time()
    render(scenes, audio_path, out, args.fps, endcard)
    print(f"\n書き出し完了: {out}")
    print("  %.1fs の動画を %.0fs で書き出しました" % (total, time.time() - started))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

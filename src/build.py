# -*- coding: utf-8 -*-
"""動画を組み立てる。

    python -m src.build --item 3   # 3項目目だけ。間の取り方を詰めるとき用
    python -m src.build            # 通し
    python -m src.build --no-endcard

1項目の流れは 振り表示・読み上げ → イラスト表示 → オチ表示・読み上げ。
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
class Shot:
    """画面1枚ぶん。背景クリップの上に overlay を出す。"""

    overlay: Image.Image
    duration: float
    background: Path | None


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


def plan(script: dict, only: int | None) -> tuple[list[Shot], list[Cue]]:
    """絵の並びと音の位置を決める。ここだけ読めば構成がわかるようにしてある。"""
    manifest = load_manifest()
    shots: list[Shot] = []
    cues: list[Cue] = []
    clock = 0.0

    items = list(enumerate(script["items"], start=1))
    if only is not None:
        items = [(i, item) for i, item in items if i == only]
        if not items:
            raise BuildError(f"--item {only} は台本にありません")
    else:
        shots.append(Shot(layout.render_title(script["title"], overlay=True),
                          config.TITLE_DURATION, layout.background_path(0)))
        clock += config.TITLE_DURATION

    for i, item in items:
        background = layout.background_path(i - 1)
        illustration, attribution = illustration_for(i - 1, manifest)
        setup_wav = config.AUDIO_DIR / f"{i:02d}_setup.wav"
        punch_wav = config.AUDIO_DIR / f"{i:02d}_punch.wav"
        for path in (setup_wav, punch_wav):
            if not path.exists():
                raise BuildError(f"音声がありません: {path}\n  python -m src.voice で作ってください")

        setup_len, punch_len = wav_duration(setup_wav), wav_duration(punch_wav)

        # 振りだけ / イラストを足す / オチを足す の3枚
        cues.append(Cue(setup_wav, clock))
        shots.append(Shot(
            layout.render_item(item["setup"], None, None, None, overlay=True),
            setup_len, background))
        clock += setup_len

        shots.append(Shot(
            layout.render_item(item["setup"], None, illustration, attribution, overlay=True),
            config.REVEAL_GAP, background))
        clock += config.REVEAL_GAP

        cues.append(Cue(punch_wav, clock))
        tail = punch_len + (config.ITEM_GAP if i != items[-1][0] else config.TAIL)
        shots.append(Shot(
            layout.render_item(item["setup"], item["punch"], illustration, attribution,
                               overlay=True),
            tail, background))
        clock += tail

    return shots, cues


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

    if config.BGM.exists():
        track += _bgm(cues, length, total)

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


def _bgm(cues: list[Cue], length: int, total: float) -> np.ndarray:
    """BGM を尺に合わせ、読み上げ中だけ音量を下げる。"""
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
    return samples * np.interp(positions, np.arange(blocks, dtype=np.float32),
                               smoothed).astype(np.float32)


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


def render(shots: list[Shot], audio_path: Path, out_path: Path, fps: int,
           endcard: bool) -> None:
    from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips

    segments = []
    for shot in shots:
        background = _background_clip(shot.background, shot.duration)
        segments.append(_blend(background, shot.overlay).with_duration(shot.duration))

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--item", type=int, help="この項目だけ書き出す (1始まり)")
    parser.add_argument("--no-endcard", action="store_true", help="エンドカードを付けない")
    parser.add_argument("--fps", type=int, default=config.FPS)
    parser.add_argument("-o", "--out", type=Path)
    args = parser.parse_args(argv)

    try:
        script = load_script()
        shots, cues = plan(script, args.item)
    except BuildError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1

    body = sum(shot.duration for shot in shots)
    endcard = not args.no_endcard and args.item is None and config.ENDCARD.exists()
    endcard_len = 0.0
    if endcard:
        from moviepy import VideoFileClip

        with VideoFileClip(str(config.ENDCARD)) as clip:
            endcard_len = clip.duration

    total = body + endcard_len
    print("画面 %d 枚 / 本編 %.2fs%s = 合計 %.2fs"
          % (len(shots), body,
             (" + エンドカード %.2fs" % endcard_len) if endcard else "", total))

    audio_path = build_audio(cues, total, body if endcard else None,
                             config.OUT_DIR / "audio" / "_mix.wav")
    suffix = f"_item{args.item:02d}" if args.item else ""
    out = args.out or (config.OUT_DIR / f"video{suffix}.mp4")

    started = time.time()
    render(shots, audio_path, out, args.fps, endcard)
    print(f"\n書き出し完了: {out}")
    print("  %.1fs の動画を %.0fs で書き出しました" % (total, time.time() - started))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

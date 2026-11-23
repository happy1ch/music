import argparse
import sys
from pathlib import Path

from acapella import (
    mix_parts,
    read_score,
    render_part,
    separate_satb,
    write_wav,
)
from acapella.voice_synth import VOICE_PROFILES


def process(input_path: str, output_dir: str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    score = read_score(input_path)
    parts = separate_satb(score)

    rendered = {}
    events_report = []
    for voice_name, part in parts.items():
        audio, events = render_part(part, voice_name, score)
        if len(audio) == 0:
            sys.stderr.write(f"[warn] {voice_name}: 음표가 없어 스킵\n")
            continue
        rendered[voice_name] = audio
        part_wav = out / f"{voice_name}.wav"
        write_wav(str(part_wav), audio)
        sys.stderr.write(
            f"[voice] {VOICE_PROFILES[voice_name]['label']}: {len(events)}음표, "
            f"{len(audio) / 44100:.1f}초 -> {part_wav.name}\n"
        )
        events_report.append({"voice": voice_name, "notes": events})

    mix = mix_parts(rendered)
    mix_path = out / "acapella_mix.wav"
    write_wav(str(mix_path), mix)
    sys.stderr.write(f"[mix] 4부 아카펠라 믹싱 완료: {mix_path} ({len(mix) / 44100:.1f}초)\n")
    return mix_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="악보 PDF/MusicXML을 읽어 SATB 4부로 분리하고 남성 아카펠라 음원을 생성합니다."
    )
    parser.add_argument("input", help="악보 파일 (PDF, .musicxml, .mxl, .krn, .abc, .mid)")
    parser.add_argument("-o", "--output", default="output", help="출력 디렉터리 (기본: output)")
    args = parser.parse_args()

    try:
        mix_path = process(args.input, args.output)
    except Exception as exc:
        sys.stderr.write(f"[error] {exc}\n")
        return 1
    print(f"완료: {mix_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

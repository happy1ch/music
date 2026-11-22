import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from music21 import converter, stream

MUSICXML_SUFFIXES = {".mxl", ".xml", ".musicxml", ".krn", ".abc", ".mid", ".midi"}


def _run_audiveris(pdf_path: Path, out_dir: Path) -> Path:
    executable = shutil.which("Audiveris") or shutil.which("audiveris")
    if executable is None:
        raise RuntimeError(
            "PDF 악보 인식(OMR)에는 Audiveris가 필요합니다. "
            "https://github.com/Audiveris/audiveris 에서 설치한 뒤 PATH에 등록하거나, "
            "악보를 MusicXML(.musicxml/.mxl)로 저장해 함께 넣어 주세요."
        )
    cmd = [executable, "-batch", "-export", "-output", str(out_dir), str(pdf_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audiveris 실행 실패:\n{result.stdout}\n{result.stderr}")
    candidates = sorted(out_dir.rglob("*.mxl")) + sorted(out_dir.rglob("*.musicxml"))
    if not candidates:
        raise RuntimeError("Audiveris가 MusicXML을 생성하지 않았습니다. 악보 스캔 품질을 확인하세요.")
    return candidates[0]


def _voices_to_parts(score):
    for part in score.parts:
        if len(part.getElementsByClass(stream.Voice)) > 0:
            extractor = stream.VoicesToParts()
            return extractor.processScore(score)
    return score


def read_score(path: str | Path) -> stream.Score:
    score_path = Path(path)
    if not score_path.exists():
        raise FileNotFoundError(f"악보 파일을 찾을 수 없습니다: {score_path}")

    suffix = score_path.suffix.lower()
    if suffix == ".pdf":
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            musicxml_path = _run_audiveris(score_path, out_dir)
            score = converter.parse(str(musicxml_path))
    elif suffix in MUSICXML_SUFFIXES:
        score = converter.parse(str(score_path))
    else:
        raise ValueError(
            f"지원하지 않는 형식입니다: {suffix}. "
            f"PDF 또는 MusicXML을 사용하세요. (지원됨: pdf, mxl, musicxml, xml, krn, abc, mid)"
        )
    sys.stderr.write(f"[score] 파트 {len(score.parts)}개 로드 완료: {score_path.name}\n")
    return _voices_to_parts(score)

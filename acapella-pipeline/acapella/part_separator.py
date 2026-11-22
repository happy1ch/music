import sys

from music21 import instrument, stream

SATB_ORDER = ("soprano", "alto", "tenor", "bass")
KOREAN_NAMES = {
    "소프라노": "soprano",
    "소프라노1": "soprano",
    "소프라노2": "alto",
    "알토": "alto",
    "테너": "tenor",
    "베이스": "bass",
    "남성": "tenor",
    "여성": "soprano",
}
NAME_KEYWORDS = {
    "soprano": ("sopr", "sop.", "cantus", "canto", "child"),
    "alto": ("alto", "contralto", "alt."),
    "tenor": ("tenor", "ten."),
    "bass": ("bass", "basso", "barit", "b.c", "continuo"),
}
PITCH_ORDER = ["soprano", "alto", "tenor", "bass"]


def _guess_by_name(part: stream.Part) -> str | None:
    labels = [part.partName, part.partAbbreviation, part.id]
    for element in part.getElementsByClass(instrument.Instrument):
        labels.append(element.instrumentName)
        labels.append(element.partName)
    for label in labels:
        if not label:
            continue
        text = str(label).strip().lower()
        if text in KOREAN_NAMES:
            return KOREAN_NAMES[text]
        non_space = text.replace(" ", "")
        if non_space in KOREAN_NAMES:
            return KOREAN_NAMES[non_space]
        for voice_name, keywords in NAME_KEYWORDS.items():
            if any(keyword in non_space for keyword in keywords):
                return voice_name
    return None


def _has_voices(part: stream.Part) -> bool:
    return len(part.getElementsByClass(stream.Voice)) > 0


def separate_satb(score: stream.Score) -> dict[str, stream.Part]:
    parts = [p for p in score.parts if len(p.recurse().notes) > 0]
    if not parts:
        raise ValueError("음표가 있는 파트가 없습니다.")

    assigned: dict[str, stream.Part] = {}
    unmatched: list[stream.Part] = []
    for part in parts:
        name = _guess_by_name(part)
        if name and name not in assigned:
            assigned[name] = part
        else:
            unmatched.append(part)

    if len(assigned) < 4 and unmatched:
        remaining = [v for v in SATB_ORDER if v not in assigned]
        if len(unmatched) == len(remaining):
            def average_pitch(part):
                pitches = [n.pitch.ps for n in part.recurse().notes if n.isNote]
                return sum(pitches) / len(pitches) if pitches else 0.0

            by_avg = sorted(unmatched, key=average_pitch, reverse=True)
            for voice_name, part in zip(remaining, by_avg):
                assigned[voice_name] = part

    missing = [v for v in SATB_ORDER if v not in assigned]
    if missing:
        sys.stderr.write(f"[warn] 파트를 찾지 못함: {missing}\n")

    sys.stderr.write(
        "[parts] " + ", ".join(f"{k}: {v.partName or v.id}" for k, v in assigned.items()) + "\n"
    )
    return assigned

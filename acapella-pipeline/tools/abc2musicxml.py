import re
import sys
from pathlib import Path

from music21 import clef, key, meter, note, stream, tempo

PITCH_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
ACCIDENTAL = {"_": -1, "^": 1, "=": 0}
SHARP_ORDER = "FCGDAEB"
FLAT_ORDER = "BEADGCF"
KEY_PARSERS = re.compile(r"^([A-G])(#|b)?")

VOICE_TO_PART = {
    "S1V1": ("Soprano", clef.TrebleClef()),
    "S1V2": ("Alto", clef.TrebleClef()),
    "S2V1": ("Tenor", clef.Treble8vbClef()),
    "S2V2": ("Bass", clef.BassClef()),
}

VOICE_TAG = re.compile(r"\[?V:\s*([A-Za-z0-9]+)\s*[,\]]?")
NOTE_TOKEN = re.compile(r"([_^=]?)([A-Ga-g])([,']+)?(\d+(?:/\d+)?|/\d*)?(-)?")


def _key_signature(key_name: str) -> tuple[str, list[str]]:
    match = KEY_PARSERS.match(key_name.strip())
    if not match:
        return "major", []
    letter, accidental = match.group(1), match.group(2) or ""
    if accidental == "b":
        n = {"B": 1, "E": 2, "A": 3, "D": 4, "G": 5, "C": 6, "F": 7}.get(letter, 0)
        return "flat", list(FLAT_ORDER[:n])
    n = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F": 6}.get(letter, 0)
    if accidental == "#":
        n = {"C": 7, "G": 3, "D": 4, "A": 5, "E": 6, "B": 7, "F": 6}.get(letter, n)
    return "sharp", list(SHARP_ORDER[:n])


def _tokenize(music: str) -> list[str]:
    tokens = []
    current = ""
    for char in music:
        if char in '()|! ";;':
            if current:
                tokens.append(current)
            current = ""
            continue
        if char in "abcdefgABCDEFG":
            if current:
                tokens.append(current)
            current = char
        else:
            current += char
    if current:
        tokens.append(current)
    return tokens


def _duration_of(suffix: str | None, base_len: float) -> float:
    if not suffix:
        return base_len
    if suffix.startswith("/"):
        denom = int(suffix[1:] or 2)
        return base_len / denom
    if "/" in suffix:
        num, denom = suffix.split("/")
        return base_len * int(num) / int(denom)
    return base_len * int(suffix)


def _parse_notes(tokens: list[str], base_len: float, altered_letters: list[str], sharp: bool) -> list[dict]:
    notes = []
    for token in tokens:
        match = NOTE_TOKEN.match(token.replace("(3", "").replace("(6", ""))
        if not match:
            continue
        accidental, letter, octave_marks, suffix, tie = match.groups()
        midi = 60 + PITCH_BASE[letter.upper()]
        if accidental:
            midi += ACCIDENTAL[accidental]
        elif letter.upper() in altered_letters:
            midi += 1 if sharp else -1
        if letter.islower():
            midi += 12
        for mark in octave_marks or "":
            midi += -12 if mark == "," else 12
        entry = {"midi": midi, "ql": _duration_of(suffix, base_len)}
        if tie and notes and notes[-1]["midi"] == midi and not notes[-1].get("tied_next"):
            notes[-1]["ql"] += entry["ql"]
            notes[-1]["tied_next"] = True
        else:
            notes.append(entry)
    return notes


def _clean_syllable(token: str) -> str:
    token = token.strip("~*_;,.!?")
    return token


def convert(path: str, out_path: str) -> Path:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    base_len = 0.25
    time_sig = "4/4"
    key_name = "G"
    tempo_bpm = 100
    for line in lines:
        stripped = line.split("%")[0].strip()
        code = stripped.split(":", 1)[0] if ":" in stripped else ""
        payload = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
        if code == "L" and "/" in payload:
            num, denom = payload.split("/")
            base_len = int(num) * 4.0 / int(denom)
        elif code == "M" and payload:
            time_sig = payload
        elif code == "K" and payload:
            key_name = payload
        elif code == "Q" and "=" in payload:
            m = re.search(r"=\s*([\d.]+)", payload)
            if m:
                tempo_bpm = float(m.group(1))

    _, altered_letters = _key_signature(key_name)
    sharp = _key_signature(key_name)[0] == "sharp"

    cursors = {voice: 0.0 for voice in VOICE_TO_PART}
    entries = {voice: [] for voice in VOICE_TO_PART}
    lyric_entries = []
    current_voice = None

    for raw_line in lines:
        line = raw_line.strip()
        code = line[:2]
        if re.match(r"^V:\s*[A-Za-z0-9,]+\s*$", line) or "clef=" in line:
            continue
        if code == "w:":
            verse = re.sub(r"^\s*(\d+)\.", "", line[2:])
            verse = verse.replace("~", " ")
            syllables = [_clean_syllable(tok) for tok in verse.split()]
            lyric_entries.append(syllables)
            continue
        if line.startswith("W:") or line.startswith("w:"):
            continue

        work_line = line
        while True:
            tag = VOICE_TAG.search(work_line)
            if not tag:
                break
            current_voice = tag.group(1)
            if current_voice not in VOICE_TO_PART:
                current_voice = None
            work_line = work_line[tag.end():]
            if code != "V:" and not work_line.split("%")[0].strip():
                break

        music = re.sub(r"!\S*?!", " ", work_line.split("%")[0]).strip()
        if not music or not current_voice or music.startswith(("%%", "!", '"')):
            continue
        tokens = _tokenize(music)
        parsed = _parse_notes(tokens, base_len, altered_letters, sharp)
        for entry in parsed:
            entries[current_voice].append(
                {"offset": cursors[current_voice], **entry}
            )
            cursors[current_voice] += entry["ql"]

    score = stream.Score()
    parts = {}
    for voice, (part_name, clef_obj) in VOICE_TO_PART.items():
        part = stream.Part(id=part_name)
        part.partName = part_name
        part.partAbbreviation = part_name[0]
        part.insert(0, tempo.MetronomeMark(number=tempo_bpm))
        part.insert(0, meter.TimeSignature(time_sig or "4/4"))
        part.insert(0, key.Key(key_name))
        part.insert(0, clef_obj)
        parts[voice] = part

    for voice, voice_entries in entries.items():
        part = parts[voice]
        for entry in voice_entries:
            part.insert(
                entry["offset"],
                note.Note(midi=entry["midi"], quarterLength=entry["ql"]),
            )

    syllables = lyric_entries[0] if lyric_entries else []
    for i, entry in enumerate(entries.get("S1V1", [])):
        if i < len(syllables) and syllables[i]:
            for element in parts["S1V1"].getElementsByOffset(
                entry["offset"], mustBeginInSpan=False
            ):
                if isinstance(element, note.Note):
                    element.lyric = syllables[i]
                    break

    for part in parts.values():
        score.insert(0, part)
    score.makeNotation(inPlace=True)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = score.write("musicxml", fp=str(out))
    return Path(result)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python tools/abc2musicxml.py input.abc [output.musicxml]")
        return 1
    abc_in = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else str(Path(abc_in).with_suffix(".musicxml"))
    result = convert(abc_in, out)
    print(f" converted: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path

from music21 import key, meter, note, stream, tempo


def build_sample_score(path: Path) -> Path:
    soprano_pitches = ["C5", "C5", "G5", "G5", "A5", "A5", "G5", "F5", "E5", "F5", "G5", "C5"]
    alto_pitches = ["G4", "A4", "C5", "C5", "C5", "D5", "D5", "C5", "B4", "C5", "B4", "G4"]
    tenor_pitches = ["E4", "F4", "G4", "G4", "A4", "F4", "G4", "A4", "G4", "A4", "G4", "E4"]
    bass_pitches = ["C3", "F3", "C3", "E3", "F3", "D3", "G3", "F3", "C3", "F3", "G3", "C3"]
    soprano_lyrics = ["나", "무", "사", "이", "빛", "나", "는", "풀", "위", "에", "서", "네"]

    score = stream.Score()
    score.insert(0, meter.TimeSignature("4/4"))
    score.insert(0, tempo.MetronomeMark(number=92))
    score.insert(0, key.Key("C"))

    for name, pitches, lyrics in [
        ("Soprano", soprano_pitches, soprano_lyrics),
        ("Alto", alto_pitches, [None] * len(alto_pitches)),
        ("Tenor", tenor_pitches, [None] * len(tenor_pitches)),
        ("Bass", bass_pitches, [None] * len(bass_pitches)),
    ]:
        part = stream.Part(id=name)
        part.partName = name
        part.partAbbreviation = name
        part.insert(0.0, tempo.MetronomeMark(number=92))
        part.insert(0.0, meter.TimeSignature("4/4"))
        for index, pitch in enumerate(pitches):
            n = note.Note(pitch, quarterLength=1.0)
            lyric = lyrics[index] if lyrics else None
            if lyric:
                n.lyric = lyric
            part.insert(float(index), n)
        score.insert(0, part)

    path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(path))
    return path


if __name__ == "__main__":
    out = build_sample_score(Path("data/sample_chorale.musicxml"))
    print(f" 샘플 악보 생성: {out}")

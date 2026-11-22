from __future__ import annotations

import numpy as np
from scipy.signal import butter, lfilter, sosfilt

from music21 import note as m21note, stream

from .phonemes import lyric_to_vowel

SAMPLE_RATE = 44100

VOWEL_FORMANTS = {
    "a": [730, 1090, 2440],
    "e": [530, 1840, 2480],
    "i": [270, 2290, 3010],
    "o": [570, 840, 2410],
    "u": [300, 870, 2240],
}

VOICE_PROFILES = {
    "soprano": {
        "label": "소프라노 파트 (남성 테너1, 1옥타브 하강)",
        "pitch_shift": -12,
        "formant_scale": 1.02,
        "vibrato_hz": 5.5,
        "vibrato_depth": 0.0035,
        "level": 1.0,
    },
    "alto": {
        "label": "알토 파트 (남성 테너2, 1옥타브 하강)",
        "pitch_shift": -12,
        "formant_scale": 1.0,
        "vibrato_hz": 5.2,
        "vibrato_depth": 0.0035,
        "level": 1.0,
    },
    "tenor": {
        "label": "테너 파트 (남성 보이스 그대로)",
        "pitch_shift": 0,
        "formant_scale": 0.95,
        "vibrato_hz": 4.8,
        "vibrato_depth": 0.0030,
        "level": 1.0,
    },
    "bass": {
        "label": "베이스 파트 (남성 베이스 그대로)",
        "pitch_shift": 0,
        "formant_scale": 0.85,
        "vibrato_hz": 4.5,
        "vibrato_depth": 0.0025,
        "level": 1.0,
    },
}

MALE_REFERENCE_FORMANT_SCALE = 1.0


def _resonator(center: float, bandwidth: float) -> np.ndarray:
    w0 = 2.0 * np.pi * center / SAMPLE_RATE
    r = np.exp(-np.pi * bandwidth / SAMPLE_RATE)
    b0 = (1.0 - r ** 2) * np.sin(w0)
    a = np.array([1.0, -2.0 * r * np.cos(w0), r ** 2])
    b = np.array([b0, 0.0, 0.0])
    return np.concatenate([b, a])


def _glottal_source(freq_array: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    phase = 2.0 * np.pi * np.cumsum(freq_array) / SAMPLE_RATE
    pulse = np.maximum(1.0 - np.cos(phase), 0.0)
    pulse = np.diff(np.concatenate([[0.0], pulse]))
    pulse = np.clip(pulse, 0.0, None)
    pulse /= max(pulse.max(), 1e-9)
    return pulse


def _apply_formants(signal: np.ndarray, vowel: str, formant_scale: float) -> np.ndarray:
    scale = MALE_REFERENCE_FORMANT_SCALE * formant_scale
    out = signal
    for center in VOWEL_FORMANTS[vowel]:
        freq = center * scale
        if freq >= SAMPLE_RATE / 2 - 100:
            continue
        coeffs = _resonator(freq, bandwidth=max(freq * 0.12, 60.0))
        b, a = coeffs[:3], coeffs[3:]
        out = lfilter(b, a, out)
    sos = butter(2, 7000 / (SAMPLE_RATE / 2), btype="low", output="sos")
    out = sosfilt(sos, out)
    return out


def _adsr(n: int, attack: float = 0.04, release: float = 0.09) -> np.ndarray:
    a = min(int(attack * SAMPLE_RATE), n // 3)
    r = min(int(release * SAMPLE_RATE), n // 3)
    env = np.ones(n)
    if a > 0:
        env[:a] = np.linspace(0.0, 1.0, a) ** 0.8
    if r > 0:
        env[-r:] = np.linspace(1.0, 0.0, r) ** 0.8
    return env


def _synthesize_note(
    midi_pitch: float,
    duration_sec: float,
    vowel: str,
    profile: dict,
    rng: np.random.Generator,
) -> np.ndarray:
    n = max(int(duration_sec * SAMPLE_RATE), 256)
    midi = midi_pitch + profile["pitch_shift"] + rng.normal(0.0, 0.05)
    base_freq = 440.0 * 2.0 ** ((midi - 69) / 12.0)
    base_freq = float(np.clip(base_freq, 55.0, 600.0))

    t = np.arange(n) / SAMPLE_RATE
    vibrato_env = np.clip((t - 0.18) / 0.4, 0.0, 1.0)
    freq_array = base_freq * (
        1.0 + profile["vibrato_depth"] * vibrato_env * np.sin(2.0 * np.pi * profile["vibrato_hz"] * t)
    )
    drift = rng.normal(0.0, 1.0, n)
    freq_array *= 1.0 + 0.002 * np.cumsum(drift) / max(n, 1)

    source = _glottal_source(freq_array, rng)

    breath = rng.normal(0.0, 1.0, n)
    sos = butter(2, [300 / (SAMPLE_RATE / 2), 5000 / (SAMPLE_RATE / 2)], btype="band", output="sos")
    breath = sosfilt(sos, breath)
    voiced = source + 0.015 * breath

    voiced = _apply_formants(voiced, vowel, profile["formant_scale"])
    voiced *= _adsr(n)
    peak = max(np.abs(voiced).max(), 1e-9)
    voiced = np.tanh(1.3 * voiced / peak) * 0.85
    return voiced * profile["level"]


def _tempo_of(part: stream.Part, score: stream.Score | None) -> float:
    for metronome in part.recurse().getElementsByClass("MetronomeMark"):
        if metronome.number:
            return float(metronome.number)
    if score is not None:
        for metronome in score.recurse().getElementsByClass("MetronomeMark"):
            if metronome.number:
                return float(metronome.number)
    context = part.getContextByClass("MetronomeMark")
    if context is not None and context.number:
        return float(context.number)
    return 120.0


def _events_of(part: stream.Part, tempo: float) -> list[dict]:
    events = []
    for n in part.recurse().notes:
        if isinstance(n, m21note.Note):
            note_obj = n
        elif n.isChord and len(n.notes):
            note_obj = n.notes[0]
        else:
            continue
        offset_beats = float(n.getOffsetInHierarchy(part))
        duration_beats = float(n.duration.quarterLength)
        if duration_beats <= 0:
            continue
        events.append(
            {
                "midi": int(note_obj.pitch.midi),
                "start": offset_beats * 60.0 / tempo,
                "duration": duration_beats * 60.0 / tempo,
                "vowel": lyric_to_vowel(note_obj.lyric),
            }
        )
    return events


def render_part(
    part: stream.Part, voice_name: str, score: stream.Score | None = None
) -> tuple[np.ndarray, list[dict]]:
    profile = VOICE_PROFILES[voice_name]
    rng = np.random.default_rng((abs(hash((str(part.id), voice_name)))) % (2**32))
    tempo = _tempo_of(part, score)
    events = _events_of(part, tempo)
    if not events:
        return np.zeros(0), []

    total_length = max(e["start"] + e["duration"] for e in events)
    total_samples = int(total_length * SAMPLE_RATE) + SAMPLE_RATE // 8
    buffer = np.zeros(total_samples, dtype=np.float64)
    for event in events:
        audio = _synthesize_note(event["midi"], event["duration"], event["vowel"], profile, rng)
        idx = int(event["start"] * SAMPLE_RATE)
        end = min(idx + len(audio), total_samples)
        if end > idx:
            buffer[idx:end] += audio[: end - idx]
    return buffer, events


def render_part_to_audio(part: stream.Part, voice_name: str):
    return render_part(part, voice_name)

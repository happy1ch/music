from __future__ import annotations

import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter

from .voice_synth import SAMPLE_RATE

REVERB_MIX = 0.22
COMB_DELAYS_MS = [29.7, 37.1, 41.1, 43.7]
COMB_DECAYS = [0.84, 0.82, 0.80, 0.78]
ALLPASS_DELAYS_MS = [5.0, 1.7]
ALLPASS_GAIN = 0.7

PART_PAN = {
    "soprano": 0.0,
    "alto": 0.25,
    "tenor": -0.25,
    "bass": 0.0,
}


def _reverb(mono: np.ndarray, sr: int = SAMPLE_RATE) -> np.ndarray:
    wet = np.zeros_like(mono)
    for delay_ms, decay in zip(COMB_DELAYS_MS, COMB_DECAYS):
        delay = int(sr * delay_ms / 1000.0)
        if delay < 1:
            continue
        numerator = np.zeros(delay + 1)
        numerator[0] = 1.0
        denominator = np.zeros(delay + 1)
        denominator[0] = 1.0
        denominator[delay] = -decay
        wet += lfilter(numerator, denominator, mono)
    for delay_ms in ALLPASS_DELAYS_MS:
        delay = max(int(sr * delay_ms / 1000.0), 1)
        feedback = ALLPASS_GAIN
        for i in range(len(wet) - delay):
            wet[i + delay] = -feedback * wet[i] + wet[i + delay] + feedback * wet[i + delay]
    return wet


def _stereo_pan(mono: np.ndarray, pan: float) -> np.ndarray:
    angle = (pan + 1.0) * np.pi / 4.0
    left = mono * np.cos(angle)
    right = mono * np.sin(angle)
    return np.stack([left, right], axis=1)


def mix_parts(rendered: dict[str, np.ndarray]) -> np.ndarray:
    if not rendered:
        raise ValueError("믹싱할 파트가 없습니다.")
    length = max(len(audio) for audio in rendered.values())
    mix = np.zeros((length, 2), dtype=np.float64)
    for voice_name, mono in rendered.items():
        padded = np.zeros(length, dtype=np.float64)
        padded[: len(mono)] = mono
        gain = {"soprano": 0.9, "alto": 0.9, "tenor": 1.0, "bass": 1.15}.get(voice_name, 1.0)
        mix += _stereo_pan(padded * gain, PART_PAN.get(voice_name, 0.0))
    for channel in range(2):
        mix[:, channel] += REVERB_MIX * _reverb(mix[:, channel])
    peak = np.abs(mix).max()
    if peak > 0:
        mix = mix / peak * 0.95
    return mix


def write_wav(path: str, audio: np.ndarray) -> None:
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.95
    pcm = (audio * 32767.0).astype(np.int16)
    wavfile.write(path, SAMPLE_RATE, pcm)

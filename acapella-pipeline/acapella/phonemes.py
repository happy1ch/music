import re

VOWELS = "aeiou"
KOREAN_VOWELS = "ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣㅐㅔㅚㅟㅘㅝㅙㅞㅢㅖㅒ"

JAMO_VOWEL_MAP = {
    "ㅏ": "a", "ㅐ": "e", "ㅑ": "a", "ㅒ": "e", "ㅓ": "o", "ㅔ": "e",
    "ㅕ": "o", "ㅖ": "e", "ㅗ": "o", "ㅘ": "a", "ㅙ": "e", "ㅚ": "u",
    "ㅛ": "o", "ㅜ": "u", "ㅝ": "o", "ㅞ": "e", "ㅟ": "u", "ㅠ": "u",
    "ㅡ": "u", "ㅢ": "u", "ㅣ": "i",
}

LATIN_FALLBACK = {
    "la": "a", "loo": "u", "loo1": "u", "ah": "a", "oo": "u", "o": "o",
    "a": "a", "e": "e", "i": "i", "u": "u",
}


def _last_hangul_syllable(text: str) -> str | None:
    for char in reversed(text):
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            return char
    return None


def _hangul_to_vowel(syllable: str) -> str | None:
    code = ord(syllable) - 0xAC00
    vowel_index = (code // 28) % 21
    for jamo, vowel in JAMO_VOWEL_MAP.items():
        if ord(jamo) - 0x1161 == vowel_index:
            return vowel
    return None


def lyric_to_vowel(lyric: str | None) -> str:
    if not lyric:
        return "a"
    text = str(lyric).strip().lower()
    if not text:
        return "a"

    syllable = _last_hangul_syllable(text)
    if syllable:
        vowel = _hangul_to_vowel(syllable)
        if vowel:
            return vowel

    if text in LATIN_FALLBACK:
        return LATIN_FALLBACK[text]

    matches = re.findall(f"[aeiou]", text)
    if matches:
        return matches[-1]

    return "a"

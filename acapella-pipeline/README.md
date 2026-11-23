# 남성 아카펠라 자동 생성 파이프라인 (SATB → Male A Cappella)

악보 PDF(또는 MusicXML)를 읽어 **소프라노·알토·테너·베이스 4부를 분리**하고,
각 파트를 **남성 보이스 합성엔진**으로 단선 노래로 만든 뒤, 4부를 **하나의 아카펠라 믹스**로 합치는 프로그램입니다.

## 처리 흐름

```
악보 PDF ──(Audiveris OMR)──> MusicXML ──(music21 파싱)──> SATB 파트 분리
      │                                                  ┌── soprano.wav (남성 테너1, 1옥타브 하강)
      │                                                  ├── alto.wav    (남성 테너2, 1옥타브 하강)
      │                                                  ├── tenor.wav   (남성 보이스 그대로)
      └──────────────────────────────────────────────────┤── bass.wav    (남성 베이스 그대로)
                                                         └── acapella_mix.wav (4부 합창 + 잔향)
```

## 설치

```bash
pip install -r requirements.txt
```

PDF 악보 인식(OMR)에는 [Audiveris](https://github.com/Audiveris/audiveris)가 필요합니다.
설치 후 `Audiveris` 명령이 PATH에 있어야 하며, 없으면 MusicXML(.musicxml/.mxl)로 입력하세요.
(MuseScore로 악보를 열어 File → Export → MusicXML 로 저장)

## 사용법

```bash
python main.py 곡이름.pdf -o output
python main.py 곡이름.musicxml -o output
```

출력:
- `output/soprano.wav` … `output/bass.wav` — 각 파트의 단선 남성 보이스
- `output/acapella_mix.wav` — 4부 아카펠라 합창 (스테레오, 잔향 포함)

샘플 악보로 전 과정 테스트:

```bash
python make_sample_score.py
python main.py data/sample_chorale.musicxml -o output
```

## 파트 분리 규칙

1. 파트 이름·약자에서 SATB 키워드 탐지 (Soprano/Alto/Tenor/Bass, 소프라노/알토/테너/베이스, Cantus 등)
2. 한 스태프에 여러 Voice가 있으면 파트로 분리 (2스태프 합창 악보 지원)
3. 이름으로 판별 불가 시 평균 음높이로 높은 순 → S, A, T, B 순서로 자동 배정

## 보이스 합성 방식 (Source–Filter 모델)

- **성대 파형**: 느린 위상 변조(비브라토 4.5~5.5Hz, 심도 음역별 차등) + 주파수 드리프트(jitter)
- **포먼트 필터**: 모음별 F1/F2/F3 존재 공진기 캐스케이드. 남성 음역별 포먼트 스케일 차등
  (소프라노/알토 파트는 남성이 1옥타브 내려 부르므로 테너형 포먼트, 베이스는 저포먼트)
- **모음 선택**: 악보에 가사가 있으면 음절 끝 모음 추출(한글 자모 모음 → a/e/i/o/u 매핑, 라틴어 fallback),
  가사가 없으면 "ah" 모음
- **에너지**: ADSR 엔벨로프(공격 40ms/방출 90ms), 성대·호흡 소음 혼합, 소프트 클리핑

## 제한 사항

- 스캔 PDF의 OMR 인식률은 악보 품질에 따라 달라집니다. 인쇄/벡터 PDF나 MusicXML을 권장합니다.
- 합성은 OCARINA류 간이 성모합신(singer-like synth)이며 실제 가창 음성이 아닙니다. 더 높은 완성도가
  필요하면 MusicXML → MIDI 변환 후 VOCALOID/Synthesizer V 등 상용 성모 합신으로 교체할 수 있습니다.
- 이탤릭/속도 표시(rit., fermata), 다성 셈여림은 단순화되어 있습니다.

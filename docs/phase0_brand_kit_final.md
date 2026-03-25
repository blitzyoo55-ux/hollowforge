# Phase 0 브랜드 킷 확정본
**확정일:** 2026-02-17
**브랜드 계정명:** `@hollow_doll` (전 플랫폼 통일)

---

## 1. 브랜드 핵심 정의

### 1.1 계정 정체성
- 메인 핸들: `@hollow_doll`
- 모든 플랫폼에서 동일 핸들 사용
- 워터마크, 캡션 시그니처, 파일명 규칙까지 동일 적용

### 1.2 세계관
- 세계관명: **Lab-XX**
- 설정: 미래의 비밀 연구소. 피험자들은 이름 대신 번호로만 불리며, 전신 라텍스 슈트와 마스크를 착용한 채 다양한 "실험"에 투입됨.
- 핵심 키워드: `faceless`, `anonymous`, `controlled`, `specimen`, `unit`

### 1.3 넘버링 체계
- 개체 식별자: `Unit-01`, `Unit-02`, `Unit-03` ...
- 포스트 단위로 고유 유닛 번호 부여
- 캡션/메타데이터/파일명에 동일 번호 동기화 권장

예시:
- `Lab-XX Log / Unit-07 / Series B / Neon Set`

---

## 2. 비주얼 시스템

### 2.1 컬러 팔레트 (Cyber Orange)
- **Primary**
  - Obsidian Black: `#0A0A0A`
  - Deep Charcoal: `#1A1A2E`
- **Accent**
  - Orange: `#FF6600` (시리즈별 변주 가능)

운용 원칙:
- 배경/슈트는 Black-Charcoal 중심 유지
- 강조광, 소품, UI 오버레이, 텍스트 포인트에 Orange 사용
- Orange 과다 사용 금지 (프레임 내 10~20% 권장)

### 2.2 체형 가이드
- 기본 체형: `mature_female`, `voluptuous`, `athletic`, `tall (170cm+)`
- 금지 네거티브: `child`, `loli`, `flat_chest`, `school_uniform`

### 2.3 배경 세트
- **Lab**: 하얀 타일벽 연구실
- **Dungeon**: 콘크리트 기반 밀실
- **Neon**: 사이버펑크 네온 환경

권장 로테이션:
- 주간 게시 기준 `Lab 40% / Dungeon 30% / Neon 30%`

---

## 3. 마스크 시리즈 정의

### Phase 1
- **Series A "Sealed"**: 풀페이스 가스마스크
- **Series B "Gaze"**: 하프마스크, 눈만 노출

### Phase 2
- **Series C "Silent"**: 볼개그 + 블라인드폴드
- **Series D "Doll"**: 키구루미 마스크
- **Series E "Hood"**: 라텍스 후드 전체 커버

---

## 4. 워터마크 규격
- 텍스트: `@hollow_doll`
- 위치: 우하단
- 투명도: 30~40%
- 폰트: `Montserrat Light`
- 색상: 기본 흰색 또는 Orange (`#FF6600`) 저채도 버전

---

## 5. ComfyUI 실전 프롬프트 템플릿

아래 템플릿은 그대로 복붙 후, `[ ]` 슬롯만 교체해서 사용.

### 5.1 공통 슬롯
- `[UNIT]`: Unit-01 같은 식별자
- `[BG_SET]`: `laboratory white tile wall` / `concrete dungeon` / `cyberpunk neon street`
- `[POSE]`: `standing`, `kneeling`, `leaning against wall` 등
- `[SHOT]`: `full body`, `cowboy shot`, `low angle full body`
- `[LIGHT]`: `cinematic rim light`, `hard studio light`, `neon backlight`

### 5.2 공통 네거티브 프롬프트

```text
child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, bad hands, extra fingers, malformed limbs, deformed face, text, logo, watermark, jpeg artifacts
```

---

## 6. WAI Illustrious v16 템플릿 (Booru 태그 형식)

### Series A - Sealed
```text
masterpiece, best quality, ultra detailed, 1woman, mature_female, voluptuous, athletic_build, tall, long_legs, latex bodysuit, glossy latex, full body, full-face gas mask, sealed mask, no visible face, orange accent straps, black suit, deep charcoal background, [BG_SET], [POSE], [SHOT], [LIGHT], dramatic shadows, high contrast, fetish fashion, unit id [UNIT]
```

### Series B - Gaze
```text
masterpiece, best quality, ultra detailed, 1woman, mature_female, voluptuous, athletic_build, tall, long_legs, latex bodysuit, glossy latex, half mask, covered mouth, visible eyes only, intense eye contact, black and orange palette, [BG_SET], [POSE], [SHOT], [LIGHT], moody atmosphere, cinematic composition, fetish fashion, unit id [UNIT]
```

### Series C - Silent
```text
masterpiece, best quality, ultra detailed, 1woman, mature_female, voluptuous, athletic_build, tall, long_legs, latex bodysuit, glossy latex, ball gag, blindfold, restrained aesthetic, black latex straps, orange edge light, [BG_SET], [POSE], [SHOT], [LIGHT], dramatic mood, fetish editorial, unit id [UNIT]
```

### Series D - Doll
```text
masterpiece, best quality, ultra detailed, 1woman, mature_female, voluptuous, athletic_build, tall, long_legs, latex bodysuit, glossy latex, kigurumi mask, expressionless doll face mask, uncanny beauty, black and orange accents, [BG_SET], [POSE], [SHOT], [LIGHT], surreal fashion, clean composition, unit id [UNIT]
```

### Series E - Hood
```text
masterpiece, best quality, ultra detailed, 1woman, mature_female, voluptuous, athletic_build, tall, long_legs, latex bodysuit, full latex hood, fully covered head, faceless, black latex shine, orange reflected light, [BG_SET], [POSE], [SHOT], [LIGHT], atmospheric haze, fetish fashion editorial, unit id [UNIT]
```

WAI Negative:
```text
child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, bad hands, extra digits, malformed limbs, deformed, bad proportions, text, logo, watermark
```

---

## 7. Pony v6 템플릿 (score 태그 포함)

### Series A - Sealed
```text
score_9, score_8_up, score_7_up, source_anime, rating_explicit, 1girl, mature_female, voluptuous, athletic, tall, long legs, glossy latex catsuit, full-face gas mask, sealed, faceless, black theme, orange accent, [BG_SET], [POSE], [SHOT], [LIGHT], cinematic, high detail, unit [UNIT]
```

### Series B - Gaze
```text
score_9, score_8_up, score_7_up, source_anime, rating_explicit, 1girl, mature_female, voluptuous, athletic, tall, long legs, glossy latex catsuit, half mask, mouth covered, visible eyes, eye focus, black and orange palette, [BG_SET], [POSE], [SHOT], [LIGHT], cinematic, high detail, unit [UNIT]
```

### Series C - Silent
```text
score_9, score_8_up, score_7_up, source_anime, rating_explicit, 1girl, mature_female, voluptuous, athletic, tall, long legs, glossy latex catsuit, ball gag, blindfold, restrained look, fetish styling, orange rim light, [BG_SET], [POSE], [SHOT], [LIGHT], cinematic, high detail, unit [UNIT]
```

### Series D - Doll
```text
score_9, score_8_up, score_7_up, source_anime, rating_explicit, 1girl, mature_female, voluptuous, athletic, tall, long legs, glossy latex catsuit, kigurumi doll mask, smooth doll face, uncanny, black suit, orange details, [BG_SET], [POSE], [SHOT], [LIGHT], cinematic, high detail, unit [UNIT]
```

### Series E - Hood
```text
score_9, score_8_up, score_7_up, source_anime, rating_explicit, 1girl, mature_female, voluptuous, athletic, tall, long legs, glossy latex catsuit, full latex hood, fully covered face, faceless, black dominant, orange highlights, [BG_SET], [POSE], [SHOT], [LIGHT], cinematic, high detail, unit [UNIT]
```

Pony Negative:
```text
score_4, score_5, child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, bad hands, extra fingers, fused fingers, watermark, text, logo
```

---

## 8. Flux schnell 템플릿 (자연어)

### Series A - Sealed
```text
Lab-XX specimen [UNIT], a mature tall voluptuous athletic woman in a glossy black latex bodysuit, wearing a full-face sealed gas mask with no visible facial features. Cyber Orange accents (#FF6600) on straps and reflected lighting. Scene: [BG_SET]. Pose: [POSE]. Shot: [SHOT]. Lighting: [LIGHT]. Cinematic fetish fashion editorial, high contrast, sharp details, clean composition.
```

### Series B - Gaze
```text
Lab-XX specimen [UNIT], a mature tall voluptuous athletic woman in a glossy black latex bodysuit, wearing a half mask that covers the lower face with only the eyes visible. Cyber Orange accents (#FF6600), dark obsidian and charcoal base palette. Scene: [BG_SET]. Pose: [POSE]. Shot: [SHOT]. Lighting: [LIGHT]. Cinematic fetish editorial look, dramatic eye focus, detailed latex texture.
```

### Series C - Silent
```text
Lab-XX specimen [UNIT], a mature tall voluptuous athletic woman in a glossy black latex bodysuit, styled with a black blindfold and ball gag, faceless submissive aesthetic, controlled laboratory mood. Cyber Orange accent lighting (#FF6600). Scene: [BG_SET]. Pose: [POSE]. Shot: [SHOT]. Lighting: [LIGHT]. Dark cinematic fetish fashion scene with strong texture and clean framing.
```

### Series D - Doll
```text
Lab-XX specimen [UNIT], a mature tall voluptuous athletic woman in a glossy black latex bodysuit, wearing an expressionless kigurumi doll mask, uncanny artificial beauty theme. Cyber Orange accents (#FF6600) over obsidian and charcoal tones. Scene: [BG_SET]. Pose: [POSE]. Shot: [SHOT]. Lighting: [LIGHT]. Stylized cinematic fetish editorial, high detail, polished finish.
```

### Series E - Hood
```text
Lab-XX specimen [UNIT], a mature tall voluptuous athletic woman in a glossy black latex bodysuit, wearing a full latex hood that completely covers the head and face, fully anonymous identity. Cyber Orange accent reflections (#FF6600), dark controlled atmosphere. Scene: [BG_SET]. Pose: [POSE]. Shot: [SHOT]. Lighting: [LIGHT]. Cinematic fetish fashion photography, high detail, dramatic contrast.
```

Flux Negative:
```text
Do not generate minors or youthful appearance. No child, loli, teen, school uniform, flat chest. Avoid low resolution, blur, bad anatomy, malformed hands, extra fingers, text artifacts, logos, or watermark.
```

---

## 9. 운영 체크리스트 (Phase 1 착수용)
- 계정 핸들 전 플랫폼 선점 및 통일 (`@hollow_doll`)
- 게시물 템플릿에 `Unit-xx` 자동 삽입
- 워터마크 프리셋(우하단, 30~40%, Montserrat Light) 저장
- Phase 1 시리즈(A/B) 우선 생산, Phase 2(C/D/E)는 큐레이션 후 확장
- 배경 세트 로테이션(Lab/Dungeon/Neon) 일정표 적용


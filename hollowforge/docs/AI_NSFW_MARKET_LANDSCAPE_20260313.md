# HollowForge Market Landscape Report

작성일: 2026-03-13  
대상 프로젝트: HollowForge  
목적: 공개 데이터 기반으로 AI 생성 성인 콘텐츠 시장 지형을 파악하고, 현재 `latex + bdsm` 중심 방향성이 전략적으로 타당한지 재검토한다.

관련 문서:
- [HollowForge Market Validation Matrix](./HOLLOWFORGE_MARKET_VALIDATION_MATRIX_20260313.md)

---

## Executive Summary

- 공개 반응 규모만 보면 가장 큰 수요는 여전히 `넓은 미형 여성/솔로/바디 강조` 클러스터에 몰려 있다.
- `latex + bdsm`는 수요가 아예 약한 영역은 아니지만, 메인 시장축이라기보다 `시그니처 fetish layer`에 가깝다.
- 생성 생태계에서는 `극단적 niche성`보다 `캐릭터 정확도`, `결과물의 청결함`, `재현성`, `고정 팬을 만들 수 있는 오리지널 캐릭터성`이 더 크게 반응한다.
- 구독형 플랫폼에서는 태그보다 `페르소나`, `업로드 일관성`, `팬 유지`, `PPV/캠페인`, `외부 유입`이 더 중요하다.
- 유명 IP 캐릭터 기반 콘텐츠는 실제 수요가 매우 크지만, 저작권/상표/플랫폼 리스크가 높아 사업 축으로 삼기 어렵다.

**결론:**  
HollowForge는 `latex + bdsm`를 버릴 필요는 없지만, 이를 프로젝트의 유일한 정체성으로 두는 것은 비효율적이다. 더 높은 가능성은 `오리지널 캐릭터 중심`, `미형/스타성`, `alt/goth/editorial`, `비IP cosplay-coded 스타일`을 코어로 두고, `latex/bdsm`는 프리미엄 확장 라인으로 두는 구조에 있다.

---

## Scope and Method

이번 정리는 2026년 3월 13일 기준 공개 웹 데이터만 사용했다.

분석에 활용한 플랫폼은 아래와 같다.

- `Rule34.xxx`: 태그별 게시물 규모를 통해 공개 소비 수요와 아카이브형 발견 패턴 확인
- `Civitai`: 어떤 모델/프롬프트 생태계가 실제로 큰 반응을 받는지 확인
- `Fansly`: 공식 leaderboard 구조를 통해 노출/수익 경쟁 메커니즘 확인
- `OnlyFans`: 공식 Creator Center와 공개 프로필 지표를 통해 수익화 메커니즘 확인

### 해석 시 주의점

- `Rule34` 수치는 태그 볼륨이다. 수익 지표가 아니라 소비/발견 수요 지표다.
- `Civitai`는 모델/커뮤니티 반응 지표다. 직접적인 최종 소비 시장과는 다르다.
- `Fansly`는 공식 공개 랭킹 구조가 있어 비교적 읽을 수 있지만, 세부 장르 데이터는 제한적이다.
- `OnlyFans`는 플랫폼 차원의 공개 태그/카테고리 데이터가 약하다. 따라서 장르 heatmap보다 `운영/수익화 메커니즘` 위주로 봐야 한다.
- 본 문서는 사업 전략 참고용이며, 법률 자문 문서가 아니다.

---

## Market Heatmap

### 1. 공개 수요 강도 요약

| 클러스터 | 공개 반응 강도 | 대표 공개 수치 | 시사점 |
|---|---:|---:|---|
| 넓은 미형 여성/솔로 바디 클러스터 | 매우 높음 | `female` 약 9,814,748, `solo` 약 3,845,156, `ass` 약 3,637,682, `big breasts` 약 3,327,345, `thick thighs` 약 2,302,748 | 가장 큰 바닥 수요는 broad appeal 미형/솔로/바디 비주얼이다. |
| AI 생성 자체 | 높음 | `ai generated` 약 2,699,319, `stable diffusion` 약 355,318 | AI 생성물은 이미 대규모 공급 축이다. |
| 유명 IP / 프랜차이즈 | 매우 높음 | `pokemon` 약 867,475, `disney` 약 260,336, `league of legends` 약 197,559 | IP 기반 발견성은 매우 강하지만 HollowForge에는 법적 리스크가 크다. |
| 발/액세서리 fetish-adjacent | 높음 | `feet` 약 788,862, `foot fetish` 약 163,055, `choker` 약 323,808 | `latex`보다 공개 볼륨이 크며 테스트 가치가 높다. |
| 복종/지배감 coded 관계형 fetish | 중상 | `submissive` 약 144,197, `submissive female` 약 87,579 | 관계성/서사와 연결하기 좋다. |
| `latex` / fetish | 중간 | `latex` 약 111,519, `fetish` 약 14,146 | niche로서는 의미 있으나 메인 축으로는 좁다. |
| `goth` / `goth girl` / `cosplay` | 중간~중상 | `goth` 약 100,510, `goth girl` 약 57,900, `cosplay` 약 57,252 | 오리지널 캐릭터 브랜딩과 결합하기 좋은 스타일 훅이다. |

### 2. 첫 번째 해석

- `latex`는 생각보다 작은 niche는 아니다.
- 하지만 시장 전체를 견인하는 중심 수요와는 거리가 있다.
- 가장 큰 수요는 여전히 `넓은 미형`, `바디 중심`, `솔로 소비`, `직관적인 매력 포인트`에 있다.
- 따라서 `latex/bdsm`를 메인으로 전면에 두면, 유입 풀을 스스로 좁힐 가능성이 높다.

---

## Platform Landscape

## Rule34.xxx

`Rule34`는 가장 직접적으로 “사람들이 많이 쌓아두고 찾는 것”을 보여준다.

### 핵심 신호

- `female` 약 981만
- `breasts` 약 770만
- `solo` 약 384만
- `nude` 약 356만
- `pussy` 약 379만
- `sex` 약 272만
- `big breasts` 약 333만
- `thick thighs` 약 230만
- `ass` 약 364만

이 수치는 시장의 최대 공약수가 `미형 여성 솔로 이미지 + 강한 신체 포인트`임을 보여준다.

### HollowForge 관련 신호

- `latex` 약 11.1만
- `goth` 약 10만
- `goth girl` 약 5.8만
- `cosplay` 약 5.7만
- `foot fetish` 약 16.3만
- `submissive` 약 14.4만

### 해석

- `latex`는 살아 있는 niche다.
- 하지만 `feet`, `foot fetish`, `submissive` 같은 인접 fetish 신호와 비교해도 절대 우위는 아니다.
- `goth`, `cosplay-coded`, `accessory fetish`, `submissive dynamic` 같은 축이 `latex`와 비슷하거나 더 넓은 확장성을 가진다.

### 중요한 추가 신호

유명 IP 태그도 매우 크다.

- `pokemon` 약 86.7만
- `disney` 약 26만
- `league of legends` 약 19.8만

이는 시장에서 IP가 실제로 강력한 트래픽 엔진이라는 뜻이다. 다만 HollowForge가 이를 따라가기는 위험하다.

---

## Civitai

`Civitai`는 “어떤 스타일과 어떤 제작 파이프라인이 실제로 큰 반응을 얻는가”를 보여준다.

### 핵심 신호

- [`WAI-illustrious-SDXL`](https://civitai.com/models/827184/wai-nsfw-illustrious-sdxl)
  - Published: 2025-12-18
  - Reviews: 11,138
  - 페이지 표시 통계: 157,532 / 12.1M / 15.3M
  - 릴리즈 설명: 기본 스타일 청결도와 캐릭터 정확도 개선을 강조
- [`Prefectious XL NSFW`](https://civitai.com/models/992378)
  - Reviews: 9,405
- [`REED_XXX_illustrious_SDXL`](https://civitai.com/models/1717562/reednsfwillustrioussdxl)
  - Published: 2026-03-05
  - Reviews: 163
- [`Over 10K CivitAI Top NSFW Prompts dataset`](https://civitai.com/articles/22181/over-10k-civitai-top-nsfw-prompts-dataset)
  - 2025-11-07 공개
  - 상위 NSFW 이미지 1만 개 이상에서 프롬프트를 추출했다고 명시
- [`Master Generators (mature) Leaderboard`](https://civitai.com/leaderboard/images-nsfw)
  - mature creator 리더보드가 별도로 존재

### 해석

가장 중요한 점은 이것이다.

- 대형 반응 모델은 대체로 `fetish 전용성`보다 `클린함`, `정확한 캐릭터 재현`, `높은 호환성`, `다목적 사용성`을 앞세운다.
- 다시 말해 Civitai에서 강한 것은 “특정 fetish만 잘하는 모델”보다 “많은 창작자가 오래 쓰는 기반 모델”이다.
- HollowForge가 시장성을 높이려면, `세계관 + 캐릭터 일관성 + 결과물 청결함`을 먼저 확보하고 fetish는 그 위에 얹는 것이 맞다.

---

## Fansly

`Fansly`는 공식적으로 revenue 기반 공개 경쟁 구조를 제공한다는 점이 중요하다.

### 핵심 신호

- [`March Leaderboard FAQ`](https://help.fansly.com/en/articles/10946985-march-leaderboard-faq)
  - 랭킹 기준: 총 revenue
  - 업데이트 주기: 15분
  - 공개 범위: 상위 500명
  - 비공개 순위 확인: 상위 1000명까지

### 해석

- Fansly는 콘텐츠 태그보다 `매출 성과` 중심으로 작동한다.
- 즉, 플랫폼 내부 경쟁력은 “어떤 fetish를 하느냐”보다 “얼마나 팬을 결제하게 만드느냐”에 더 가깝다.
- 이 구조에서는 시각적 fetish 자체보다 `캐릭터 페르소나`, `팬 고착도`, `반복 구매 동기`가 더 중요해진다.

---

## OnlyFans

`OnlyFans`는 공개 카테고리 heatmap이 약하다. 대신 공식 가이드와 공개 프로필 집계에서 운영 원리가 드러난다.

### 공식 운영 신호

- [`OnlyFans Creator Center`](https://blog.onlyfans.com/creator-center/)
  - 3 million creators 이상
  - niche의 중요성을 직접 강조
  - `engage with your fans`, `post consistently`, `quality vs quantity`, `PPV`, `marketing`, `retaining your fans`를 핵심으로 제시
- [`How to Promote Your OnlyFans Profile`](https://blog.onlyfans.com/how-to-promote-your-onlyfans-profile/)
  - 외부 소셜 유입
  - 협업
  - 프로모션
  - 워터마크
  - 기존 팬 유지

### 공개 프로필 지표 예시

[`Feedspot OnlyFans 리스트`](https://influencers.feedspot.com/onlyfans_instagram_influencers/)에 따르면 다음과 같은 공개 지표가 보인다.

- `Francia James`: 2.4M likes, free, 17.4K posts
- `Angela White`: 3.1M likes
- `Skylar Mae`: 6.1M likes
- `Liliana Jasmine`: 10.3M likes

### 해석

- OnlyFans에서 강한 것은 특정 태그 하나보다 `강한 외부 팬베이스`, `꾸준한 공급`, `재방문 동기`, `계정 운영력`이다.
- 이는 AI 생성 프로젝트에도 그대로 적용된다.
- HollowForge가 실제 구독형 전환을 노린다면 `한 번 세게 보이는 fetish`보다 `반복 소비 가능한 캐릭터`가 더 중요하다.

---

## Strategic Reading for HollowForge

## 현재 `latex + bdsm` 방향성은 맞는가?

부분적으로는 맞다.

### 맞는 이유

- 시각적으로 강한 차별성이 있다.
- 라텍스는 재질감만으로도 브랜드 식별력이 생긴다.
- power dynamic 계열은 관계성/서사를 만들기 좋다.
- 일반적인 glamour보다 더 뚜렷한 브랜드 결을 만들 수 있다.

### 한계

- 메인 유입 풀을 너무 좁힌다.
- broad appeal 미형/캐릭터 시장보다 절대 볼륨이 작다.
- fetish의 강도가 너무 앞서면 반복 소비보다 “한 번 보고 지나가는” 구조가 되기 쉽다.
- 구독 플랫폼형 비즈니스에서는 `fetish object`보다 `follow할 페르소나`가 더 중요하다.

### 판단

`latex + bdsm`는 잘못된 방향이 아니라, **프로젝트 전체의 메인 축으로 두기엔 좁고, 브랜드 시그니처/프리미엄 라인으로 두기엔 좋은 방향**이다.

---

## 더 가능성이 높은 영역

현재 공개 데이터만 놓고 보면 HollowForge가 검증해야 할 우선순위는 아래와 같다.

### 1순위: Original Character + Beauty + Editorial

- 핵심 요소: 미형, 얼굴 기억도, 캐릭터 일관성, 강한 스타성
- 이유: Civitai와 구독 플랫폼 양쪽에서 동시에 먹히는 구조다.
- HollowForge에 가장 부족한 것도 바로 이 축이다.

### 2순위: Alt / Goth / Cosplay-coded but Non-IP

- 핵심 요소: 검은 톤, 체인/초커/메이크업, 대체 서브컬처 감성, 비IP 코스튬 언어
- 이유: `goth`, `goth girl`, `cosplay`는 공개 수요가 존재하면서도 오리지널 캐릭터 브랜딩과 결합하기 쉽다.

### 3순위: Feet / Accessory / Submissive-coded Adjacent Fetish

- 핵심 요소: 발, 신발, 초커, 목걸이, 부츠, posture, 관계성
- 이유: `latex`보다 더 넓은 공개 볼륨을 확인할 수 있었고, fetish 강도를 조절하기도 쉽다.

### 4순위: Latex / BDSM Premium Line

- 핵심 요소: 라텍스 재질감, 구속감, confinement, power dynamic
- 이유: 차별화와 시그니처성은 강하지만, 코어 유입층으로 보기엔 좁다.

---

## Recommended Positioning

HollowForge의 더 나은 포지셔닝은 아래 구조다.

### Core Line

`Original Character + Beauty + Editorial + Alt/Goth`

- 신규 유입 확보용
- 반복 소비 가능한 페르소나 구축용
- 추후 구독형 전환의 기반

### Expansion Line

`Cosplay-coded Non-IP + Accessory Fetish + Submissive-coded Narrative`

- 취향층 확장
- 시각적 다양성 확보
- 캐릭터별 차별화 포인트 생성

### Premium Line

`Latex + BDSM + Confinement`

- 브랜드 시그니처
- 고강도 niche 대응
- 메인 라인보다 좁지만 높은 식별력 보유

---

## IP and Copyright Risk

## 왜 유명 IP가 위험한가

시장 반응이 큰 것과 법적으로 안전한 것은 전혀 다른 문제다.

### 저작권 리스크

미국 저작권청은 파생저작물을 기존 저작물에 기반한 작업으로 설명하고, 원저작권자의 허락 없이 만든 변형은 침해가 될 수 있다고 밝힌다.

- [`Circular 14: Copyright in Derivative Works and Compilations`](https://www.copyright.gov/circs/circ14.pdf)

또한 저작권청 Compendium은 캐릭터의 시각적 요소가 충분히 독창적이면 보호될 수 있다고 설명한다.

- [`Compendium Chapter 900`](https://www.copyright.gov/comp3/chap900/chap900-draft-3-15-19.pdf)

즉, 이름만 안 쓴다고 안전해지지 않는다.

### 상표 / 브랜드 오인 리스크

상표 문제는 단순히 “이름이 같은가”가 아니라, 소비자가 출처, 제휴, 후원 관계를 오인할 가능성이 있는가로 본다.

USPTO 실무 문서와 결정문에서도 `source or sponsorship` 기준이 반복된다.

- USPTO/TMEP 인용 포함 사례: [FIRST LADY TTAB filing](https://ttabvue.uspto.gov/ttabvue/ttabvue-87293691-EXA-7.pdf)

즉, 아래 요소가 recognizable하면 위험하다.

- 의상 실루엣
- 대표 색 조합
- 헤어스타일
- 상징 장신구
- 로고/문양
- 캐릭터명
- 프랜차이즈 태그

### 플랫폼 리스크

OnlyFans 약관은 업로더가 제3자 권리에 필요한 라이선스와 동의를 확보해야 한다고 둔다.

- [`OnlyFans Terms of Service`](https://onlyfans.com/terms)

이는 단순한 법률 리스크뿐 아니라 아래 리스크로 이어진다.

- 게시물 삭제
- 계정 제한
- DMCA 대응
- 정산/운영 리스크
- 외부 결제 및 제휴 리스크

### 전략적 결론

유명 IP는 `트래픽`은 강하지만 `사업 자산`으로는 불안정하다.  
HollowForge는 `자체 캐릭터 자산`을 쌓는 편이 맞다.

---

## Recommendations

## 전략 결론

HollowForge는 아래 원칙으로 재정렬하는 것이 가장 합리적이다.

1. `latex + bdsm`를 폐기하지 않는다.
2. 대신 이를 코어가 아니라 `프리미엄 라인`으로 내린다.
3. 코어는 `오리지널 캐릭터 + 미형/스타성 + alt/goth/editorial`로 둔다.
4. 중간 확장 축으로 `cosplay-coded non-IP`, `feet/accessory`, `submissive-coded narrative`를 테스트한다.
5. 모든 실험은 “태그 반응”보다 “캐릭터 반복 반응”을 더 중요하게 본다.

## 운영 실험 제안

다음 검증은 `태그 기반`보다 `라인 기반`으로 설계하는 것이 좋다.

### Lane A: Original Alt/Goth Glamour

- 목적: 가장 넓은 유입 가능성 검증
- 평가 포인트: 얼굴 기억도, favorite 전환, 반복 favorite

### Lane B: Non-IP Cosplay-coded Character Editorial

- 목적: IP 없이도 “캐릭터 판타지”가 먹히는지 검증
- 평가 포인트: 시리즈 소비성, 캐릭터 일관성, 저장 가치

### Lane C: Latex / BDSM Premium

- 목적: 시그니처 fetish 라인의 상대 강도 검증
- 평가 포인트: 강한 반응도, niche 집중도, premium lane 분리 가능성

### Lane D: Feet / Accessory / Submissive-coded Adjacent

- 목적: 더 넓은 fetish-adjacent 볼륨 검증
- 평가 포인트: broad appeal과 fetish specificity의 균형

---

## Final Assessment

현재 공개 데이터 기준으로 HollowForge의 가장 현실적인 방향은 아래와 같다.

**권장 포지션**

`Original character studio with high-beauty editorial core, alt/goth flavor, and latex/bdsm premium extension`

이 포지션은 아래 세 가지를 동시에 충족한다.

- 시장의 더 넓은 수요와 연결된다.
- HollowForge만의 차별화 요소를 유지할 수 있다.
- 유명 IP를 쓰지 않고도 자체 자산을 축적할 수 있다.

---

## Sources

### Rule34

- https://rule34.xxx/index.php?page=post&s=list&tags=ai_generated
- https://rule34.xxx/index.php?page=post&s=list&tags=female
- https://rule34.xxx/index.php?page=post&s=list&tags=solo
- https://rule34.xxx/index.php?page=post&s=list&tags=ass
- https://rule34.xxx/index.php?page=post&s=list&tags=big_breasts
- https://rule34.xxx/index.php?page=post&s=list&tags=thick_thighs
- https://rule34.xxx/index.php?page=post&s=list&tags=latex
- https://rule34.xxx/index.php?page=post&s=list&tags=foot_fetish
- https://rule34.xxx/index.php?page=post&s=list&tags=choker
- https://rule34.xxx/index.php?page=post&s=list&tags=goth_girl
- https://rule34.xxx/index.php?page=post&s=list&tags=cosplay
- https://rule34.xxx/index.php?page=post&s=list&tags=submissive
- https://rule34.xxx/index.php?page=post&s=list&tags=pokemon
- https://rule34.xxx/index.php?page=post&s=list&tags=disney
- https://rule34.xxx/index.php?page=post&s=list&tags=league_of_legends

### Civitai

- https://civitai.com/models/827184/wai-nsfw-illustrious-sdxl
- https://civitai.com/models/992378
- https://civitai.com/models/1717562/reednsfwillustrioussdxl
- https://civitai.com/articles/22181/over-10k-civitai-top-nsfw-prompts-dataset
- https://civitai.com/leaderboard/images-nsfw

### Fansly

- https://help.fansly.com/en/articles/10946985-march-leaderboard-faq

### OnlyFans

- https://blog.onlyfans.com/creator-center/
- https://blog.onlyfans.com/how-to-promote-your-onlyfans-profile/
- https://onlyfans.com/terms

### Copyright / Trademark

- https://www.copyright.gov/circs/circ14.pdf
- https://www.copyright.gov/comp3/chap900/chap900-draft-3-15-19.pdf
- https://ttabvue.uspto.gov/ttabvue/ttabvue-87293691-EXA-7.pdf

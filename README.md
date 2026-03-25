# NSFW Market Research - Rule34.xxx Tag Analyzer

AI 생성 NSFW 콘텐츠의 시장 수요 분석 도구.
Rule34.xxx Gelbooru API를 통해 태그별 콘텐츠 수, 유저 반응도, 코멘트 수를 수집.

## Setup

```bash
cd 04_AI_Creative/nsfw-market-research
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# 전체 태그 수집
python src/tag_collector.py

# 출력: data/tag_stats_YYYYMMDD_HHMM.csv, data/combo_stats_YYYYMMDD_HHMM.csv
```

## Config

- `config/target_tags.yaml` - 수집 대상 태그 목록 (primary/secondary/trending)

## Output Fields

| Field | Description |
|-------|-------------|
| tag | 태그명 |
| post_count | 해당 태그의 전체 게시물 수 |
| avg_score | 샘플 게시물의 평균 점수 (유저 반응도) |
| sampled_comments | 상위 게시물의 코멘트 수 |

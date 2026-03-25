"""
Rule34.xxx Tag Statistics Collector

Collects tag-level post counts via the Gelbooru-compatible API (no scraping).
Uses direct API calls for tag stats and post sampling.
"""

import time
import logging
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import os

import requests
import yaml
import pandas as pd
from tqdm import tqdm

BASE_URL = "https://api.rule34.xxx/index.php"
RATE_LIMIT_DELAY = 1.5  # seconds between requests


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            Path(__file__).parent.parent / "logs" / "collector.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).parent.parent / ".env")
API_KEY = os.getenv("R34_API_KEY", "")
USER_ID = os.getenv("R34_USER_ID", "")
_FIRST_COMBO_XML_LOGGED = False


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_to_list(data) -> list[dict]:
    """Normalize API payload to list for JSON variants across endpoints."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "comment" in data and isinstance(data["comment"], list):
            return data["comment"]
        if "post" in data and isinstance(data["post"], list):
            return data["post"]
        if "tag" in data and isinstance(data["tag"], list):
            return data["tag"]
    return []


def load_target_tags(config_path: str = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "target_tags.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_tag_info(tag_name: str) -> dict | None:
    """Get tag metadata (post count, type) from API."""
    params = {
        "page": "dapi",
        "s": "tag",
        "q": "index",
        "limit": "1",
        "name": tag_name,
        "api_key": API_KEY,
        "user_id": USER_ID,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        tag_elem = root.find("tag")
        if tag_elem is not None:
            return {
                "count": _safe_int(tag_elem.attrib.get("count", 0)),
                "name": tag_elem.attrib.get("name", ""),
                "type": _safe_int(tag_elem.attrib.get("type", 0)),
                "id": _safe_int(tag_elem.attrib.get("id", 0)),
                "ambiguous": tag_elem.attrib.get("ambiguous", "false").lower() == "true",
            }
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch tag '{tag_name}': {e}")
        return None


def get_post_count_for_tags(tag_combo: str, log_raw_xml_once: bool = False) -> int:
    """Get total post count for a tag combination (e.g. 'latex mask')."""
    global _FIRST_COMBO_XML_LOGGED
    normalized_tags = " ".join(tag_combo.replace("+", " ").split())
    params_xml = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "limit": "1",
        "tags": normalized_tags,
        "api_key": API_KEY,
        "user_id": USER_ID,
    }

    # Reliable path: XML root includes count attribute on Gelbooru-compatible APIs.
    try:
        resp_xml = requests.get(BASE_URL, params=params_xml, timeout=15)
        resp_xml.raise_for_status()
        if log_raw_xml_once and not _FIRST_COMBO_XML_LOGGED:
            _FIRST_COMBO_XML_LOGGED = True
            logger.debug("First combo XML response: %s", resp_xml.text)
        root = ET.fromstring(resp_xml.text)
        return _safe_int(root.attrib.get("count", 0))
    except Exception as e:
        logger.warning(f"Failed to fetch combo count for '{normalized_tags}': {e}")
        return 0


def sample_posts(tag: str, limit: int = 50) -> list[dict]:
    """Sample recent posts for a tag to analyze engagement."""
    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": "1",
        "limit": str(min(limit, 100)),
        "tags": tag,
        "api_key": API_KEY,
        "user_id": USER_ID,
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = _normalize_to_list(resp.json())
        for post in data:
            post["score"] = _safe_int(post.get("score", 0))
            post["id"] = _safe_int(post.get("id", 0))
            post["comment_count"] = _safe_int(post.get("comment_count", 0))
        return data
    except Exception as e:
        logger.warning(f"Failed to sample posts for '{tag}': {e}")
        return []


def collect_tag_stats(tags: list[str]) -> pd.DataFrame:
    """Collect statistics for a list of tags."""
    results = []

    for tag in tqdm(tags, desc="Collecting tag stats"):
        tag_info = get_tag_info(tag)
        time.sleep(RATE_LIMIT_DELAY)

        post_count = 0
        tag_type = ""
        if tag_info:
            post_count = tag_info.get("count", 0)
            tag_type = tag_info.get("type", "")

        # Sample posts for engagement metrics
        posts = sample_posts(tag, limit=20)
        time.sleep(RATE_LIMIT_DELAY)

        avg_score = 0
        total_comments = 0
        has_ai_tag = False
        if posts:
            scores = [p.get("score", 0) for p in posts]
            avg_score = sum(scores) / len(scores) if scores else 0
            total_comments = sum(_safe_int(p.get("comment_count", 0)) for p in posts)
            has_ai_tag = any("ai_generated" in p.get("tags", "").split() for p in posts)

        results.append({
            "tag": tag,
            "post_count": post_count,
            "tag_type": tag_type,
            "sample_size": len(posts),
            "avg_score": round(avg_score, 2),
            "sampled_comments": total_comments,
            "has_ai_tag": has_ai_tag,
            "collected_at": datetime.now().isoformat(),
        })

        logger.info(
            f"[{tag}] posts={post_count}, avg_score={avg_score:.1f}, "
            f"comments={total_comments}"
        )

    return pd.DataFrame(results)


def collect_combo_stats(primary_tags: list[str], modifier_tags: list[str]) -> pd.DataFrame:
    """Collect post counts for tag combinations (e.g. latex + mask)."""
    results = []

    combos = [(p, m) for p in primary_tags for m in modifier_tags if p != m]
    for idx, (tag_a, tag_b) in enumerate(tqdm(combos, desc="Collecting combo stats")):
        combo_query = f"{tag_a} {tag_b}"
        combo_display = f"{tag_a}+{tag_b}"
        count = get_post_count_for_tags(combo_query, log_raw_xml_once=(idx == 0))
        time.sleep(RATE_LIMIT_DELAY)

        results.append({
            "tag_a": tag_a,
            "tag_b": tag_b,
            "combo": combo_display,
            "combo_query": combo_query,
            "post_count": count,
            "collected_at": datetime.now().isoformat(),
        })

    return pd.DataFrame(results)


def main():
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    tag_config = load_target_tags()
    all_tags = (
        tag_config.get("primary_tags", [])
        + tag_config.get("secondary_tags", [])
        + tag_config.get("trending_tags", [])
    )

    logger.info(f"Starting collection for {len(all_tags)} tags")

    # 1. Individual tag stats
    tag_stats = collect_tag_stats(all_tags)
    tag_stats_path = data_dir / f"tag_stats_{datetime.now():%Y%m%d_%H%M}.csv"
    tag_stats.to_csv(tag_stats_path, index=False, encoding="utf-8-sig")
    logger.info(f"Tag stats saved to {tag_stats_path}")

    # 2. Combo stats (primary x primary only to limit requests)
    primary = tag_config.get("primary_tags", [])
    if len(primary) > 1:
        combo_stats = collect_combo_stats(primary[:8], primary[:8])
        combo_path = data_dir / f"combo_stats_{datetime.now():%Y%m%d_%H%M}.csv"
        combo_stats.to_csv(combo_path, index=False, encoding="utf-8-sig")
        logger.info(f"Combo stats saved to {combo_path}")

    # 3. Summary
    print("\n" + "=" * 60)
    print("TOP TAGS BY POST COUNT")
    print("=" * 60)
    top = tag_stats.sort_values("post_count", ascending=False).head(15)
    for _, row in top.iterrows():
        print(f"  {row['tag']:25s} | {row['post_count']:>10,} posts | "
              f"avg_score={row['avg_score']:.1f}")

    print("\n" + "=" * 60)
    print("TOP TAGS BY ENGAGEMENT (avg_score)")
    print("=" * 60)
    engaged = tag_stats.sort_values("avg_score", ascending=False).head(15)
    for _, row in engaged.iterrows():
        print(f"  {row['tag']:25s} | score={row['avg_score']:>6.1f} | "
              f"{row['post_count']:>10,} posts")


if __name__ == "__main__":
    main()

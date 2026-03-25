"""
Rule34.xxx Full Tag Ranker

Collects tags with a multi-strategy approach (seed lookups + pattern discovery
+ pid probing) and then samples posts for top tags to compute engagement signals.
"""

import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

BASE_URL = "https://api.rule34.xxx/index.php"
RATE_LIMIT_DELAY = 1.5
TAG_REQUEST_DELAY = 0.35
PAGE_LIMIT = 100
TARGET_TAG_COUNT = 1000
TOP_SAMPLE_COUNT = 200
POST_SAMPLE_PER_TAG = 10

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


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


SEED_TAGS = _unique_preserve_order(
    [
        # Body parts / features
        "breasts", "big_breasts", "small_breasts", "huge_breasts", "flat_chest", "cleavage",
        "nipples", "areolae", "ass", "big_ass", "thighs", "thick_thighs", "hips", "waist",
        "stomach", "navel", "pussy", "cameltoe", "penis", "balls", "testicles", "foreskin",
        "hands", "fingers", "legs", "calves", "feet", "toes", "soles", "armpits", "tongue",
        "mouth", "lips", "teeth", "face", "eyes", "eyebrows", "ears", "neck", "shoulders",
        "back", "spine", "collarbone", "anus", "butthole", "pubic_hair", "body_hair",
        # Core action / sexual acts
        "sex", "vaginal", "anal", "oral", "blowjob", "deepthroat", "handjob", "titjob",
        "footjob", "fingering", "masturbation", "cum", "creampie", "cum_in_pussy",
        "cum_on_face", "cumshot", "facial", "bukkake", "double_penetration", "tribadism",
        "scissoring", "rimming", "spanking", "groping", "kissing", "french_kiss", "sucking",
        "licking", "nipple_suck", "paizuri", "grinding", "threesome", "foursome", "gangbang",
        "orgy", "public_sex", "voyeurism", "exhibitionism", "peeing", "squirting", "milking",
        # Clothing / style / presentation
        "nude", "naked", "lingerie", "bikini", "micro_bikini", "swimsuit", "school_swimsuit",
        "stockings", "thighhighs", "pantyhose", "garter_belt", "high_heels", "boots",
        "gloves", "dress", "miniskirt", "skirt_lift", "panties", "no_panties", "bra",
        "no_bra", "yuri", "yaoi", "crossdressing", "cosplay", "maid", "nurse", "office_lady",
        "school_uniform", "gym_uniform", "apron", "latex", "leotard", "bodysuit", "kimono",
        # Fetish / kink
        "bondage", "bdsm", "shibari", "rope", "handcuffs", "blindfold", "gag", "ball_gag",
        "collar", "leash", "dominatrix", "femdom", "humiliation", "petplay", "tentacles",
        "monster_girl", "vore", "inflation", "giantess", "size_difference", "mind_control",
        "hypnosis", "mind_break", "ahegao", "choking", "rough_sex", "slave", "submission",
        "dominant", "cumflation", "pov", "facesitting", "facefucking", "cunnilingus",
        # Composition / participants
        "solo", "solo_female", "solo_male", "1girl", "2girls", "3girls", "4girls", "5girls",
        "multiple_girls", "1boy", "2boys", "multiple_boys", "girl_on_top", "cowgirl_position",
        "reverse_cowgirl_position", "missionary", "doggystyle", "standing_sex", "spread_legs",
        "from_behind", "hetero", "group_sex", "bisexual", "interracial", "age_difference",
        # Character archetypes / demographics
        "milf", "teen", "loli", "shota", "futanari", "femboy", "trap", "tomboy", "muscular",
        "petite", "chubby", "bbw", "pregnant", "mother", "teacher", "student", "idol",
        "princess", "elf", "demon_girl", "angel", "catgirl", "fox_girl", "bunny_girl",
        # Hair / appearance attributes
        "long_hair", "short_hair", "ponytail", "twintails", "braid", "messy_hair",
        "black_hair", "brown_hair", "blonde_hair", "red_hair", "pink_hair", "blue_hair",
        "white_hair", "silver_hair", "green_hair", "purple_hair", "orange_hair", "grey_hair",
        "heterochromia", "glasses", "freckles", "tanlines", "dark_skin", "pale_skin",
        # Art / generation tags
        "anime", "manga", "comic", "3d", "cgi", "realistic", "photo", "ai_generated",
        "stable_diffusion", "midjourney", "highres", "lowres", "sketch", "monochrome",
        "colored", "animated", "video", "sound", "loop", "pixel_art",
        # Major franchises / games / anime
        "pokemon", "genshin_impact", "honkai_star_rail", "fate_grand_order", "fate_series",
        "touhou", "fire_emblem", "azur_lane", "blue_archive", "arknights", "nikke",
        "league_of_legends", "dota_2", "overwatch", "fortnite", "minecraft", "roblox",
        "world_of_warcraft", "final_fantasy", "persona", "nier_automata", "zelda",
        "super_mario", "metroid", "street_fighter", "tekken", "mortal_kombat",
        "resident_evil", "devil_may_cry", "cyberpunk_2077", "the_witcher", "one_piece",
        "naruto", "bleach", "dragon_ball", "my_hero_academia", "jujutsu_kaisen",
        "demon_slayer", "chainsaw_man", "evangelion", "attack_on_titan", "sailor_moon",
        "spy_x_family", "vocaloid", "hatsune_miku",
        # Places / settings / context
        "bedroom", "bathroom", "kitchen", "classroom", "school", "office", "library",
        "locker_room", "pool", "beach", "forest", "outdoors", "night", "day", "street",
        "train", "bus", "car", "hotel", "onsen", "shower", "bathtub", "dungeon",
        # Situations / post types
        "undressing", "upskirt", "underboob", "sideboob", "nip_slip", "wardrobe_malfunction",
        "see-through", "wet_clothes", "pantyshot", "spread_pussy", "ass_focus",
        "breast_focus", "foot_focus", "close-up", "full_body", "mirror", "selfie", "rape",
        "consensual", "uncensored", "censored", "mosaic_censoring", "pixel_censoring",
    ]
)

PATTERN_QUERIES = [
    "a%", "b%", "c%", "d%", "e%", "f%", "g%", "h%", "i%", "j%",
    "k%", "l%", "m%", "n%", "o%", "p%", "q%", "r%", "s%", "t%",
    "u%", "v%", "w%", "x%", "y%", "z%",
    "1%", "2%", "3%",
    "girl%", "boy%", "big_%", "small_%", "cum%", "sex%", "anal%",
    "oral%", "nude%", "futanari%", "milf%", "loli%", "anime%", "genshin%",
]

PID_PROBES = _unique_preserve_order(
    [*range(0, 30), 35, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 400, 500, 700, 900,
     1200, 1500, 2000, 3000, 5000, 8000, 10000]
)


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_to_list(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "post" in data and isinstance(data["post"], list):
            return data["post"]
    return []


def _parse_tag_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    rows: list[dict] = []
    for tag_elem in root.findall("tag"):
        rows.append(
            {
                "id": _safe_int(tag_elem.attrib.get("id", 0)),
                "name": tag_elem.attrib.get("name", ""),
                "count": _safe_int(tag_elem.attrib.get("count", 0)),
                "type": _safe_int(tag_elem.attrib.get("type", 0)),
                "ambiguous": tag_elem.attrib.get("ambiguous", "false").lower() == "true",
            }
        )
    return rows


def _fetch_tag_rows(params: dict) -> list[dict]:
    merged_params = {
        "page": "dapi",
        "s": "tag",
        "q": "index",
        "api_key": API_KEY,
        "user_id": USER_ID,
    }
    merged_params.update(params)
    try:
        resp = requests.get(BASE_URL, params=merged_params, timeout=30)
        resp.raise_for_status()
        return _parse_tag_xml(resp.text)
    except Exception as e:
        logger.warning(f"Failed tag request params={params}: {e}")
        return []


def fetch_tag_page(pid: int, limit: int = PAGE_LIMIT) -> list[dict]:
    return _fetch_tag_rows({"limit": str(limit), "pid": str(pid)})


def fetch_tag_exact(name: str) -> dict | None:
    rows = _fetch_tag_rows({"limit": "1", "name": name})
    if not rows:
        return None
    return rows[0]


def fetch_tags_by_pattern(name_pattern: str, limit: int = PAGE_LIMIT) -> list[dict]:
    # Different Gelbooru forks vary in accepted sort params; try both forms.
    attempts = [
        {"limit": str(limit), "name_pattern": name_pattern, "order": "count"},
        {"limit": str(limit), "name_pattern": name_pattern, "orderby": "count", "order": "desc"},
        {"limit": str(limit), "name_pattern": name_pattern},
    ]
    for params in attempts:
        rows = _fetch_tag_rows(params)
        if rows:
            return rows
    return []


def sample_posts_for_tag(tag: str, limit: int = POST_SAMPLE_PER_TAG) -> list[dict]:
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
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        posts = _normalize_to_list(resp.json())
        for p in posts:
            p["score"] = _safe_int(p.get("score", 0))
            p["comment_count"] = _safe_int(p.get("comment_count", 0))
        return posts
    except Exception as e:
        logger.warning(f"Failed to sample posts for '{tag}': {e}")
        return []


def collect_full_tag_ranking(
    target_tag_count: int = TARGET_TAG_COUNT,
    page_limit: int = PAGE_LIMIT,
    top_sample_count: int = TOP_SAMPLE_COUNT,
    post_sample_per_tag: int = POST_SAMPLE_PER_TAG,
) -> pd.DataFrame:
    tag_by_name: dict[str, dict] = {}

    def _merge_rows(rows: list[dict], source: str) -> None:
        for row in rows:
            name = str(row.get("name", "")).strip()
            if not name:
                continue
            count = _safe_int(row.get("count", 0))
            if count <= 0:
                continue
            existing = tag_by_name.get(name)
            if existing is None or count > _safe_int(existing.get("count", 0)):
                merged = dict(row)
                merged["source"] = source
                tag_by_name[name] = merged

    logger.info("Strategy 1/3: exact XML lookup for curated seed tags")
    for seed in tqdm(SEED_TAGS, desc="Seed tag lookups"):
        row = fetch_tag_exact(seed)
        if row:
            _merge_rows([row], source="seed_exact")
        time.sleep(TAG_REQUEST_DELAY)

    logger.info("Strategy 2/3: XML name_pattern discovery")
    for pattern in tqdm(PATTERN_QUERIES, desc="Pattern discovery"):
        rows = fetch_tags_by_pattern(name_pattern=pattern, limit=page_limit)
        _merge_rows(rows, source=f"pattern:{pattern}")
        time.sleep(TAG_REQUEST_DELAY)

    logger.info("Strategy 3/3: pid probing for broader coverage")
    for pid in tqdm(PID_PROBES, desc="PID probes"):
        rows = fetch_tag_page(pid=pid, limit=page_limit)
        _merge_rows(rows, source=f"pid:{pid}")
        time.sleep(TAG_REQUEST_DELAY)
        if len(tag_by_name) >= target_tag_count and pid >= 300:
            break

    if not tag_by_name:
        return pd.DataFrame()

    logger.info(f"Collected {len(tag_by_name)} unique tags before ranking")
    df = pd.DataFrame(tag_by_name.values())
    df = (
        df.sort_values("count", ascending=False)
        .drop_duplicates(subset=["name"], keep="first")
        .reset_index(drop=True)
    )
    df["rank_by_post_count"] = df.index + 1
    df["avg_score"] = 0.0
    df["avg_comment_count"] = 0.0
    df["sample_size"] = 0
    df["collected_at"] = datetime.now().isoformat()

    if target_tag_count > 0 and len(df) > target_tag_count:
        df = df.head(target_tag_count).copy()

    sample_n = min(top_sample_count, len(df))
    logger.info(f"Sampling posts for top {sample_n} tags ({post_sample_per_tag} posts each)")
    for idx in tqdm(range(sample_n), desc="Sampling top tags"):
        tag = str(df.at[idx, "name"])
        posts = sample_posts_for_tag(tag, limit=post_sample_per_tag)
        time.sleep(RATE_LIMIT_DELAY)

        if posts:
            avg_score = sum(p.get("score", 0) for p in posts) / len(posts)
            avg_comment_count = sum(p.get("comment_count", 0) for p in posts) / len(posts)
            df.at[idx, "avg_score"] = round(avg_score, 2)
            df.at[idx, "avg_comment_count"] = round(avg_comment_count, 2)
            df.at[idx, "sample_size"] = len(posts)

    return df


def print_summary(df: pd.DataFrame) -> None:
    if df.empty:
        print("No data collected.")
        return

    print("\n" + "=" * 72)
    print("TOP 50 TAGS BY POST COUNT")
    print("=" * 72)
    top_by_count = df.sort_values("count", ascending=False).head(50)
    for _, row in top_by_count.iterrows():
        print(
            f"{row['rank_by_post_count']:>4}. {row['name'][:32]:32s} | "
            f"posts={int(row['count']):>10,} | avg_score={row['avg_score']:>6.2f}"
        )

    print("\n" + "=" * 72)
    print("TOP 50 TAGS BY AVG SCORE")
    print("=" * 72)
    top_by_score = df.sort_values("avg_score", ascending=False).head(50)
    for rank, (_, row) in enumerate(top_by_score.iterrows(), start=1):
        print(
            f"{rank:>4}. {row['name'][:32]:32s} | "
            f"avg_score={row['avg_score']:>6.2f} | posts={int(row['count']):>10,}"
        )


def main() -> None:
    log_dir = Path(__file__).parent.parent / "logs"
    data_dir = Path(__file__).parent.parent / "data"
    log_dir.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)

    df = collect_full_tag_ranking()
    if df.empty:
        logger.error("No tag data collected. Exiting.")
        return

    out_path = data_dir / f"full_tag_ranking_{datetime.now():%Y%m%d_%H%M}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved full tag ranking to {out_path}")
    print_summary(df)


if __name__ == "__main__":
    main()

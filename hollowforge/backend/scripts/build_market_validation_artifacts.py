#!/usr/bin/env python3
"""Build queue-ready market validation artifacts for HollowForge."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT_DIR / "docs"

DEFAULT_NEGATIVE_PROMPT = (
    "child, teen, underage, school uniform, text, logo, watermark, blurry, "
    "lowres, deformed, cropped face"
)
PHASE1_CHECKPOINT = "prefectIllustriousXL_v70.safetensors"
WORKFLOW_LANE = "sdxl_illustrious"
SAMPLER = "euler_a"
SCHEDULER = "normal"
RESOLUTION = (832, 1216)
REPEATS_PER_VARIANT = 5


@dataclass(frozen=True)
class PackDefinition:
    pack_id: str
    line_series: str
    line_label: str
    pack_label: str
    tone: str
    heat_level: str
    creative_autonomy: str
    steps: int
    cfg: float
    scene_hook: str
    camera_plan: str
    pose_plan: str
    environment: str
    device_focus: str
    lighting_plan: str
    material_focus: str
    intensity_hook: str
    concept_brief: str
    creative_brief: str
    base_tags: tuple[str, ...]
    variants: tuple[str, ...]


PACKS: tuple[PackDefinition, ...] = (
    PackDefinition(
        pack_id="A1",
        line_series="line_a_original_beauty",
        line_label="Line A - Original Beauty / Editorial",
        pack_label="Luxury Editorial Baseline",
        tone="editorial",
        heat_level="steamy",
        creative_autonomy="hybrid",
        steps=30,
        cfg=5.2,
        scene_hook="Luxury hotel editorial built around a high-value original star persona.",
        camera_plan="Portrait and three-quarter glamour coverage with clean composition.",
        pose_plan="Calm confidence with direct eye contact and elegant posture.",
        environment="High-end suite, balcony, or lounge space with premium set dressing.",
        device_focus="No device anchor; character beauty and styling lead the frame.",
        lighting_plan="Soft key light, window glow, and polished cinematic highlights.",
        material_focus="Silk, satin, jewelry, and upscale interior textures.",
        intensity_hook="Tasteful sensuality and aspirational beauty rather than fetish coding.",
        concept_brief=(
            "Original adult beauty star, solo editorial glamour, luxury lingerie styling, "
            "premium hotel interiors, polished celebrity aura."
        ),
        creative_brief=(
            "Keep the subject clearly adult, beautiful, and non-IP. Prioritize elegant beauty, "
            "premium styling, readable face, and expensive atmosphere."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "luxury editorial glamour",
            "refined facial features",
            "luminous skin",
            "silk lingerie styling",
            "hotel suite interior",
            "confident gaze",
            "soft key light",
            "cinematic portrait",
            "tasteful sensuality",
        ),
        variants=(
            "close portrait, seated on a velvet chaise, direct eye contact",
            "three-quarter shot, balcony doorway framing, city lights behind",
            "mirror-side standing pose, one shoulder turned toward camera",
            "lounge bar corner, champagne table styling, relaxed posture",
            "window light silhouette, elegant hand placement, upscale suite depth",
        ),
    ),
    PackDefinition(
        pack_id="A2",
        line_series="line_a_original_beauty",
        line_label="Line A - Original Beauty / Editorial",
        pack_label="Star Quality / Red Carpet Glam",
        tone="campaign",
        heat_level="steamy",
        creative_autonomy="hybrid",
        steps=35,
        cfg=5.4,
        scene_hook="Celebrity-coded beauty shoot with red carpet energy and paparazzi flash.",
        camera_plan="Beauty close-ups and polished half-body red carpet angles.",
        pose_plan="Public-facing confidence with sharp chin line and star posture.",
        environment="Premiere arrival, backstage glam room, or flash-heavy event corridor.",
        device_focus="No prop dependency; makeup, gown structure, and public presence carry the shot.",
        lighting_plan="Flash glam, specular highlights, and beauty dish polish.",
        material_focus="Sheer couture, sequins, satin drape, polished hair and makeup.",
        intensity_hook="Star aura and desirability over explicit exposure.",
        concept_brief=(
            "Original adult beauty star, solo high-fashion glamour, red carpet mood, "
            "celebrity aura, flash-heavy editorial."
        ),
        creative_brief=(
            "Bias toward clean high-fashion beauty, paparazzi glam, and repeatable star presence. "
            "Keep the scene glamorous and non-IP."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "high-fashion glamour",
            "sheer couture styling",
            "red carpet mood",
            "paparazzi flash glam",
            "celebrity aura",
            "beauty close-up",
            "polished makeup",
            "sleek hair",
            "public star presence",
        ),
        variants=(
            "arrival carpet close-up, flash bulbs popping, chin raised",
            "backstage vanity mirror, makeup lights, poised half-turn",
            "spotlight hallway, trailing gown movement, controlled stride",
            "event step-and-repeat framing, camera-facing confidence",
            "afterparty lounge, glossy flash portrait, relaxed smile",
        ),
    ),
    PackDefinition(
        pack_id="A3",
        line_series="line_a_original_beauty",
        line_label="Line A - Original Beauty / Editorial",
        pack_label="Dark Romance / Elegant Drama",
        tone="editorial",
        heat_level="steamy",
        creative_autonomy="director",
        steps=35,
        cfg=5.4,
        scene_hook="Romantic darkness with couture corsetry and moody cinematic beauty.",
        camera_plan="Dramatic portraiture and medium shots that preserve elegance.",
        pose_plan="Graceful poses with controlled melancholy and long hair motion.",
        environment="Candlelit chamber, velvet salon, or shadowed gallery space.",
        device_focus="No apparatus; costume silhouette and atmosphere do the work.",
        lighting_plan="Candle glow, dramatic side light, and deep shadow separation.",
        material_focus="Corset couture, velvet, lace, and antique metallic accents.",
        intensity_hook="Beauty-first dark romance with sensual tension, not overt fetish.",
        concept_brief=(
            "Original adult beauty star, solo dark romance editorial, corset couture, "
            "candlelit interiors, elegant dramatic light."
        ),
        creative_brief=(
            "Push dramatic elegance, shadow contrast, and romantic melancholy while keeping the "
            "character aspirational and clearly original."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "romantic darkness",
            "corset couture",
            "candlelit chamber",
            "elegant pose",
            "flowing hair",
            "dramatic side light",
            "velvet textures",
            "melancholic glamour",
        ),
        variants=(
            "velvet chaise portrait, candle clusters, distant gaze",
            "arched doorway framing, long hair motion, side-lit face",
            "dark salon standing pose, gloved hands, dramatic shadow",
            "library balcony view, corset silhouette, warm candle glow",
            "ornate chair seated pose, soft smoke haze, quiet intensity",
        ),
    ),
    PackDefinition(
        pack_id="B1",
        line_series="line_b_alt_goth",
        line_label="Line B - Alt / Goth / Non-IP Cosplay-coded",
        pack_label="Alt Goth Core",
        tone="editorial",
        heat_level="steamy",
        creative_autonomy="hybrid",
        steps=30,
        cfg=5.4,
        scene_hook="Alt-goth heroine with strong face identity and cool club confidence.",
        camera_plan="Portrait and waist-up coverage with attitude-forward framing.",
        pose_plan="Calm dominance, cool eye contact, and fashion-led posture.",
        environment="Club backroom, alley neon spill, dressing mirror, or velvet booth.",
        device_focus="No device dependency; makeup, lace, and silhouette define the pack.",
        lighting_plan="Moody club light, colored spill, and hard rim accents.",
        material_focus="Black lace, leather accents, chokers, sheer layers.",
        intensity_hook="High-character alternative beauty without IP references.",
        concept_brief=(
            "Original adult alt-goth heroine, solo fashion-forward beauty, black lace, smoky eyes, "
            "club lighting, strong character read."
        ),
        creative_brief=(
            "Keep the face memorable, the styling alt-forward, and the energy cool rather than chaotic. "
            "Avoid obvious IP cosplay cues."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "alt goth beauty",
            "black lace styling",
            "choker",
            "smoky eyes",
            "cool confidence",
            "moody club light",
            "dark manicure",
            "sharp styling",
        ),
        variants=(
            "club stairwell portrait, purple spill light, calm expression",
            "velvet booth seating, lace gloves, direct stare",
            "dressing mirror setup, layered jewelry, subtle smirk",
            "rainy window backdrop, black lipstick, side profile",
            "narrow hallway framing, ripped tights styling, rim-lit silhouette",
        ),
    ),
    PackDefinition(
        pack_id="B2",
        line_series="line_b_alt_goth",
        line_label="Line B - Alt / Goth / Non-IP Cosplay-coded",
        pack_label="Sci-fi Cosplay-coded",
        tone="campaign",
        heat_level="steamy",
        creative_autonomy="director",
        steps=35,
        cfg=5.6,
        scene_hook="Original sci-fi heroine with sleek costume language and clean silhouette.",
        camera_plan="Hero framing, medium full-body, and visor-forward portrait angles.",
        pose_plan="Steady tactical confidence with readable silhouette.",
        environment="Neon lab, scanner arch, sterile corridor, or reflective pod bay.",
        device_focus="Visor, suit paneling, and clean futuristic costume structure.",
        lighting_plan="Cold lighting, edge highlights, and cyan neon accent.",
        material_focus="Sleek bodysuit fabrics, chrome trim, translucent panels.",
        intensity_hook="Non-IP cosplay-coded futurism built for repeatable character branding.",
        concept_brief=(
            "Original adult sci-fi heroine, solo sleek tactical bodysuit, visor, neon lab, "
            "futuristic styling, clean silhouette."
        ),
        creative_brief=(
            "Aim for original futuristic character appeal rather than direct franchise resemblance. "
            "Keep the costume readable and premium."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "sleek tactical bodysuit",
            "visor styling",
            "neon lab",
            "futuristic fashion",
            "clean silhouette",
            "cold lighting",
            "chrome accents",
            "non-ip sci-fi heroine",
        ),
        variants=(
            "scanner corridor hero pose, cyan glow, precise silhouette",
            "control console close-up, visor reflection, gloved hands",
            "transparent pod bay framing, half-body turn, chrome highlights",
            "elevator chamber portrait, composed expression, narrow light strips",
            "clean white lab bridge, forward stride, structured suit design",
        ),
    ),
    PackDefinition(
        pack_id="B3",
        line_series="line_b_alt_goth",
        line_label="Line B - Alt / Goth / Non-IP Cosplay-coded",
        pack_label="Occult Fashion",
        tone="editorial",
        heat_level="steamy",
        creative_autonomy="director",
        steps=35,
        cfg=5.5,
        scene_hook="Mystic fashion heroine that feels original, intelligent, and collectible.",
        camera_plan="Strong portrait and seated ritual-table compositions.",
        pose_plan="Controlled elegance with ritual-coded gestures and poised stillness.",
        environment="Dark academy library, sigil chamber, balcony, or candle desk.",
        device_focus="Sigils, costume structure, gloves, and jewelry as worldbuilding anchors.",
        lighting_plan="Candle glow, library shadow, and stained-glass color spill.",
        material_focus="Structured outfits, velvet, metal charms, occult detailing.",
        intensity_hook="Worldbuilding-rich character lane with strong non-IP identity.",
        concept_brief=(
            "Original adult occult fashion heroine, solo dark academy styling, ritual sigils, "
            "structured outfit, mystic elegance."
        ),
        creative_brief=(
            "Build a collectible original character with occult fashion cues and readable face identity. "
            "Stay away from franchise-like iconography."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "occult fashion",
            "ritual sigils",
            "dark academy",
            "structured outfit",
            "mystic elegance",
            "library set",
            "candle glow",
            "ornate jewelry",
        ),
        variants=(
            "library aisle portrait, glowing sigils, composed stare",
            "ritual desk seating, layered books, candlelit hands",
            "balcony over old stacks, long coat silhouette, moody profile",
            "stained glass chamber, velvet gloves, poised half-turn",
            "stone altar backdrop, occult symbols on the floor, calm posture",
        ),
    ),
    PackDefinition(
        pack_id="C1",
        line_series="line_c_fetish_adjacent",
        line_label="Line C - Fetish-adjacent Broad Appeal",
        pack_label="Legwear / Heels / Choker",
        tone="editorial",
        heat_level="steamy",
        creative_autonomy="hybrid",
        steps=30,
        cfg=5.2,
        scene_hook="Broad-appeal glamour lane built on legs, heels, and high-polish styling.",
        camera_plan="Long-leg framing, seated beauty, and mirror-friendly angles.",
        pose_plan="Playful confidence with clean posture and fashion-led body language.",
        environment="Dressing room, hotel hallway, vanity mirror, or staircase landing.",
        device_focus="Stilettos, stockings, and choker styling carry the tension.",
        lighting_plan="Soft flash glam, vanity bulbs, and clean indoor highlights.",
        material_focus="Stockings, satin, glossy heels, jewelry, smooth skin lighting.",
        intensity_hook="Fetish-adjacent, not niche-first; broad glamour comes first.",
        concept_brief=(
            "Original adult glamour heroine, solo long-leg styling, stockings, stilettos, choker, "
            "soft flash beauty."
        ),
        creative_brief=(
            "Keep this pack broad and clickable. Emphasize glamour, polish, long-leg composition, and "
            "repeatable star quality."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "long legs",
            "stockings",
            "stilettos",
            "choker",
            "glam pose",
            "soft flash lighting",
            "polished makeup",
            "broad appeal glamour",
        ),
        variants=(
            "vanity chair pose, crossed legs, mirror bulbs behind",
            "hotel hallway stride, heel emphasis, confident expression",
            "mirror wall lean, long-leg composition, soft smile",
            "staircase landing pose, one knee bent, flash-glam finish",
            "dressing stool portrait, stockings highlight, clean pose line",
        ),
    ),
    PackDefinition(
        pack_id="C2",
        line_series="line_c_fetish_adjacent",
        line_label="Line C - Fetish-adjacent Broad Appeal",
        pack_label="Boots / Authority",
        tone="campaign",
        heat_level="steamy",
        creative_autonomy="hybrid",
        steps=30,
        cfg=5.4,
        scene_hook="Authority-coded glamour pack centered on boots, gloves, and posture.",
        camera_plan="Low-tilt hero shots and strong doorway compositions.",
        pose_plan="Commanding stance, shoulders back, deliberate stride, no chaos.",
        environment="Doorway frame, corridor, leather chair set, or clean industrial hall.",
        device_focus="Thigh-high boots, gloves, and silhouette authority.",
        lighting_plan="Editorial side light with crisp contrast and floor reflections.",
        material_focus="Leather, polished boots, clean tailoring, metallic trims.",
        intensity_hook="Power-coded styling with broader appeal than direct BDSM coding.",
        concept_brief=(
            "Original adult glamour heroine, solo thigh-high boots, gloves, commanding stance, "
            "editorial power pose."
        ),
        creative_brief=(
            "Keep the result glamorous and powerful, not campy. Boots and posture should define the lane."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "thigh-high boots",
            "gloves",
            "commanding stance",
            "doorway framing",
            "editorial power pose",
            "polished leather details",
            "structured styling",
            "authority-coded glamour",
        ),
        variants=(
            "doorway hero pose, boots forward, hard side light",
            "leather chair set, crossed legs, calm dominance",
            "corridor stride, low-tilt framing, gloves visible",
            "industrial railing setup, chin raised, tailored silhouette",
            "spotlight stage entry, strong stance, clean reflections",
        ),
    ),
    PackDefinition(
        pack_id="C3",
        line_series="line_c_fetish_adjacent",
        line_label="Line C - Fetish-adjacent Broad Appeal",
        pack_label="Harness / Accessory Tension",
        tone="editorial",
        heat_level="steamy",
        creative_autonomy="hybrid",
        steps=35,
        cfg=5.5,
        scene_hook="Accessory-tension lane that hints at restraint without becoming niche-only.",
        camera_plan="Studio editorial framing with clear read on styling hardware.",
        pose_plan="Controlled body lines and fashion tension in the shoulders and waist.",
        environment="Clean studio, chrome stool, curtain set, or white cyclorama.",
        device_focus="Body harness, cuffs as styling detail, and precise accessory placement.",
        lighting_plan="Soft box clarity with controlled contrast and product-like polish.",
        material_focus="Harness straps, metal hardware, fitted fabrics, sculpted silhouette.",
        intensity_hook="Fashion restraint coding kept broad and elegant.",
        concept_brief=(
            "Original adult fashion heroine, solo body harness styling, cuffs as accessories, "
            "studio tension, controlled elegance."
        ),
        creative_brief=(
            "Keep it legible as fashion-first. Tension should come from styling and pose, not from explicit action."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "body harness styling",
            "cuffs as fashion accessories",
            "tension pose",
            "studio backdrop",
            "controlled elegance",
            "clean silhouette",
            "metal hardware accents",
            "fashion restraint coding",
        ),
        variants=(
            "seamless studio portrait, front-facing harness detail, soft box light",
            "chrome stool pose, waist emphasis, composed expression",
            "chain curtain background, angled torso, reflective hardware",
            "floor-seated studio pose, long limbs, clean backdrop",
            "white cyclorama hero stance, harness geometry clearly visible",
        ),
    ),
    PackDefinition(
        pack_id="D1",
        line_series="line_d_latex_premium",
        line_label="Line D - Latex / BDSM Premium",
        pack_label="Latex Editorial Baseline",
        tone="editorial",
        heat_level="maximal",
        creative_autonomy="hybrid",
        steps=35,
        cfg=5.6,
        scene_hook="Premium latex editorial built as a luxury material story.",
        camera_plan="High-contrast portrait and full-silhouette fashion angles.",
        pose_plan="Still, precise posture that lets the shine and shape read clearly.",
        environment="Luxury set, mirrored room, marble hallway, or spotlight stage.",
        device_focus="Glossy latex silhouette and clean fashion composition.",
        lighting_plan="Spotlight contrast, side reflections, and polished specular highlights.",
        material_focus="Glossy latex, chrome, marble, black lacquer, sculpted shine.",
        intensity_hook="Latex as premium material brand signal rather than only fetish cue.",
        concept_brief=(
            "Original adult latex fashion heroine, solo glossy latex editorial, luxury set, "
            "high contrast, sculpted shine."
        ),
        creative_brief=(
            "Keep this premium and expensive. The image should read as fashion-forward latex, not chaotic fetish clutter."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "glossy latex fashion",
            "high-contrast editorial",
            "spotlight",
            "luxury set",
            "clean composition",
            "sculpted silhouette",
            "polished shine",
            "premium fetish editorial",
        ),
        variants=(
            "spotlight stage portrait, glossy contours, black floor reflection",
            "mirrored cube room, side pose, latex shine emphasized",
            "marble hallway composition, slow stride, chrome accents",
            "neon strip room, architectural framing, precise silhouette",
            "clean black backdrop, statuesque pose, editorial contrast",
        ),
    ),
    PackDefinition(
        pack_id="D2",
        line_series="line_d_latex_premium",
        line_label="Line D - Latex / BDSM Premium",
        pack_label="Signature Masked Latex",
        tone="clinical",
        heat_level="maximal",
        creative_autonomy="hybrid",
        steps=35,
        cfg=5.8,
        scene_hook="Signature HollowForge lane with faceless elegance and lab-coded atmosphere.",
        camera_plan="Composed clinical framing with strong subject silhouette and clean set geometry.",
        pose_plan="Restrained stillness, statuesque alignment, and controlled presentation.",
        environment="Sterile chamber, observation corridor, bright white room, or glass bay.",
        device_focus="Full-cover latex mask, hood, and faceless character identity.",
        lighting_plan="Cold clinical light, glass reflections, and hard surface sheen.",
        material_focus="Black latex, sterile white surfaces, glass, polished metal.",
        intensity_hook="Keep it iconic and premium; the mask is the signature, not graphic action.",
        concept_brief=(
            "Original adult faceless latex heroine, solo full-cover latex mask, sterile chamber, "
            "lab-coded atmosphere, premium clinical styling."
        ),
        creative_brief=(
            "Push HollowForge signature cues while staying non-graphic. Prioritize iconic silhouette, composure, "
            "and clean lab architecture."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "full-cover latex mask",
            "latex hood",
            "sterile chamber",
            "faceless elegance",
            "lab-coded atmosphere",
            "reflective black surfaces",
            "architectural framing",
            "clinical luxury",
        ),
        variants=(
            "sterile white chamber, centered composition, statuesque pose",
            "observation glass corridor, side profile silhouette, cold highlights",
            "bright lab bay, seated stillness, polished black latex",
            "minimal restraint frame as set dressing, upright posture, clean geometry",
            "examination plinth room, overhead light pool, faceless heroine focus",
        ),
    ),
    PackDefinition(
        pack_id="D3",
        line_series="line_d_latex_premium",
        line_label="Line D - Latex / BDSM Premium",
        pack_label="Power Dynamic Premium",
        tone="clinical",
        heat_level="maximal",
        creative_autonomy="director",
        steps=35,
        cfg=5.8,
        scene_hook="Power-dynamic premium lane built from posture, lighting, and industrial staging.",
        camera_plan="Hero angles and side-lit medium shots that keep the scene elegant.",
        pose_plan="Submission-coded posture and controlled tension without explicit action.",
        environment="Industrial set, chain wall, steel doorway, catwalk, or leather bench stage.",
        device_focus="Latex harness and restraint-coded fashion details.",
        lighting_plan="Dramatic side light, sharp shadow, and industrial reflections.",
        material_focus="Latex harness, steel, leather, smoke haze, focused highlights.",
        intensity_hook="The lane should feel premium and intense, but still composed and non-graphic.",
        concept_brief=(
            "Original adult premium latex heroine, solo latex harness styling, industrial set, "
            "dramatic side light, submission-coded fashion posture."
        ),
        creative_brief=(
            "Keep the image intense but controlled. The power dynamic should be implied by pose and environment, "
            "not by explicit activity."
        ),
        base_tags=(
            "masterpiece",
            "best quality",
            "original character",
            "adult woman",
            "solo",
            "latex harness styling",
            "restraint aesthetic",
            "industrial set",
            "dramatic side light",
            "submission-coded posture",
            "precise styling",
            "premium tension",
            "dark luxury atmosphere",
        ),
        variants=(
            "chain wall backdrop, angled kneel-like fashion pose, sculpted side light",
            "industrial catwalk framing, lowered gaze, latex harness shine",
            "steel doorway composition, asymmetrical stance, hard rim light",
            "leather bench stage, deliberate posture, smoky depth",
            "gantry platform setup, floor reflections, tension-heavy silhouette",
        ),
    ),
)


def build_positive_prompt(pack: PackDefinition, variant: str) -> str:
    return ", ".join((*pack.base_tags, variant))


def build_csv_rows() -> list[list[object]]:
    rows: list[list[object]] = []
    set_no = 1
    for pack in PACKS:
        for variant in pack.variants:
            prompt = build_positive_prompt(pack, variant)
            for _ in range(REPEATS_PER_VARIANT):
                rows.append(
                    [
                        set_no,
                        PHASE1_CHECKPOINT,
                        "None",
                        0.0,
                        "None",
                        0.0,
                        "None",
                        0.0,
                        "None",
                        0.0,
                        SAMPLER,
                        pack.steps,
                        pack.cfg,
                        2,
                        f"{RESOLUTION[0]}x{RESOLUTION[1]}",
                        prompt,
                        DEFAULT_NEGATIVE_PROMPT,
                    ]
                )
                set_no += 1
    return rows


def build_queue_payload() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    direction_pack: list[dict[str, str]] = []
    set_no = 1
    for pack in PACKS:
        direction_pack.append(
            {
                "codename_stub": pack.pack_id.lower(),
                "series": pack.line_series,
                "scene_hook": pack.scene_hook,
                "camera_plan": pack.camera_plan,
                "pose_plan": pack.pose_plan,
                "environment": pack.environment,
                "device_focus": pack.device_focus,
                "lighting_plan": pack.lighting_plan,
                "material_focus": pack.material_focus,
                "intensity_hook": pack.intensity_hook,
            }
        )
        for variant_index, variant in enumerate(pack.variants, start=1):
            prompt = build_positive_prompt(pack, variant)
            for repeat_index in range(1, REPEATS_PER_VARIANT + 1):
                rows.append(
                    {
                        "set_no": set_no,
                        "codename": (
                            f"{pack.pack_id.lower()}_v{variant_index:02d}_r{repeat_index:02d}"
                        ),
                        "series": pack.line_series,
                        "checkpoint": PHASE1_CHECKPOINT,
                        "workflow_lane": WORKFLOW_LANE,
                        "loras": [],
                        "sampler": SAMPLER,
                        "steps": pack.steps,
                        "cfg": pack.cfg,
                        "clip_skip": 2,
                        "width": RESOLUTION[0],
                        "height": RESOLUTION[1],
                        "positive_prompt": prompt,
                        "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
                    }
                )
                set_no += 1

    return {
        "provider": "manual_preset",
        "model": "hollowforge_market_validation_phase1_20260313",
        "requested_count": len(rows),
        "generated_count": len(rows),
        "chunk_count": len(PACKS),
        "benchmark": {
            "favorites_total": 0,
            "workflow_lane": WORKFLOW_LANE,
            "prompt_dialect": "market_validation_phase1",
            "top_checkpoints": [PHASE1_CHECKPOINT],
            "top_loras": [],
            "avg_lora_strength": 0.0,
            "cfg_values": sorted({pack.cfg for pack in PACKS}),
            "steps_values": sorted({pack.steps for pack in PACKS}),
            "sampler": SAMPLER,
            "scheduler": SCHEDULER,
            "clip_skip": 2,
            "width": RESOLUTION[0],
            "height": RESOLUTION[1],
            "theme_keywords": [
                "original beauty",
                "editorial glamour",
                "alt goth",
                "non-ip cosplay-coded",
                "fetish-adjacent",
                "latex premium",
            ],
            "material_cues": [
                "silk",
                "sheer couture",
                "lace",
                "leather",
                "latex",
                "chrome",
            ],
            "control_cues": [
                "fashion tension",
                "power posture",
                "clinical framing",
                "faceless elegance",
            ],
            "camera_cues": [
                "close portrait",
                "three-quarter glamour",
                "hero angle",
                "doorway frame",
            ],
            "environment_cues": [
                "hotel suite",
                "club backroom",
                "neon lab",
                "library",
                "industrial set",
                "sterile chamber",
            ],
            "exposure_cues": [
                "tasteful sensuality",
                "beauty-first",
                "premium tension",
                "non-graphic adult glamour",
            ],
            "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
        },
        "direction_pack": direction_pack,
        "rows": rows,
    }


def build_request_presets() -> dict[str, object]:
    phase1_requests: list[dict[str, object]] = []
    for pack in PACKS:
        phase1_requests.append(
            {
                "pack_id": pack.pack_id,
                "line_series": pack.line_series,
                "pack_label": pack.pack_label,
                "generate_request": {
                    "concept_brief": pack.concept_brief,
                    "creative_brief": pack.creative_brief,
                    "count": 25,
                    "chunk_size": 25,
                    "workflow_lane": WORKFLOW_LANE,
                    "provider": "default",
                    "model": None,
                    "tone": pack.tone,
                    "heat_level": pack.heat_level,
                    "creative_autonomy": pack.creative_autonomy,
                    "direction_pass_enabled": True,
                    "target_lora_count": 1,
                    "checkpoint_pool_size": 1,
                    "include_negative_prompt": True,
                    "dedupe": True,
                    "forbidden_elements": [
                        "recognizable franchise character",
                        "logo",
                        "watermark",
                        "underage coding",
                    ],
                    "expansion_axes": [
                        "camera distance",
                        "lighting mood",
                        "material emphasis",
                        "location",
                        "pose tension",
                    ],
                    "direction_pack_override": [
                        {
                            "codename_stub": pack.pack_id.lower(),
                            "series": pack.line_series,
                            "scene_hook": pack.scene_hook,
                            "camera_plan": pack.camera_plan,
                            "pose_plan": pack.pose_plan,
                            "environment": pack.environment,
                            "device_focus": pack.device_focus,
                            "lighting_plan": pack.lighting_plan,
                            "material_focus": pack.material_focus,
                            "intensity_hook": pack.intensity_hook,
                        }
                    ],
                },
            }
        )

    return {
        "generated_on": "2026-03-13",
        "notes": [
            "Phase 1 direct queue artifact is the canonical ready-to-run file.",
            "Prompt Factory generate requests below are operator presets and may still reflect benchmark/checkpoint bias unless checkpoint preferences are pinned first.",
            "Phase 2 should duplicate the winning 25-row block twice and swap checkpoints to waiIllustriousSDXL_v160.safetensors and animayhemPaleRider_v2TrueGrit.safetensors.",
            "Phase 3 should duplicate the final two winning 25-row blocks three times each for character lock, environment drift, and intensity ladder variants.",
        ],
        "phase_1_generate_requests": phase1_requests,
        "phase_2_checkpoint_swap_template": {
            "checkpoint_a": "waiIllustriousSDXL_v160.safetensors",
            "checkpoint_b": "animayhemPaleRider_v2TrueGrit.safetensors",
            "copies_per_winner": 2,
            "expected_rows_per_winner": 50,
        },
        "phase_3_series_template": {
            "copies_per_winner": 3,
            "tracks": [
                "character_lock",
                "environment_drift",
                "intensity_ladder",
            ],
            "expected_rows_per_winner": 75,
        },
    }


def build_runbook() -> str:
    lines = [
        "# HollowForge Market Validation Preset Runbook",
        "",
        "작성일: 2026-03-13",
        "대상: HollowForge Prompt Factory / Batch Import",
        "",
        "관련 파일:",
        "- `HOLLOWFORGE_MARKET_VALIDATION_PHASE1_DIRECT_IMPORT_20260313.csv`",
        "- `HOLLOWFORGE_MARKET_VALIDATION_PHASE1_QUEUE_PAYLOAD_20260313.json`",
        "- `HOLLOWFORGE_MARKET_VALIDATION_REQUEST_PRESETS_20260313.json`",
        "- `HOLLOWFORGE_MARKET_VALIDATION_MATRIX_20260313.md`",
        "",
        "## 0. 목적",
        "",
        "- Phase 1 시장 검증을 실제 발주 가능한 형태로 고정한다.",
        "- `1 batch = 25 images` 원칙을 유지한다.",
        "- 이번 산출물은 `12 packs x 25 images = 300 images`를 바로 만들 수 있다.",
        "",
        "## 1. 어떤 파일을 언제 쓰는가",
        "",
        "### CSV",
        "",
        "- 용도: Batch Import 페이지에 바로 붙여 넣거나 업로드할 때",
        "- 특징: `300 rows`, 각 행이 `1 generation`",
        "- 구조: `12 packs x 5 prompt variants x 5 random-seed repeats`",
        "",
        "### Queue Payload JSON",
        "",
        "- 용도: `/api/tools/prompt-factory/queue` 또는 `/api/v1/tools/prompt-factory/queue`에 바로 POST할 때",
        "- 특징: Prompt Factory 응답 스키마에 맞춰서 바로 큐에 넣을 수 있다.",
        "",
        "### Request Presets JSON",
        "",
        "- 용도: Prompt Factory Generate UI/API에서 pack별 preset을 불러 수동 검토 후 생성할 때",
        "- 특징: direct queue보다 덜 고정적이지만, pack별 creative brief를 유지하기 쉽다.",
        "",
        "## 2. Pack 범위",
        "",
        "| Pack | Row Range | Images | Line |",
        "|---|---:|---:|---|",
    ]

    start = 1
    for pack in PACKS:
        end = start + (len(pack.variants) * REPEATS_PER_VARIANT) - 1
        lines.append(
            f"| {pack.pack_id} | {start}-{end} | 25 | {pack.line_label} / {pack.pack_label} |"
        )
        start = end + 1

    lines.extend(
        [
            "",
            "## 3. 권장 사용 순서",
            "",
            "1. CSV 또는 queue payload로 Phase 1 300장을 한 번에 발주한다.",
            "2. Pack별로 `favorite_rate`, `strong_pick_rate`, `character_seed_rate`를 기록한다.",
            "3. 상위 4 packs만 남겨서 Phase 2로 넘긴다.",
            "4. Phase 2에서는 각 winning pack의 25-row 블록을 두 번 복제하고 checkpoint만 교체한다.",
            "5. Phase 3에서는 최종 2 packs만 남기고 `character_lock`, `environment_drift`, `intensity_ladder` 세 트랙으로 복제한다.",
            "",
            "## 4. CSV 사용",
            "",
            "Batch Import 페이지 헤더는 아래 형식을 기대한다.",
            "",
            "```text",
            "Set_No|Checkpoint|LoRA_1|Strength_1|LoRA_2|Strength_2|LoRA_3|Strength_3|LoRA_4|Strength_4|Sampler|Steps|CFG|Clip_Skip|Resolution|Positive_Prompt|Negative_Prompt",
            "```",
            "",
            "이번 CSV는 LoRA를 비워 둔 baseline 버전이다. 콘텐츠 축 반응을 먼저 보고, 이후 winning lane에만 LoRA를 얹는 것이 맞다.",
            "",
            "## 5. JSON Queue 사용",
            "",
            "예시:",
            "",
            "```bash",
            "curl -X POST http://127.0.0.1:8000/api/tools/prompt-factory/queue \\",
            "  -H 'Content-Type: application/json' \\",
            "  --data @docs/HOLLOWFORGE_MARKET_VALIDATION_PHASE1_QUEUE_PAYLOAD_20260313.json",
            "```",
            "",
            "## 6. 운영 메모",
            "",
            "- 이번 버전은 `prefectIllustriousXL_v70.safetensors` 고정 baseline이다.",
            "- negative prompt는 현재 HollowForge 기본값과 동일하다.",
            "- `adult woman`, `original character`, `non-IP` 축을 유지하도록 직접 작성했다.",
            "- `latex / bdsm`는 Phase 1 안에서 `Line D`로 검증하되, 코어 전체를 그 방향으로 몰지 않는다.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter="|")
        writer.writerow(
            [
                "Set_No",
                "Checkpoint",
                "LoRA_1",
                "Strength_1",
                "LoRA_2",
                "Strength_2",
                "LoRA_3",
                "Strength_3",
                "LoRA_4",
                "Strength_4",
                "Sampler",
                "Steps",
                "CFG",
                "Clip_Skip",
                "Resolution",
                "Positive_Prompt",
                "Negative_Prompt",
            ]
        )
        writer.writerows(rows)


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    csv_rows = build_csv_rows()
    queue_payload = build_queue_payload()
    request_presets = build_request_presets()

    write_csv(
        DOCS_DIR / "HOLLOWFORGE_MARKET_VALIDATION_PHASE1_DIRECT_IMPORT_20260313.csv",
        csv_rows,
    )
    (
        DOCS_DIR / "HOLLOWFORGE_MARKET_VALIDATION_PHASE1_QUEUE_PAYLOAD_20260313.json"
    ).write_text(json.dumps(queue_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (
        DOCS_DIR / "HOLLOWFORGE_MARKET_VALIDATION_REQUEST_PRESETS_20260313.json"
    ).write_text(json.dumps(request_presets, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (
        DOCS_DIR / "HOLLOWFORGE_MARKET_VALIDATION_PRESET_RUNBOOK_20260313.md"
    ).write_text(build_runbook(), encoding="utf-8")

    print("Wrote market validation artifacts:")
    print("- HOLLOWFORGE_MARKET_VALIDATION_PHASE1_DIRECT_IMPORT_20260313.csv")
    print("- HOLLOWFORGE_MARKET_VALIDATION_PHASE1_QUEUE_PAYLOAD_20260313.json")
    print("- HOLLOWFORGE_MARKET_VALIDATION_REQUEST_PRESETS_20260313.json")
    print("- HOLLOWFORGE_MARKET_VALIDATION_PRESET_RUNBOOK_20260313.md")
    print(f"Phase 1 rows: {len(csv_rows)}")


if __name__ == "__main__":
    main()

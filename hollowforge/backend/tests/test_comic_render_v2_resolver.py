from __future__ import annotations

from types import MappingProxyType

import pytest

from app.services.comic_render_profiles import ComicPanelRenderProfile
from app.services.comic_render_v2_resolver import (
    _BINDING_EXECUTION_REGISTRY,
    _STYLE_EXECUTION_REGISTRY,
    resolve_comic_render_v2_contract,
)
import app.services.series_style_canon_registry as series_style_canon_registry
from app.services.series_style_canon_registry import get_series_style_canon


def _make_role_profile() -> ComicPanelRenderProfile:
    return ComicPanelRenderProfile(
        profile_id="beat_dialogue_v1",
        panel_types=("beat",),
        lora_mode="inherit_all",
        width=960,
        height=1216,
        negative_prompt_append="plastic skin, waxy face, dead eyes",
        anchor_filter_mode="drop_face_gloss_bias",
        prompt_order_mode="default_subject_first",
        subject_prominence_mode="default",
        scene_cue_mode="none",
    )


def _make_insert_role_profile() -> ComicPanelRenderProfile:
    return ComicPanelRenderProfile(
        profile_id="insert_detail_v1",
        panel_types=("insert",),
        lora_mode="inherit_all",
        width=960,
        height=1216,
        negative_prompt_append="plastic skin, waxy face, dead eyes",
        anchor_filter_mode="drop_face_gloss_bias",
        prompt_order_mode="default_subject_first",
        subject_prominence_mode="default",
        scene_cue_mode="none",
    )


def _make_closeup_role_profile() -> ComicPanelRenderProfile:
    return ComicPanelRenderProfile(
        profile_id="closeup_detail_v1",
        panel_types=("closeup",),
        lora_mode="inherit_all",
        width=960,
        height=1216,
        negative_prompt_append="plastic skin, waxy face, dead eyes",
        anchor_filter_mode="drop_face_gloss_bias",
        prompt_order_mode="default_subject_first",
        subject_prominence_mode="default",
        scene_cue_mode="none",
    )


def _make_establish_role_profile() -> ComicPanelRenderProfile:
    return ComicPanelRenderProfile(
        profile_id="establish_static_v1",
        panel_types=("establish",),
        lora_mode="inherit_all",
        width=1216,
        height=960,
        negative_prompt_append="plastic skin, waxy face, dead eyes",
        anchor_filter_mode="drop_face_gloss_bias",
        prompt_order_mode="default_subject_first",
        subject_prominence_mode="default",
        scene_cue_mode="none",
    )


def test_resolve_comic_render_v2_contract_materializes_required_sections() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="beat",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_role_profile(),
    )

    assert tuple(contract.model_dump().keys()) == (
        "identity_block",
        "style_block",
        "binding_block",
        "role_block",
        "execution_params",
        "negative_rules",
    )


def test_resolve_comic_render_v2_contract_uses_establish_style_override() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="establish",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_establish_role_profile(),
    )

    assert contract.execution_params["checkpoint"] == "akiumLumenILLBase_baseV2.safetensors"
    assert contract.execution_params["loras"] == ()


def test_camila_v2_establish_uses_reference_guided_execution_lane() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="establish",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_establish_role_profile(),
    )

    assert contract.execution_params["checkpoint"] == "akiumLumenILLBase_baseV2.safetensors"
    assert contract.execution_params["loras"] == ()
    assert contract.execution_params["still_backend_family"] == "sdxl_ipadapter_still"
    assert contract.execution_params["reference_guided"] is True


def test_camila_v2_establish_rolls_back_to_bounded_text_only_execution_lane() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="establish",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_establish_role_profile(),
    )

    assert contract.execution_params["checkpoint"] == "akiumLumenILLBase_baseV2.safetensors"
    assert contract.execution_params["loras"] == ()
    assert contract.execution_params.get("reference_guided") is not True
    assert "still_backend_family" not in contract.execution_params


def test_series_style_canon_exposes_role_override() -> None:
    pilot = get_series_style_canon(series_style_id="camila_pilot_v1")
    motion_test = get_series_style_canon(series_style_id="camila_motion_test_v1")

    assert pilot.role_execution_overrides == {
        "establish": {
            "checkpoint": "akiumLumenILLBase_baseV2.safetensors",
            "loras": (),
            "reference_guided": True,
            "still_backend_family": "sdxl_ipadapter_still",
        }
    }
    assert motion_test.role_execution_overrides == {}


def test_series_style_canon_establish_override_is_text_only() -> None:
    pilot = get_series_style_canon(series_style_id="camila_pilot_v1")

    assert pilot.role_execution_overrides == {
        "establish": {
            "checkpoint": "akiumLumenILLBase_baseV2.safetensors",
            "loras": (),
        }
    }


def test_resolve_comic_render_v2_contract_keeps_base_stack_for_beat() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="beat",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_role_profile(),
    )

    assert contract.execution_params["checkpoint"] == "prefectIllustriousXL_v70.safetensors"
    assert contract.execution_params["loras"] == (
        {"filename": "DetailedEyes_V3.safetensors", "strength": 0.45},
        {"filename": "Face_Enhancer_Illustrious.safetensors", "strength": 0.36},
    )
    assert contract.execution_params.get("reference_guided") is not True
    assert "still_backend_family" not in contract.execution_params


def test_resolve_comic_render_v2_contract_keeps_existing_lane_for_insert() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="insert",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_insert_role_profile(),
    )

    assert contract.execution_params["checkpoint"] == "prefectIllustriousXL_v70.safetensors"
    assert contract.execution_params["loras"] == (
        {"filename": "DetailedEyes_V3.safetensors", "strength": 0.45},
        {"filename": "Face_Enhancer_Illustrious.safetensors", "strength": 0.36},
    )
    assert contract.execution_params.get("reference_guided") is not True
    assert "still_backend_family" not in contract.execution_params


def test_resolve_comic_render_v2_contract_keeps_existing_lane_for_closeup() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="closeup",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_closeup_role_profile(),
    )

    assert contract.execution_params["checkpoint"] == "prefectIllustriousXL_v70.safetensors"
    assert contract.execution_params["loras"] == (
        {"filename": "DetailedEyes_V3.safetensors", "strength": 0.45},
        {"filename": "Face_Enhancer_Illustrious.safetensors", "strength": 0.36},
    )
    assert contract.execution_params.get("reference_guided") is not True
    assert "still_backend_family" not in contract.execution_params


def test_resolve_comic_render_v2_contract_does_not_over_route_without_explicit_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        series_style_canon_registry._SERIES_STYLE_CANON_REGISTRY,
        "camila_pilot_v1",
        series_style_canon_registry.SeriesStyleCanonEntry(
            id="camila_pilot_v1",
            display_name="Camila Pilot V1",
            teaser_motion_policy="static_hero",
            line_policy=(
                "Keep linework clean, controlled, and panel-readable without heavy "
                "finish loss."
            ),
            shading_policy=(
                "Use restrained shading that supports volume while avoiding muddy contrast."
            ),
            surface_texture_policy=(
                "Render surfaces with enough texture to stay natural without adding noise."
            ),
            panel_readability_policy=(
                "Prioritize clear subject separation and readable forms in still frames."
            ),
            appeal_policy=(
                "Preserve attractive adult facial clarity, healthy warmth, and natural "
                "presence without glamour gloss, teen-coded exaggeration, or plastic skin."
            ),
            artifact_avoidance_policy=(
                "Avoid blur, melt, warped anatomy, over-smoothing, random unreadable text, "
                "subtitle overlays, logo or watermark marks, camera UI, viewfinder frames, "
                "screenshot borders, and other generation artifacts."
            ),
            hand_face_reliability_policy=(
                "Preserve hands and faces with extra care because they are the highest "
                "risk regions for still quality."
            ),
            notes=(
                "Pilot series style canon for the Camila-only V2 pilot, aligned to "
                "the installed favorite-quality stack rather than an unshipped custom LoRA."
            ),
            role_execution_overrides={
                "establish": {
                    "checkpoint": "akiumLumenILLBase_baseV2.safetensors",
                    "loras": (),
                }
            },
        ),
    )

    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="establish",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_establish_role_profile(),
    )

    assert contract.execution_params["checkpoint"] == "akiumLumenILLBase_baseV2.safetensors"
    assert contract.execution_params["loras"] == ()
    assert contract.execution_params.get("reference_guided") is not True
    assert "still_backend_family" not in contract.execution_params


def test_resolve_comic_render_v2_contract_rejects_malformed_reference_guided_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        series_style_canon_registry._SERIES_STYLE_CANON_REGISTRY,
        "camila_pilot_v1",
        series_style_canon_registry.SeriesStyleCanonEntry(
            id="camila_pilot_v1",
            display_name="Camila Pilot V1",
            teaser_motion_policy="static_hero",
            line_policy=(
                "Keep linework clean, controlled, and panel-readable without heavy "
                "finish loss."
            ),
            shading_policy=(
                "Use restrained shading that supports volume while avoiding muddy contrast."
            ),
            surface_texture_policy=(
                "Render surfaces with enough texture to stay natural without adding noise."
            ),
            panel_readability_policy=(
                "Prioritize clear subject separation and readable forms in still frames."
            ),
            appeal_policy=(
                "Preserve attractive adult facial clarity, healthy warmth, and natural "
                "presence without glamour gloss, teen-coded exaggeration, or plastic skin."
            ),
            artifact_avoidance_policy=(
                "Avoid blur, melt, warped anatomy, over-smoothing, random unreadable text, "
                "subtitle overlays, logo or watermark marks, camera UI, viewfinder frames, "
                "screenshot borders, and other generation artifacts."
            ),
            hand_face_reliability_policy=(
                "Preserve hands and faces with extra care because they are the highest "
                "risk regions for still quality."
            ),
            notes=(
                "Pilot series style canon for the Camila-only V2 pilot, aligned to "
                "the installed favorite-quality stack rather than an unshipped custom LoRA."
            ),
            role_execution_overrides={
                "establish": {
                    "checkpoint": "akiumLumenILLBase_baseV2.safetensors",
                    "loras": (),
                    "reference_guided": True,
                    "still_backend_family": "",
                }
            },
        ),
    )

    with pytest.raises(ValueError, match="still_backend_family"):
        resolve_comic_render_v2_contract(
            character_id="camila_v2",
            series_style_id="camila_pilot_v1",
            binding_id="camila_pilot_binding_v1",
            panel_type="establish",
            location_label=None,
            continuity_notes=None,
            role_profile=_make_establish_role_profile(),
        )


def test_resolve_comic_render_v2_contract_materializes_richer_quality_contract() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="beat",
        location_label="artist loft morning",
        continuity_notes="Carry over the wet brush on the easel from prior panel.",
        role_profile=_make_role_profile(),
    )

    assert contract.role_block == (
        "Panel type: beat",
        "Role profile: beat_dialogue_v1",
    )
    assert contract.identity_block == (
        "Camila Duarte, adult Brazilian woman with warm sun-kissed tan skin, long chestnut-brown wavy hair, and a naturally elegant grounded presence",
        "Graceful adult face structure with calm cheekbone and jawline balance, stable recognition, and no youthful simplification.",
        "Warm hazel eyes with steady directness, calm confidence, and adult warmth.",
        "Long chestnut-brown waves with warm highlights; never orange, blonde, or school-idol styled.",
        "Preserve a natural lightly tanned skin surface with warm undertone, light texture, healthy warmth, and no oversmoothing.",
        "Adult grounded build with believable feminine presence, balanced posture, healthy proportions, and no youth-coded silhouette.",
        "Calm, observant, and direct with small controlled shifts in emotion.",
        "Composed mature beauty, approachable warmth, and quietly magnetic adult presence; attractive without glamour posing or teen-coded stylization.",
        (
            "Simple studio-casual wardrobe such as soft knits, open-collar shirts, "
            "or adult loungewear that flatters an adult silhouette without turning "
            "her into a fashion portrait."
        ),
        (
            "Measured, observant, and direct; she reads as self-possessed, mature, "
            "grounded, and quietly alluring through confidence rather than performance."
        ),
        (
            "Chestnut-brown hair with warm highlights, lightly tanned skin, and a "
            "mature calm presence with natural elegance. Reject school-uniform and "
            "youth-coded drift."
        ),
    )
    assert contract.style_block == (
        "Series style: Camila Pilot V1",
        "Keep linework clean, controlled, and panel-readable without heavy finish loss.",
        "Use restrained shading that supports volume while avoiding muddy contrast.",
        "Render surfaces with enough texture to stay natural without adding noise.",
        "Prioritize clear subject separation and readable forms in still frames.",
        "Preserve attractive adult facial clarity, healthy warmth, and natural presence without glamour gloss, teen-coded exaggeration, or plastic skin.",
        "Avoid blur, melt, warped anatomy, over-smoothing, random unreadable text, subtitle overlays, logo or watermark marks, camera UI, viewfinder frames, screenshot borders, and other generation artifacts.",
        "Preserve hands and faces with extra care because they are the highest risk regions for still quality.",
        (
            "Style notes: Pilot series style canon for the Camila-only V2 pilot, "
            "aligned to the installed favorite-quality stack rather than an "
            "unshipped custom LoRA."
        ),
    )
    assert contract.binding_block == (
        "Binding notes: Camila-only pilot binding for the V2 registry pilot.",
        "Keep Camila appealing in an adult, grounded way: calm eyes, healthy warm skin, graceful posture, and natural charm without glamour posing.",
        "Wardrobe family: simple functional everyday wardrobe",
        "Location: artist loft morning",
        "Continuity: Carry over the wet brush on the easel from prior panel.",
    )
    assert contract.execution_params["positive_merge_sequence"] == (
        "role",
        "identity",
        "style",
        "binding",
        "continuity_location",
    )
    assert contract.execution_params["negative_merge_sequence"] == (
        "style_artifacts",
        "identity_drift",
        "binding_drift",
        "role_quality",
    )
    assert contract.negative_rules == (
        "Avoid blur, melt, warped anatomy, over-smoothing, random unreadable text, subtitle overlays, logo or watermark marks, camera UI, viewfinder frames, screenshot borders, and other generation artifacts.",
        "No glamour styling, no editorial beauty language, no resort presentation, no model-pose drift, no school-uniform cues, no necktie, no orange hair, no youth-coded anime heroine drift.",
        (
            "Keep Camila anchored in a calm, grounded, adult non-glamour identity. "
            "Avoid drifting into editorial beauty framing, school-uniform styling, "
            "or youthful heroine shortcuts."
        ),
        "No wardrobe drift, no glamour drift, no editorial styling drift, no camera-frame drift, no UI overlay drift, no random text drift, no school uniform, no necktie, no blazer-and-tie school look.",
        "Role negative: plastic skin, waxy face, dead eyes",
    )


def test_resolve_comic_render_v2_contract_applies_execution_precedence() -> None:
    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="beat",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_role_profile(),
    )

    assert contract.execution_params["checkpoint"] == "prefectIllustriousXL_v70.safetensors"
    assert contract.execution_params["loras"] == (
        {"filename": "DetailedEyes_V3.safetensors", "strength": 0.45},
        {"filename": "Face_Enhancer_Illustrious.safetensors", "strength": 0.36},
    )
    assert contract.execution_params["steps"] == 30
    assert contract.execution_params["cfg"] == 5.4
    assert contract.execution_params["sampler"] == "euler_a"
    assert contract.execution_params["identity_lock_strength"] == 0.92
    assert contract.execution_params["style_lock_strength"] == 0.88
    assert contract.execution_params["width"] == 960
    assert contract.execution_params["height"] == 1216
    assert contract.execution_params["framing_profile"] == "beat_dialogue_v1"


def test_resolve_comic_render_v2_contract_execution_precedence_with_overlapping_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        _STYLE_EXECUTION_REGISTRY,
        "camila_pilot_v1",
        {
            "checkpoint": "custom_checkpoint.safetensors",
            "loras": (
                {"filename": "style_lora.safetensors", "strength": 0.11},
            ),
            "steps": 99,
            "cfg": 6.8,
            "sampler": "ddim",
            "identity_lock_strength": 0.31,
            "style_lock_strength": 0.33,
            "width": 640,
            "height": 640,
            "framing_profile": "style_frame",
            "style_artifact_negative": "Avoid style artifacts: test style value.",
        },
    )
    monkeypatch.setitem(
        _BINDING_EXECUTION_REGISTRY,
        "camila_pilot_binding_v1",
        {
            "identity_lock_strength": 0.92,
            "style_lock_strength": 0.88,
            "width": 1024,
            "height": 1024,
            "framing_profile": "binding_frame",
        },
    )

    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="beat",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_role_profile(),
    )

    # style values stay for style-owned knobs
    assert contract.execution_params["checkpoint"] == "custom_checkpoint.safetensors"
    assert contract.execution_params["loras"] == (
        {"filename": "style_lora.safetensors", "strength": 0.11},
    )
    assert contract.execution_params["steps"] == 99
    assert contract.execution_params["cfg"] == 6.8
    assert contract.execution_params["sampler"] == "ddim"
    # binding overrides style on lock strengths
    assert contract.execution_params["identity_lock_strength"] == 0.92
    assert contract.execution_params["style_lock_strength"] == 0.88
    # role profile still overrides for role-owned framing dimensions
    assert contract.execution_params["width"] == 960
    assert contract.execution_params["height"] == 1216
    assert contract.execution_params["framing_profile"] == "beat_dialogue_v1"


def test_resolve_comic_render_v2_contract_rejects_panel_type_not_in_role_profile() -> None:
    with pytest.raises(ValueError, match="panel_type"):
        resolve_comic_render_v2_contract(
            character_id="camila_v2",
            series_style_id="camila_pilot_v1",
            binding_id="camila_pilot_binding_v1",
            panel_type="action",
            location_label=None,
            continuity_notes=None,
            role_profile=_make_role_profile(),
        )


def test_resolve_comic_render_v2_contract_fails_without_style_execution_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(_STYLE_EXECUTION_REGISTRY, "camila_pilot_v1", raising=False)

    with pytest.raises(ValueError, match="execution template"):
        resolve_comic_render_v2_contract(
            character_id="camila_v2",
            series_style_id="camila_pilot_v1",
            binding_id="camila_pilot_binding_v1",
            panel_type="beat",
            location_label=None,
            continuity_notes=None,
            role_profile=_make_role_profile(),
        )


def test_resolve_comic_render_v2_contract_execution_params_are_deep_immutable_and_copied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    style_payload = {
        "checkpoint": "immutable_test.safetensors",
        "loras": [
            {"filename": "lora_a.safetensors", "strength": 0.5},
        ],
        "steps": 30,
        "cfg": 5.4,
        "sampler": "euler_a",
        "style_artifact_negative": "Avoid style artifacts: immutable test.",
    }
    monkeypatch.setitem(_STYLE_EXECUTION_REGISTRY, "camila_pilot_v1", style_payload)

    contract = resolve_comic_render_v2_contract(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        binding_id="camila_pilot_binding_v1",
        panel_type="beat",
        location_label=None,
        continuity_notes=None,
        role_profile=_make_role_profile(),
    )

    assert isinstance(contract.execution_params, MappingProxyType)
    assert isinstance(contract.execution_params["loras"][0], MappingProxyType)

    style_payload["loras"][0]["strength"] = 0.9
    style_payload["checkpoint"] = "changed.safetensors"
    assert contract.execution_params["loras"][0]["strength"] == 0.5
    assert contract.execution_params["checkpoint"] == "immutable_test.safetensors"

    with pytest.raises(TypeError):
        contract.execution_params["cfg"] = 7.0
    with pytest.raises(TypeError):
        contract.execution_params["loras"][0]["strength"] = 0.7

from __future__ import annotations

from app.services.comic_render_profiles import ComicPanelRenderProfile
from app.services.comic_render_v2_resolver import resolve_comic_render_v2_contract


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


def test_resolve_comic_render_v2_contract_keeps_positive_and_negative_order_stable() -> None:
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
        "Camila, poised adult woman with a practical, grounded presence",
        (
            "Simple, functional wardrobe choices that support the scene without "
            "turning her into a fashion portrait."
        ),
        (
            "Measured, observant, and direct; she reads as self-possessed rather "
            "than performatively styled."
        ),
    )
    assert contract.style_block == (
        "Series style: Camila Pilot V1",
        "Style notes: Pilot series style canon for the Camila-only V2 pilot.",
    )
    assert contract.binding_block == (
        "Binding notes: Camila-only pilot binding for the V2 registry pilot.",
        "Location: artist loft morning",
        "Continuity: Carry over the wet brush on the easel from prior panel.",
    )
    assert contract.negative_rules == (
        "Avoid style artifacts: over-sharpened outlines, posterized gradients, muddy midtones.",
        (
            "Keep Camila anchored in a calm, grounded, non-glamour identity. "
            "Avoid drifting into editorial beauty framing."
        ),
        "Binding negative: do not swap character identity or style assignment outside this binding.",
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

    assert contract.execution_params["checkpoint"] == "waiIllustriousSDXL_v160.safetensors"
    assert contract.execution_params["loras"] == (
        {"filename": "camila_pilot_line_treatment_v1.safetensors", "strength": 0.65},
    )
    assert contract.execution_params["steps"] == 30
    assert contract.execution_params["cfg"] == 5.4
    assert contract.execution_params["sampler"] == "euler_a"
    assert contract.execution_params["identity_lock_strength"] == 0.92
    assert contract.execution_params["style_lock_strength"] == 0.88
    assert contract.execution_params["width"] == 960
    assert contract.execution_params["height"] == 1216
    assert contract.execution_params["framing_profile"] == "beat_dialogue_v1"

"""Registry for pilot series style canon entries."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SeriesStyleCanonEntry(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    teaser_motion_policy: str = Field(min_length=1, max_length=120)
    line_policy: str = Field(min_length=1, max_length=1000)
    shading_policy: str = Field(min_length=1, max_length=1000)
    surface_texture_policy: str = Field(min_length=1, max_length=1000)
    panel_readability_policy: str = Field(min_length=1, max_length=1000)
    artifact_avoidance_policy: str = Field(min_length=1, max_length=1000)
    hand_face_reliability_policy: str = Field(min_length=1, max_length=1000)
    notes: str = Field(min_length=1, max_length=1000)


_SERIES_STYLE_CANON_REGISTRY: dict[str, SeriesStyleCanonEntry] = {
    "camila_pilot_v1": SeriesStyleCanonEntry(
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
        artifact_avoidance_policy=(
            "Avoid blur, melt, warped anatomy, over-smoothing, and other generation "
            "artifacts."
        ),
        hand_face_reliability_policy=(
            "Preserve hands and faces with extra care because they are the highest "
            "risk regions for still quality."
        ),
        notes="Pilot series style canon for the Camila-only V2 pilot.",
    ),
    "camila_motion_test_v1": SeriesStyleCanonEntry(
        id="camila_motion_test_v1",
        display_name="Camila Motion Test V1",
        teaser_motion_policy="subtle_loop",
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
        artifact_avoidance_policy=(
            "Avoid blur, melt, warped anatomy, over-smoothing, and other generation "
            "artifacts."
        ),
        hand_face_reliability_policy=(
            "Preserve hands and faces with extra care because they are the highest "
            "risk regions for still quality."
        ),
        notes=(
            "Test-only alternate style used to validate teaser motion policy "
            "variance."
        ),
    ),
}


def get_series_style_canon(series_style_id: str) -> SeriesStyleCanonEntry:
    entry = _SERIES_STYLE_CANON_REGISTRY.get(series_style_id)
    if entry is None:
        raise ValueError(f"Unknown series style canon: {series_style_id}")
    return entry.model_copy(deep=True)

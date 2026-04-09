"""Registry for pilot series style canon entries."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SeriesStyleCanonEntry(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    teaser_motion_policy: str = Field(min_length=1, max_length=120)
    notes: str = Field(min_length=1, max_length=1000)


_SERIES_STYLE_CANON_REGISTRY: dict[str, SeriesStyleCanonEntry] = {
    "camila_pilot_v1": SeriesStyleCanonEntry(
        id="camila_pilot_v1",
        display_name="Camila Pilot V1",
        teaser_motion_policy="static_hero",
        notes="Pilot series style canon for the Camila-only V2 pilot.",
    ),
    "camila_motion_test_v1": SeriesStyleCanonEntry(
        id="camila_motion_test_v1",
        display_name="Camila Motion Test V1",
        teaser_motion_policy="subtle_loop",
        notes=(
            "Test-only alternate style used to validate teaser motion policy "
            "variance."
        ),
    ),
}


def get_series_style_canon(series_style_canon_id: str) -> SeriesStyleCanonEntry:
    entry = _SERIES_STYLE_CANON_REGISTRY.get(series_style_canon_id)
    if entry is None:
        raise ValueError(f"Unknown series style canon: {series_style_canon_id}")
    return entry.model_copy(deep=True)

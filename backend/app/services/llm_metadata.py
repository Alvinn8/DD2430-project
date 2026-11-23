from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Literal, Optional

import google.genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings

log = logging.getLogger(__name__)

MAX_HEADER_CHARS = 8000

PROMPT = """You read the header of a DSC (differential scanning calorimetry) export file.
Copy values that are explicitly written in the header. Never guess, never infer from
typical values, never calculate. If a value is not written, return null.

Rules:
- endothermic_direction: only if the header says which way endothermic peaks point
  ("endo up", "exo down", "endothermic peaks point down"). "exo up" means endotherm "down".
- Keep the units exactly as written (mass: mg, g or ug; heating rate: C/min, K/min, K/s).
- sample_mass is the sample weight, not the pan weight.

Header:
---
{header}
---"""


class LLMHeaderFields(BaseModel):
    sample_name: Optional[str] = None
    sample_mass_value: Optional[Decimal] = None
    sample_mass_unit: Optional[Literal["mg", "g", "ug"]] = None
    heating_rate_value: Optional[Decimal] = None
    heating_rate_unit: Optional[Literal["C/min", "K/min", "K/s", "C/s"]] = None
    endothermic_direction: Optional[Literal["up", "down"]] = None
    crucible_type: Optional[str] = None
    purge_gas: Optional[str] = None


def _blank(header_text: str) -> bool:
    return len(header_text.strip()) < 20


def _call_model(header_text: str) -> LLMHeaderFields:
    client = google.genai.Client(
        vertexai=True, project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION
    )
    response = client.models.generate_content(
        model=settings.DEFAULT_MODEL,
        contents=PROMPT.format(header=header_text[:MAX_HEADER_CHARS]),
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=LLMHeaderFields,
        ),
    )
    if response is None or not response.text:
        raise RuntimeError("LLM returned no response")
    return LLMHeaderFields.model_validate_json(response.text)


async def extract_missing_with_llm(header_text: str, missing: list[str]) -> dict:
    """Return values for fields in ``missing`` only, or {} when nothing can be found.

    ``missing`` uses the names from ``run_params.CRITICAL_FIELDS`` (sample_mass,
    heating_rate, endothermic_direction). A failure never blocks ingestion.
    """
    if not missing or _blank(header_text):
        return {}
    try:
        fields = await asyncio.to_thread(_call_model, header_text)
    except Exception:  # model or network failure: fall back to asking the user
        log.exception("LLM header extraction failed")
        return {}

    wanted = {
        "sample_mass": ("sample_mass_value", "sample_mass_unit"),
        "heating_rate": ("heating_rate_value", "heating_rate_unit"),
        "endothermic_direction": ("endothermic_direction",),
    }
    result: dict = {}
    for name in missing:
        for key in wanted.get(name, ()):
            value = getattr(fields, key)
            if value is not None:
                result[key] = value

    for key in ("sample_mass_value", "heating_rate_value"):
        value = result.get(key)
        if value is not None and value <= 0:
            del result[key]

    # a value without its unit is not usable: unit and value stand or fall together
    for value_key, unit_key in (
        ("sample_mass_value", "sample_mass_unit"),
        ("heating_rate_value", "heating_rate_unit"),
    ):
        if value_key in result and unit_key not in result:
            del result[value_key]
    return result

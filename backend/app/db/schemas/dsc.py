from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IsothermalHold(BaseModel):
    temp: float
    temp_unit: Literal["C", "K"] = "C"
    duration: float
    time_unit: Literal["s", "min", "h"] = "min"


class MixtureComponent(BaseModel):
    name: str
    weight_fraction: Optional[float] = Field(None, ge=0.0, le=1.0)
    mass_value: Optional[float] = Field(None, gt=0.0)
    mass_unit: Optional[Literal["mg", "g", "ug"]] = "mg"


class DSCMetadataPayload(BaseModel):
    """Shared metadata structure used by header parser, LLM extractor, and API."""

    # Signal Interpretation
    endothermic_direction: Optional[Literal["up", "down", "unknown"]] = "unknown"
    heat_flow_unit: Optional[str] = None
    is_mass_normalized: bool = False
    temperature_unit: Optional[Literal["C", "K", "F"]] = None
    has_time_axis: bool = False
    time_unit: Optional[Literal["s", "min", "ms"]] = None

    # Run Conditions
    heating_rate_value: Optional[Decimal] = None
    heating_rate_unit: Optional[str] = None
    temp_start_value: Optional[Decimal] = None
    temp_end_value: Optional[Decimal] = None
    temp_range_unit: Optional[Literal["C", "K"]] = None
    isothermal_holds: list[IsothermalHold] = Field(default_factory=list)
    sample_mass_value: Optional[Decimal] = None
    sample_mass_unit: Optional[Literal["mg", "g", "ug"]] = None
    crucible_type: Optional[str] = None
    crucible_lid_config: Optional[
        Literal["open", "hermetic", "pinhole", "pierced_lid"]
    ] = None
    purge_gas: Optional[str] = None
    purge_flow_value: Optional[Decimal] = None
    purge_flow_unit: Optional[str] = None

    # Sample Information
    sample_name: str
    sample_category: Optional[
        Literal["pure_drug", "excipient", "mixture", "reference"]
    ] = None
    composition: list[MixtureComponent] = Field(default_factory=list)
    sample_preparation: Optional[str] = None
    storage_condition: Optional[str] = None
    storage_duration_value: Optional[Decimal] = None
    storage_duration_unit: Optional[Literal["days", "hours", "months"]] = None
    reference_file_id: Optional[uuid.UUID] = None

    extraction_source: Literal["header_parser", "llm_extracted", "user_verified"] = (
        "header_parser"
    )
    raw_header_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def infer_mass_normalization(self) -> "DSCMetadataPayload":
        """Automatically flag mass-normalized units like mW/mg or W/g."""
        if self.heat_flow_unit:
            normalized_tokens = ("/mg", "/g", "mg^-1", "g^-1")
            if any(tok in self.heat_flow_unit.lower() for tok in normalized_tokens):
                self.is_mass_normalized = True
        return self

    def missing_critical_fields(self) -> list[str]:
        """Checks mandatory Signal & Mass questions before integration can run."""
        missing: list[str] = []
        if not self.endothermic_direction or self.endothermic_direction == "unknown":
            missing.append("endothermic_direction")
        if not self.heat_flow_unit:
            missing.append("heat_flow_unit")
        if not self.temperature_unit:
            missing.append("temperature_unit")
        if not self.is_mass_normalized and self.sample_mass_value is None:
            missing.append("sample_mass_value")
        return missing


class DSCMetadataRead(DSCMetadataPayload):
    model_config = ConfigDict(from_attributes=True)
    metadata_id: uuid.UUID
    file_id: uuid.UUID
    updated_at: datetime


class FileUploadResponse(BaseModel):
    file_id: uuid.UUID
    original_filename: str
    storage_uri: str
    metadata: DSCMetadataRead
    missing_critical_fields: list[str]
    ready_for_analysis: bool

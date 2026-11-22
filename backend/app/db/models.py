from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy 2.0 models."""


class DSCFile(Base):
    __tablename__ = "dsc_files"

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    file_format: Mapped[str] = mapped_column(String(32), nullable=False)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    metadata_record: Mapped[Optional["DSCMetadata"]] = relationship(
        back_populates="file",
        foreign_keys="DSCMetadata.file_id",
        uselist=False,
        cascade="all, delete-orphan",
    )
    analysis_runs: Mapped[list["AnalysisRun"]] = relationship(
        back_populates="file",
        foreign_keys="AnalysisRun.file_id",
        cascade="all, delete-orphan",
    )
    table_uri: Mapped[Optional[str]] = mapped_column(Text)


class DSCMetadata(Base):
    __tablename__ = "dsc_metadata"
    __table_args__ = (
        CheckConstraint(
            "endothermic_direction IN ('up', 'down', 'unknown')",
            name="ck_endothermic_direction",
        ),
        CheckConstraint(
            "sample_category IN ('pure_drug', 'excipient', 'mixture', 'reference')",
            name="ck_sample_category",
        ),
    )

    metadata_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dsc_files.file_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # 1. Signal Interpretation & Axis Units
    endothermic_direction: Mapped[Optional[str]] = mapped_column(String(10))
    heat_flow_unit: Mapped[Optional[str]] = mapped_column(String(20))
    is_mass_normalized: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature_unit: Mapped[Optional[str]] = mapped_column(String(10))
    has_time_axis: Mapped[bool] = mapped_column(Boolean, default=False)
    time_unit: Mapped[Optional[str]] = mapped_column(String(10))

    # 2. Run Conditions (Value + Explicit Unit pairs)
    heating_rate_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    heating_rate_unit: Mapped[Optional[str]] = mapped_column(String(20))
    temp_start_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    temp_end_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    temp_range_unit: Mapped[Optional[str]] = mapped_column(String(10))
    isothermal_holds: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    sample_mass_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 5))
    sample_mass_unit: Mapped[Optional[str]] = mapped_column(String(10))
    crucible_type: Mapped[Optional[str]] = mapped_column(String(100))
    crucible_lid_config: Mapped[Optional[str]] = mapped_column(String(50))
    purge_gas: Mapped[Optional[str]] = mapped_column(String(50))
    purge_flow_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    purge_flow_unit: Mapped[Optional[str]] = mapped_column(String(20))

    # 3. Sample Information & Reference Dataset
    sample_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sample_category: Mapped[Optional[str]] = mapped_column(String(32))
    composition: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    sample_preparation: Mapped[Optional[str]] = mapped_column(Text)
    storage_condition: Mapped[Optional[str]] = mapped_column(Text)
    storage_duration_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    storage_duration_unit: Mapped[Optional[str]] = mapped_column(String(15))
    reference_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dsc_files.file_id", ondelete="SET NULL")
    )

    # Provenance & Raw Header
    extraction_source: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_header_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    file: Mapped["DSCFile"] = relationship(
        back_populates="metadata_record", foreign_keys=[file_id]
    )

    field_sources: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    parse_warnings: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    unconfirmed_fields: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'awaiting_metadata', 'running', 'completed', 'failed')",
            name="ck_analysis_status",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dsc_files.file_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    compared_reference_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dsc_files.file_id", ondelete="SET NULL")
    )
    agent_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    preprocessing_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    compatibility_verdict: Mapped[Optional[str]] = mapped_column(String(32))
    summary_report: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    file: Mapped["DSCFile"] = relationship(
        back_populates="analysis_runs", foreign_keys=[file_id]
    )
    thermal_events: Mapped[list["ThermalEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ThermalEvent(Base):
    __tablename__ = "thermal_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('melting', 'glass_transition', 'crystallization', 'decomposition', 'moisture_loss')",
            name="ck_event_type",
        ),
        CheckConstraint(
            "thermal_direction IN ('endothermic', 'exothermic', 'step_change')",
            name="ck_thermal_direction",
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    thermal_direction: Mapped[str] = mapped_column(String(15), nullable=False)

    onset_temp_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    peak_temp_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    endset_temp_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    temp_unit: Mapped[str] = mapped_column(String(10), default="C", nullable=False)

    enthalpy_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    enthalpy_unit: Mapped[str] = mapped_column(
        String(20), default="J/g", nullable=False
    )
    is_drug_normalized: Mapped[bool] = mapped_column(Boolean, default=False)

    delta_cp_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 5))
    delta_cp_unit: Mapped[Optional[str]] = mapped_column(String(20))

    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    run: Mapped["AnalysisRun"] = relationship(back_populates="thermal_events")

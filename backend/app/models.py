from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DSCDataPoint(BaseModel):
    """Single DSC measurement point"""

    temperature: float = Field(..., description="Temperature in °C")
    heat_flow: float = Field(..., description="Heat flow in mW or µV")

    class Config:
        json_schema_extra = {"example": {"temperature": 25.5, "heat_flow": 0.1}}


class DSCCurve(BaseModel):
    """Complete DSC curve data"""

    data_points: List[DSCDataPoint]
    count: int
    temperature_range: tuple
    heat_flow_range: tuple

    class Config:
        json_schema_extra = {
            "example": {
                "data_points": [
                    {"temperature": 25.0, "heat_flow": -0.05},
                    {"temperature": 166.0, "heat_flow": 2.75},
                ],
                "count": 2,
                "temperature_range": [25.0, 166.0],
                "heat_flow_range": [-0.05, 2.75],
            }
        }


class AnalysisMetrics(BaseModel):
    """DSC analysis results and metrics"""

    melting_point: Optional[float] = Field(None, description="Melting point in °C")
    onset_temperature: Optional[float] = Field(
        None, description="Onset temperature in °C"
    )
    peak_area: Optional[float] = Field(None, description="Peak area under curve")
    crystallinity_index: Optional[float] = Field(
        None, description="Relative crystallinity (0-1)"
    )
    peak_width: Optional[float] = Field(None, description="Peak width at half height")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")

    class Config:
        json_schema_extra = {
            "example": {
                "melting_point": 166.2,
                "onset_temperature": 160.5,
                "peak_area": 245.8,
                "crystallinity_index": 0.87,
                "peak_width": 5.3,
                "confidence": 0.92,
            }
        }


class AnalysisRequest(BaseModel):
    """Request to analyze DSC data"""

    filename: str = Field(..., description="Name of uploaded file")
    normalize: bool = Field(True, description="Apply normalization")
    smoothing_window: int = Field(5, ge=1, le=20, description="Smoothing window size")
    remove_baseline: bool = Field(True, description="Remove baseline drift")

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "sample.csv",
                "normalize": True,
                "smoothing_window": 5,
                "remove_baseline": True,
            }
        }


class AnalysisResult(BaseModel):
    """Complete analysis result"""

    filename: str
    metrics: AnalysisMetrics
    raw_curve: DSCCurve
    processed_curve: DSCCurve
    processing_time_ms: float
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "sample.csv",
                "metrics": {"melting_point": 166.2, "confidence": 0.92},
                "raw_curve": {
                    "data_points": [],
                    "count": 56,
                    "temperature_range": [25.0, 200.0],
                    "heat_flow_range": [-0.05, 2.8],
                },
                "processed_curve": {
                    "data_points": [],
                    "count": 56,
                    "temperature_range": [25.0, 200.0],
                    "heat_flow_range": [0.0, 1.0],
                },
                "processing_time_ms": 125.4,
                "created_at": "2024-01-15T10:30:00",
            }
        }

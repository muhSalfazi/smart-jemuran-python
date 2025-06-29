from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List, Dict


class JemuranData(BaseModel):
    temperature: float
    humidity: float
    light: int
    rain: bool
    last_update: datetime


class RecommendationDetails(BaseModel):
    rules_activated: List[str]
    input_values: Dict[str, float]


class RecommendationResponse(BaseModel):
    recommendation: str
    confidence: float
    details: RecommendationDetails


class ControlRequest(BaseModel):
    action: str


class HealthCheckResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]

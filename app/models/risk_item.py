from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskItem(BaseModel):
    id: int
    description: str
    level: RiskLevel
    related_norms: Optional[List[str]] = None

class RiskAssessment(BaseModel):
    fire_risk: RiskLevel
    structural_risk: RiskLevel
    evacuation_risk: RiskLevel
    equipment_adequacy: float
    compliance_score: float
    priority_actions: List[str]
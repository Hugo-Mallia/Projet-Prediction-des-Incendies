from pydantic import BaseModel, Field
from typing import List, Optional

class RiskAssessment(BaseModel):
    fire_risk: str
    structural_risk: str
    evacuation_risk: str
    equipment_adequacy: float
    compliance_score: float
    priority_actions: List[str]

class ContextualInsight(BaseModel):
    insight_type: str
    message: str
    urgency: str
    related_norms: List[str]

class AuditQuestion(BaseModel):
    key: str
    text: str
    validation_type: str
    options: Optional[List[str]] = Field(default_factory=list)

class Item(BaseModel):
    id: int
    name: str
    description: str | None = None

class ItemCreate(BaseModel):
    name: str
    description: str | None = None

class ItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
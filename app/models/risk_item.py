from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class RiskItem(BaseModel):
    label: str
    confidence: float
    location: dict  # Contient les coordonnées de l'objet détecté

class AuditData(BaseModel):
    buildingName: str
    buildingType: str
    buildingUsage: str
    buildingSize: int
    fireExtinguishers: int
    emergencyExits: int
    smokeDetectors: int
    fireDrills: str
    roomCount: int
    roomSizes: List[float]
    constructionMaterials: str
    evacuationPlan: str
    trainingSessions: int
    staffAwareness: int
    automatedData: Optional[Dict[str, Any]] = None

class AuditResult(BaseModel):
    status: str
    message: str
    recommendations: List[str]
    data: AuditData
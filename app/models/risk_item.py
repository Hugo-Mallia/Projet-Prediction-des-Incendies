from pydantic import BaseModel

class RiskItem(BaseModel):
    label: str
    confidence: float
    location: dict  # Contient les coordonnées de l'objet détecté

from typing import List
from app.models.risk_item import RiskItem
from fastapi import UploadFile
import numpy as np

def detect_risks(image: UploadFile) -> List[RiskItem]:
    # Simuler une détection d'objets pour l'exemple
    # Dans une application réelle, on utilisera un modèle de détection d'objets ici
    risks = [
        RiskItem(label="tapis", confidence=0.85, location={"x": 100, "y": 200, "w": 150, "h": 150}),
        RiskItem(label="cheminée", confidence=0.90, location={"x": 300, "y": 400, "w": 200, "h": 200})
    ]
    return risks

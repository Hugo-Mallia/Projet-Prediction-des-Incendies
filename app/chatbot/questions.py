from typing import List

class AuditQuestion:
    def __init__(self, text: str, key: str, validation_type: str):
        self.text = text
        self.key = key
        self.validation_type = validation_type

SMART_AUDIT_QUESTIONS: List[AuditQuestion] = [
    AuditQuestion("Quel est le type de bâtiment ?", "buildingType", "text"),
    AuditQuestion("Quelle est la taille du bâtiment en m² ?", "buildingSize", "number"),
    AuditQuestion("Combien d'extincteurs sont disponibles ?", "fireExtinguishers", "number"),
    AuditQuestion("Combien de détecteurs de fumée sont installés ?", "smokeDetectors", "number"),
    AuditQuestion("Combien de sorties de secours sont disponibles ?", "emergencyExits", "number"),
    AuditQuestion("Quelle est la dernière date d'inspection des équipements ?", "lastInspection", "date"),
    AuditQuestion("Y a-t-il un plan d'évacuation affiché ?", "evacuationPlan", "boolean"),
    AuditQuestion("Combien de sessions de formation ont été réalisées ?", "trainingSessions", "number"),
    AuditQuestion("Quels matériaux de construction sont utilisés ?", "constructionMaterials", "materials"),
    AuditQuestion("Quelle est la capacité maximale d'occupation ?", "maxOccupancy", "number"),
    AuditQuestion("Y a-t-il un système d'alarme incendie installé ?", "alarmSystem", "boolean"),
    AuditQuestion("Y a-t-il un système de sprinkleur installé ?", "sprinklerSystem", "boolean"),
]
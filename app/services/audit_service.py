from typing import Dict, Any, List
from datetime import datetime
from app.chatbot.audit_state import SmartAuditState
from app.models.schemas import RiskAssessment, ContextualInsight
from app.models.risk_item import RiskLevel
import logging

logger = logging.getLogger(__name__)

class AuditService:
    def __init__(self):
        self.audit_state = SmartAuditState()

    def export_audit_data(self) -> Dict[str, Any]:
        """Exporte les données d'audit pour sauvegarde ou traitement"""
        return {
            "audit_data": self.audit_state.data,
            "risk_indicators": self.audit_state.risk_indicators,
            "contextual_insights": [
                {
                    "type": insight.insight_type,
                    "message": insight.message,
                    "urgency": insight.urgency.value,
                    "norms": insight.related_norms
                }
                for insight in self.audit_state.contextual_insights
            ],
            "completion_status": self.audit_state.complete,
            "timestamp": datetime.now().isoformat()
        }

    def import_audit_data(self, data: Dict[str, Any]) -> bool:
        """Importe des données d'audit précédemment sauvegardes"""
        try:
            self.audit_state.data = data.get("audit_data", {})
            self.audit_state.risk_indicators = data.get("risk_indicators", [])
            
            # Reconstruction des insights
            insights_data = data.get("contextual_insights", [])
            self.audit_state.contextual_insights = []
            
            for insight_data in insights_data:
                insight = ContextualInsight(
                    insight_type=insight_data["type"],
                    message=insight_data["message"],
                    urgency=RiskLevel(insight_data["urgency"]),
                    related_norms=insight_data.get("norms", [])
                )
                self.audit_state.contextual_insights.append(insight)
            
            self.audit_state.complete = data.get("completion_status", False)
            
            # Repositionnement dans les questions
            answered_count = len([k for k in self.audit_state.data.keys() 
                                if k in [q.key for q in self.questions]])
            self.audit_state.current_idx = answered_count
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'import des données: {e}")
            return False

    def reset_audit(self):
        """Réinitialise complètement l'audit"""
        self.audit_state = SmartAuditState()

def evaluate_audit(audit_data):
    # Implémentation simple ou à adapter selon ton besoin
    # Par exemple, retourne un score fictif
    return {
        "score": 0.8,
        "details": "Audit évalué avec succès.",
        "risks": [],
    }
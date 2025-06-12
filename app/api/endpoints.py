from fastapi import APIRouter, HTTPException
from app.chatbot.audit_state import SmartAuditState

router = APIRouter()

@router.post("/audit/start")
async def start_audit():
    """Démarre un nouvel audit"""
    try:
        audit_state = SmartAuditState()
        return {"message": "Audit démarré", "audit_id": audit_state.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/audit/answer")
async def submit_answer(answer: str):
    """Soumet une réponse à l'audit"""
    try:
        # Logique pour traiter la réponse
        return {"message": "Réponse soumise avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit/export/{session_id}")
async def export_audit_results(session_id: str):
    """Exporte les résultats d'audit"""
    try:
        # Logique pour exporter les résultats
        return {"message": "Résultats d'audit exportés avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
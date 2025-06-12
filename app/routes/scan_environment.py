from fastapi import APIRouter, HTTPException
from app.chatbot.flameo import FlameoChatbotEnhanced

router = APIRouter()
chatbot = FlameoChatbotEnhanced()

@router.post("/scan")
async def scan_environment(data: dict):
    try:
        # Process the scanning data using the chatbot
        response = chatbot.perform_intelligent_analysis(data)
        return {"status": "success", "data": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import List
from app.models.risk_item import RiskItem
from app.services.detection_service import detect_risks

router = APIRouter()

@router.post("/scan-environment/", response_model=List[RiskItem])
async def scan_environment(image: UploadFile = File(...)):
    try:
        risks = detect_risks(image)
        return risks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

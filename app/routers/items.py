from fastapi import APIRouter, HTTPException
from app.models import Item

router = APIRouter()

mock_db = {
    1: {"name": "Item One"},
    2: {"name": "Item Two"}
}

@router.get("/items/{item_id}")
async def get_item(item_id: int):
    item = mock_db.get(item_id)
    if item:
        return {"item_id": item_id, **item}
    raise HTTPException(status_code=404, detail="Item not found")

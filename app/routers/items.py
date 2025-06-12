from fastapi import APIRouter, HTTPException
from app.models.schemas import Item, ItemCreate, ItemUpdate

router = APIRouter()

# In-memory storage for items (for demonstration purposes)
items_db = {}

@router.post("/items/", response_model=Item)
async def create_item(item: ItemCreate):
    item_id = len(items_db) + 1
    new_item = Item(id=item_id, **item.dict())
    items_db[item_id] = new_item
    return new_item

@router.get("/items/{item_id}", response_model=Item)
async def read_item(item_id: int):
    item = items_db.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, item_update: ItemUpdate):
    item = items_db.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    updated_item = item.copy(update=item_update.dict())
    items_db[item_id] = updated_item
    return updated_item

@router.delete("/items/{item_id}", response_model=Item)
async def delete_item(item_id: int):
    item = items_db.pop(item_id, None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
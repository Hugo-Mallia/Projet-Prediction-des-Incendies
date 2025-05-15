from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_existing_item():
    response = client.get("/api/items/1")
    assert response.status_code == 200
    assert response.json() == {"item_id": 1, "name": "Item One"}

def test_get_non_existent_item():
    response = client.get("/api/items/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}

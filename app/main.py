from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routes.scan_environment import router as scan_router
from app.routers.items import router as items_router

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

app.include_router(scan_router, prefix="/api")
app.include_router(items_router, prefix="/api")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/audit")
async def audit_page(request: Request):
    return templates.TemplateResponse("audit.html", {"request": request})

@app.post("/api/submit-audit")
async def submit_audit(
    buildingName: str = Form(...),
    fireExtinguishers: int = Form(...),
    emergencyExits: int = Form(...),
    smokeDetectors: int = Form(...),
    buildingSize: int = Form(...),
    roomCount: int = Form(...),
    roomSizes: str = Form(...)
):
    # Simuler l'intégration de capteurs pour collecter des données supplémentaires
    automated_data = {
        "temperature": 25,  # Température ambiante en °C
        "smoke_level": 0.02,  # Niveau de fumée détecté
        "fire_extinguisher_status": "OK"  # Statut des extincteurs
    }

    # Convertir les tailles des pièces en liste de nombres
    try:
        room_sizes = [float(size.strip()) for size in roomSizes.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid room sizes format")

    # Évaluation des normes européennes
    status = "Conforme"
    message = "Le bâtiment respecte les normes européennes."
    if fireExtinguishers < (buildingSize // 200):
        status = "Non conforme"
        message = "Nombre d'extincteurs insuffisant (1 extincteur requis pour 200 m²)."
    elif emergencyExits < 2:
        status = "Non conforme"
        message = "Nombre de sorties de secours insuffisant (minimum 2 requises)."
    elif smokeDetectors < roomCount:
        status = "Non conforme"
        message = "Nombre de détecteurs de fumée insuffisant (1 détecteur requis par pièce)."
    elif any(size > 50 for size in room_sizes):
        status = "Non conforme"
        message = "Certaines pièces dépassent la taille maximale autorisée de 50 m²."

    # Retourner les informations saisies, les données automatisées et le résultat de l'audit
    return {
        "status": status,
        "message": message,
        "data": {
            "buildingName": buildingName,
            "fireExtinguishers": fireExtinguishers,
            "emergencyExits": emergencyExits,
            "smokeDetectors": smokeDetectors,
            "buildingSize": buildingSize,
            "roomCount": roomCount,
            "roomSizes": room_sizes,
            "automatedData": automated_data
        }
    }

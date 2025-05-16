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
    buildingType: str = Form(...),
    buildingUsage: str = Form(...),
    buildingSize: int = Form(...),
    fireExtinguishers: int = Form(...),
    emergencyExits: int = Form(...),
    smokeDetectors: int = Form(...),
    fireDrills: str = Form(...),
    roomCount: int = Form(...),
    roomSizes: str = Form(...),
    constructionMaterials: str = Form(...),
    evacuationPlan: str = Form(...),
    trainingSessions: int = Form(...),
    staffAwareness: int = Form(...)
):
    # Convertir les tailles des pièces en liste de nombres
    try:
        room_sizes = [float(size.strip()) for size in roomSizes.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid room sizes format")

    # Simuler l'intégration de capteurs pour collecter des données supplémentaires
    automated_data = {
        "temperature": 25,  # Température ambiante en °C
        "smoke_level": 0.02,  # Niveau de fumée détecté
        "fire_extinguisher_status": "OK"  # Statut des extincteurs
    }

    # Évaluation des normes européennes
    status = "Conforme"
    message = "Le bâtiment respecte les normes européennes."
    recommendations = []

    if fireExtinguishers < (buildingSize // 200):
        status = "Non conforme"
        message = "Nombre d'extincteurs insuffisant (1 extincteur requis pour 200 m²)."
        recommendations.append("Ajoutez des extincteurs pour atteindre le ratio requis (1 extincteur pour 200 m²).")

    if emergencyExits < 2:
        status = "Non conforme"
        message = "Nombre de sorties de secours insuffisant (minimum 2 requises)."
        recommendations.append("Ajoutez au moins deux sorties de secours accessibles et bien signalées.")

    if smokeDetectors < roomCount:
        status = "Non conforme"
        message = "Nombre de détecteurs de fumée insuffisant (1 détecteur requis par pièce)."
        recommendations.append("Installez des détecteurs de fumée dans toutes les pièces.")

    if any(size > 50 for size in room_sizes):
        status = "Non conforme"
        message = "Certaines pièces dépassent la taille maximale autorisée de 50 m²."
        recommendations.append("Divisez les pièces dépassant 50 m² en espaces plus petits.")

    if evacuationPlan == "non":
        recommendations.append("Créez et affichez un plan d'évacuation clair et accessible.")

    if trainingSessions < 2:
        recommendations.append("Organisez au moins deux sessions de formation en sécurité incendie par an.")

    if staffAwareness < 3:
        recommendations.append("Sensibilisez davantage le personnel aux pratiques de sécurité incendie.")

    # Toujours inclure des recommandations générales
    recommendations.append("Effectuez des exercices d'évacuation réguliers pour améliorer la préparation.")
    recommendations.append("Vérifiez régulièrement l'état des équipements de sécurité.")

    # Retourner les informations saisies, les recommandations et le résultat de l'audit
    return {
        "status": status,
        "message": message,
        "recommendations": recommendations,
        "data": {
            "buildingName": buildingName,
            "buildingType": buildingType,
            "buildingUsage": buildingUsage,
            "buildingSize": buildingSize,
            "fireExtinguishers": fireExtinguishers,
            "emergencyExits": emergencyExits,
            "smokeDetectors": smokeDetectors,
            "fireDrills": fireDrills,
            "roomCount": roomCount,
            "roomSizes": room_sizes,
            "constructionMaterials": constructionMaterials,
            "evacuationPlan": evacuationPlan,
            "trainingSessions": trainingSessions,
            "staffAwareness": staffAwareness,
            "automatedData": automated_data
        }
    }

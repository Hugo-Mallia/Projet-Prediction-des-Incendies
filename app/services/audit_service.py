from app.models.risk_item import AuditData, AuditResult

def evaluate_audit(data: dict) -> AuditResult:
    try:
        room_sizes = [float(size.strip()) for size in data["roomSizes"].split(",")]
    except Exception:
        room_sizes = []

    automated_data = {
        "temperature": 25,
        "smoke_level": 0.02,
        "fire_extinguisher_status": "OK"
    }

    status = "Conforme"
    message = "Le bâtiment respecte les normes européennes."
    recommendations = []

    if data["fireExtinguishers"] < (data["buildingSize"] // 200):
        status = "Non conforme"
        message = "Nombre d'extincteurs insuffisant (1 extincteur requis pour 200 m²)."
        recommendations.append("Ajoutez des extincteurs pour atteindre le ratio requis (1 extincteur pour 200 m²).")

    if data["emergencyExits"] < 2:
        status = "Non conforme"
        message = "Nombre de sorties de secours insuffisant (minimum 2 requises)."
        recommendations.append("Ajoutez au moins deux sorties de secours accessibles et bien signalées.")

    if data["smokeDetectors"] < data["roomCount"]:
        status = "Non conforme"
        message = "Nombre de détecteurs de fumée insuffisant (1 détecteur requis par pièce)."
        recommendations.append("Installez des détecteurs de fumée dans toutes les pièces.")

    if any(size > 50 for size in room_sizes):
        status = "Non conforme"
        message = "Certaines pièces dépassent la taille maximale autorisée de 50 m²."
        recommendations.append("Divisez les pièces dépassant 50 m² en espaces plus petits.")

    if data["evacuationPlan"] == "non":
        recommendations.append("Créez et affichez un plan d'évacuation clair et accessible.")

    if data["trainingSessions"] < 2:
        recommendations.append("Organisez au moins deux sessions de formation en sécurité incendie par an.")

    if data["staffAwareness"] < 3:
        recommendations.append("Sensibilisez davantage le personnel aux pratiques de sécurité incendie.")

    recommendations.append("Effectuez des exercices d'évacuation réguliers pour améliorer la préparation.")
    recommendations.append("Vérifiez régulièrement l'état des équipements de sécurité.")

    audit_data = AuditData(
        buildingName=data["buildingName"],
        buildingType=data["buildingType"],
        buildingUsage=data["buildingUsage"],
        buildingSize=data["buildingSize"],
        fireExtinguishers=data["fireExtinguishers"],
        emergencyExits=data["emergencyExits"],
        smokeDetectors=data["smokeDetectors"],
        fireDrills=data["fireDrills"],
        roomCount=data["roomCount"],
        roomSizes=room_sizes,
        constructionMaterials=data["constructionMaterials"],
        evacuationPlan=data["evacuationPlan"],
        trainingSessions=data["trainingSessions"],
        staffAwareness=data["staffAwareness"],
        automatedData=automated_data
    )

    return AuditResult(
        status=status,
        message=message,
        recommendations=recommendations,
        data=audit_data
    )
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routes.scan_environment import router as scan_router
from app.routers.items import router as items_router
from app.services.audit_service import evaluate_audit
import gradio as gr

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

def audit_chatbot():
    questions = [
        ("Bonjour, je suis Flaméo, votre auditeur sécurité incendie. Pour commencer, quel est le nom du bâtiment à auditer ?", "buildingName"),
        ("Merci. Quel est le type de bâtiment (immeuble, maison, entrepôt, usine, établissement public) ?", "buildingType"),
        ("Très bien. Quel est l'usage principal du bâtiment (professionnel ou personnel) ?", "buildingUsage"),
        ("Pouvez-vous m’indiquer la taille du bâtiment en m² ?", "buildingSize"),
        ("Combien d’extincteurs sont présents dans le bâtiment ?", "fireExtinguishers"),
        ("Combien de sorties de secours sont disponibles ?", "emergencyExits"),
        ("Combien de détecteurs de fumée sont installés ?", "smokeDetectors"),
        ("Quelle est la date du dernier exercice d’évacuation (AAAA-MM-JJ) ?", "fireDrills"),
        ("Combien de pièces compte le bâtiment ?", "roomCount"),
        ("Merci. Quelle est la taille de chaque pièce (en m², séparées par des virgules) ?", "roomSizes"),
        ("Quels sont les matériaux de construction principaux ?", "constructionMaterials"),
        ("Un plan d’évacuation est-il disponible et affiché (oui/non) ?", "evacuationPlan"),
        ("Combien de sessions de formation en sécurité incendie ont eu lieu cette année ?", "trainingSessions"),
        ("Sur une échelle de 1 à 5, quel est le niveau de sensibilisation du personnel à la sécurité incendie ?", "staffAwareness"),
    ]
    state = {}

    def chat_fn(message, history):
        idx = len(history)
        if idx < len(questions):
            key = questions[idx-1][1] if idx > 0 else None
            if key:
                state[key] = message
            if idx < len(questions):
                # Ajoute une relance personnalisée
                if idx == 1:
                    return questions[idx][0] + " (N'hésitez pas à me donner des détails.)"
                return questions[idx][0]
        else:
            key = questions[-1][1]
            state[key] = message
            # Conversion des types
            try:
                state["buildingSize"] = int(state["buildingSize"])
                state["fireExtinguishers"] = int(state["fireExtinguishers"])
                state["emergencyExits"] = int(state["emergencyExits"])
                state["smokeDetectors"] = int(state["smokeDetectors"])
                state["roomCount"] = int(state["roomCount"])
                state["trainingSessions"] = int(state["trainingSessions"])
                state["staffAwareness"] = int(state["staffAwareness"])
            except Exception:
                return "Je n'ai pas compris une des valeurs numériques, pouvez-vous vérifier votre saisie ?"
            result = evaluate_audit(state)
            # Réponse finale personnalisée
            return (
                "Merci pour toutes ces informations, je vais maintenant analyser la conformité de votre bâtiment.\n\n"
                f"**Statut de l'audit** : {result.status}\n"
                f"**Résumé** : {result.message}\n"
                f"**Recommandations personnalisées** :\n- " + "\n- ".join(result.recommendations) +
                "\n\nN'hésitez pas à me solliciter pour un nouvel audit ou pour toute question complémentaire."
            )
        return ""

    with gr.Blocks() as demo:
        gr.Markdown("## 👩‍🚒 Flaméo  - Votre auditeur virtuel\nDiscutez avec votre auditeur pour réaliser un audit sécurité incendie personnalisé.")
        chatbot = gr.ChatInterface(chat_fn)
        gr.Button("⬅️ Retour à l'accueil").click(
            None,
            None,
            None,
            js="window.location.href='/'"
        )
    return demo

# Intégration Gradio sur /audit-bot
app = gr.mount_gradio_app(app, audit_chatbot(), path="/audit-bot")

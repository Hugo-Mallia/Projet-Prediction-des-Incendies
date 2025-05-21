from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routes.scan_environment import router as scan_router
from app.routers.items import router as items_router
from app.services.audit_service import evaluate_audit

import gradio as gr
from dotenv import load_dotenv
import os
import re

from langchain_core.messages import HumanMessage, AIMessage
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder
)
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI

# Chargement des variables d'environnement
load_dotenv()

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Ajouter les routers API
app.include_router(scan_router, prefix="/api")
app.include_router(items_router, prefix="/api")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def audit_chatbot():
    questions = [
        ("Bonjour, je suis Flaméo, votre auditeur sécurité incendie. Pour commencer, quel est le nom du bâtiment à auditer ?", "buildingName"),
        ("Merci. Quel est le type de bâtiment (immeuble, maison, entrepôt, usine, établissement public) ?", "buildingType"),
        ("Très bien. Quel est l'usage principal du bâtiment (professionnel ou personnel) ?", "buildingUsage"),
        ("Pouvez-vous m'indiquer la taille du bâtiment en m² ?", "buildingSize"),
        ("Combien d'extincteurs sont présents dans le bâtiment ?", "fireExtinguishers"),
        ("Combien de sorties de secours sont disponibles ?", "emergencyExits"),
        ("Combien de détecteurs de fumée sont installés ?", "smokeDetectors"),
        ("Quelle est la date du dernier exercice d'évacuation (AAAA-MM-JJ) ?", "fireDrills"),
        ("Combien de pièces compte le bâtiment ?", "roomCount"),
        ("Merci. Quelle est la taille de chaque pièce (en m², séparées par des virgules) ?", "roomSizes"),
        ("Quels sont les matériaux de construction principaux ?", "constructionMaterials"),
        ("Un plan d'évacuation est-il disponible et affiché (oui/non) ?", "evacuationPlan"),
        ("Combien de sessions de formation en sécurité incendie ont eu lieu cette année ?", "trainingSessions"),
        ("Sur une échelle de 1 à 5, quel est le niveau de sensibilisation du personnel à la sécurité incendie ?", "staffAwareness"),
    ]

    llm = ChatOpenAI(
        temperature=0.7,
        model="gpt-3.5-turbo"
    )

    system_prompt = """Tu es Flaméo, un expert en sécurité incendie qui aide à réaliser des audits de bâtiments. 
Tu es courtois, précis et tu parles français. Tu dois collecter des informations sur le bâtiment et évaluer sa conformité aux normes de sécurité incendie.

Voici les règles à suivre :
1. Un bâtiment doit avoir au moins 1 extincteur pour 200 m²
2. Un bâtiment doit avoir au moins 2 sorties de secours
3. Chaque pièce doit avoir un détecteur de fumée
4. Les pièces ne doivent pas dépasser 50 m²
5. Un plan d'évacuation doit être affiché
6. Au moins 2 sessions de formation doivent être organisées par an

Quand tu as collecté toutes les informations, tu dois évaluer la conformité du bâtiment et fournir des recommandations personnalisées."""

    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{input}")
    ])

    memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    conversation = ConversationChain(llm=llm, prompt=prompt, memory=memory, verbose=True)

    state = {}
    current_question_idx = 0
    audit_complete = False

    def extract_number(text):
        match = re.search(r'\b\d+\b', text)
        return int(match.group()) if match else None

    def convert_history(history):
        messages = []
        for entry in history:
            role = entry["role"]
            content = entry["content"]
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages

    def chat_fn(message, history):
        nonlocal current_question_idx, audit_complete

        # Convertir l'historique au format LangChain
        memory.chat_memory.messages = convert_history(history)

        if not history:
            return questions[0][0]

        if audit_complete:
            return conversation.predict(input=message)

        key = questions[current_question_idx][1]
        state[key] = message

        if key in ["buildingSize", "fireExtinguishers", "emergencyExits", "smokeDetectors", "roomCount", "trainingSessions", "staffAwareness"]:
            number = extract_number(message)
            if number is not None:
                state[key] = number
            else:
                clarification = conversation.predict(
                    input=f"L'utilisateur a répondu '{message}' à la question sur {key}. Je dois obtenir une valeur numérique. Reformule une question polie."
                )
                return clarification

        conversation.predict(input=f"Question: {questions[current_question_idx][0]}, Réponse: {message}")
        current_question_idx += 1

        if current_question_idx >= len(questions):
            audit_complete = True
            try:
                room_sizes = [float(size.strip()) for size in state.get("roomSizes", "").split(",")]
                state["roomSizes"] = room_sizes
            except Exception:
                state["roomSizes"] = []

            result = evaluate_audit(state)

            conversation.predict(
                input=f"""
                Résultat de l'audit:
                Status: {result.status}
                Message: {result.message}
                Recommandations: {result.recommendations}
                """
            )

            response = conversation.predict(
                input=f"""
                Voici les résultats de l'audit du bâtiment {state.get('buildingName', '')}.
                Statut: {result.status}
                {result.message}
                Recommandations :
                {result.recommendations}
                """
            )
            return response

        next_question = conversation.predict(
            input=f"Je dois poser la question suivante : {questions[current_question_idx][0]}. Personnalise-la si nécessaire."
        )

        return next_question

    with gr.Blocks() as demo:
        gr.Markdown("## 👩‍🚒 Flaméo - Votre auditeur sécurité incendie\nRépondez aux questions pour auditer votre bâtiment.")
        gr.ChatInterface(chat_fn, chatbot=gr.Chatbot(type="messages"))
        gr.Button("⬅️ Retour à l'accueil").click(
            None, None, None,
            js="window.location.href='/'"
        )

    return demo

# Gradio monté sur /audit-bot
app = gr.mount_gradio_app(app, audit_chatbot(), path="/audit-bot")

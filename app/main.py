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
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_openai import ChatOpenAI

load_dotenv()

app = FastAPI(title="Application d'audit de sécurité incendie")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(scan_router, prefix="/api")
app.include_router(items_router, prefix="/api")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@dataclass
class AuditQuestion:
    text: str
    key: str
    validation_type: str = "text"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    required: bool = True
    allowed_values: Optional[List[str]] = None

# Listes de valeurs autorisées pour validation
BUILDING_TYPES = [
    "immeuble", "maison", "entrepôt", "usine", "établissement public",
    "bureau", "commerce", "restaurant", "hôtel", "école", "hôpital"
]

BUILDING_USAGE = ["professionnel", "personnel", "mixte"]

CONSTRUCTION_MATERIALS = [
    "béton", "brique", "pierre", "bois", "métal", "acier", "placo",
    "parpaing", "béton armé", "bois massif", "ossature bois",
    "structure métallique", "maçonnerie", "préfabriqué"
]

AUDIT_QUESTIONS = [
    AuditQuestion("🏢 Quel est le nom du bâtiment à auditer ?", "buildingName", "text"),
    AuditQuestion("🏗️ Type de bâtiment (immeuble, maison, entrepôt, usine, établissement public, bureau, commerce, restaurant, hôtel, école, hôpital) ?", 
                  "buildingType", "building_type", allowed_values=BUILDING_TYPES),
    AuditQuestion("🎯 Usage principal (professionnel, personnel, mixte) ?", 
                  "buildingUsage", "building_usage", allowed_values=BUILDING_USAGE),
    AuditQuestion("📏 Superficie en m² ?", "buildingSize", "number", 1, 50000),
    AuditQuestion("🧯 Nombre d'extincteurs présents ?", "fireExtinguishers", "number", 0, 1000),
    AuditQuestion("🚪 Nombre de sorties de secours ?", "emergencyExits", "number", 0, 50),
    AuditQuestion("🔥 Nombre de détecteurs de fumée ?", "smokeDetectors", "number", 0, 500),
    AuditQuestion("📅 Date du dernier exercice d'évacuation (AAAA-MM-JJ) ?", "fireDrills", "date"),
    AuditQuestion("🏠 Nombre de pièces ?", "roomCount", "number", 1, 500),
    AuditQuestion("📐 Superficie de chaque pièce en m² (séparées par virgules) ?", "roomSizes", "room_sizes"),
    AuditQuestion("🧱 Matériaux de construction principaux (béton, brique, pierre, bois, métal, acier, placo, parpaing, etc.) ?", 
                  "constructionMaterials", "materials"),
    AuditQuestion("🗺️ Plan d'évacuation affiché (oui/non) ?", "evacuationPlan", "boolean"),
    AuditQuestion("📚 Nombre de sessions de formation sécurité cette année ?", "trainingSessions", "number", 0, 100),
    AuditQuestion("💡 Niveau de sensibilisation du personnel (1-5) ?", "staffAwareness", "number", 1, 5),
]

class ValidationUtils:
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalise le texte pour comparaison (minuscules, sans accents, espaces)"""
        import unicodedata
        text = text.lower().strip()
        # Supprime les accents
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        return text
    
    @staticmethod
    def fuzzy_match(input_text: str, valid_values: List[str], threshold: float = 0.7) -> Optional[str]:
        """Trouve la meilleure correspondance approximative"""
        input_normalized = ValidationUtils.normalize_text(input_text)
        
        best_match = None
        best_score = 0
        
        for value in valid_values:
            value_normalized = ValidationUtils.normalize_text(value)
            
            # Correspondance exacte
            if input_normalized == value_normalized:
                return value
            
            # Correspondance partielle
            if input_normalized in value_normalized or value_normalized in input_normalized:
                score = min(len(input_normalized), len(value_normalized)) / max(len(input_normalized), len(value_normalized))
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = value
        
        return best_match
    
    @staticmethod
    def extract_materials(text: str) -> List[str]:
        """Extrait et valide les matériaux de construction d'un texte"""
        found_materials = []
        text_normalized = ValidationUtils.normalize_text(text)
        
        for material in CONSTRUCTION_MATERIALS:
            material_normalized = ValidationUtils.normalize_text(material)
            if material_normalized in text_normalized:
                found_materials.append(material)
        
        # Recherche de correspondances approximatives pour les matériaux non trouvés
        words = text_normalized.split()
        for word in words:
            if len(word) > 3:  # Ignore les mots trop courts
                match = ValidationUtils.fuzzy_match(word, CONSTRUCTION_MATERIALS, 0.8)
                if match and match not in found_materials:
                    found_materials.append(match)
        
        return found_materials

class SimpleChatMessageHistory(BaseChatMessageHistory):
    def __init__(self):
        self._messages = []
    
    def add_user_message(self, message: str) -> None:
        self._messages.append(HumanMessage(content=message))
    
    def add_ai_message(self, message: str) -> None:
        self._messages.append(AIMessage(content=message))
    
    def clear(self) -> None:
        self._messages = []
        
    @property
    def messages(self):
        return self._messages
        
    @messages.setter
    def messages(self, value):
        self._messages = value

class AuditState:
    def __init__(self):
        self.questions = AUDIT_QUESTIONS
        self.current_idx = 0
        self.complete = False
        self.data: Dict[str, Any] = {}
        
    def get_current_question(self) -> Optional[AuditQuestion]:
        return self.questions[self.current_idx] if self.current_idx < len(self.questions) else None
    
    def advance(self) -> bool:
        self.current_idx += 1
        if self.current_idx >= len(self.questions):
            self.complete = True
            return True
        return False
    
    def store_answer(self, key: str, value: Any) -> None:
        self.data[key] = value
    
    def validate_answer(self, question: AuditQuestion, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        """Validation robuste avec vérifications spécifiques par type"""
        answer = answer.strip()
        
        if not answer and question.required:
            return False, None, "❌ Cette information est obligatoire."
        
        if question.validation_type == "number":
            return self._validate_number(question, answer)
        elif question.validation_type == "date":
            return self._validate_date(answer)
        elif question.validation_type == "room_sizes":
            return self._validate_room_sizes(answer)
        elif question.validation_type == "boolean":
            return self._validate_boolean(answer)
        elif question.validation_type == "building_type":
            return self._validate_building_type(answer)
        elif question.validation_type == "building_usage":
            return self._validate_building_usage(answer)
        elif question.validation_type == "materials":
            return self._validate_materials(answer)
        elif question.validation_type == "text":
            return self._validate_text(answer)
        
        return True, answer, None
    
    def _validate_number(self, question: AuditQuestion, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        try:
            # Recherche de nombres dans le texte
            numbers = re.findall(r'\b\d+(?:[.,]\d+)?\b', answer)
            if not numbers:
                return False, None, "❌ Aucun nombre trouvé dans votre réponse."
            
            # Prend le premier nombre trouvé
            value = float(numbers[0].replace(',', '.'))
            if value.is_integer():
                value = int(value)
            
            # Validation des limites
            if question.min_value is not None and value < question.min_value:
                return False, None, f"❌ Valeur minimum requise: {question.min_value}"
            if question.max_value is not None and value > question.max_value:
                return False, None, f"❌ Valeur maximum autorisée: {question.max_value}"
            
            # Validation logique supplémentaire
            if question.key == "buildingSize" and value > 50000:
                return False, None, "❌ Superficie trop importante. Vérifiez votre saisie."
            elif question.key == "roomCount" and value > 500:
                return False, None, "❌ Nombre de pièces trop élevé. Vérifiez votre saisie."
            
            return True, value, None
            
        except Exception as e:
            return False, None, f"❌ Format de nombre invalide: {str(e)}"
    
    def _validate_date(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        # Recherche de dates dans différents formats
        date_patterns = [
            r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b',  # YYYY-MM-DD
            r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',  # DD/MM/YYYY
            r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b',  # DD-MM-YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, answer)
            if match:
                try:
                    if pattern == date_patterns[0]:  # YYYY-MM-DD
                        year, month, day = map(int, match.groups())
                    else:  # DD/MM/YYYY ou DD-MM-YYYY
                        day, month, year = map(int, match.groups())
                    
                    # Validation de la date
                    date_obj = datetime(year, month, day)
                    
                    # Vérification que la date n'est pas dans le futur
                    if date_obj > datetime.now():
                        return False, None, "❌ La date ne peut pas être dans le futur."
                    
                    # Vérification que la date n'est pas trop ancienne (plus de 10 ans)
                    if (datetime.now() - date_obj).days > 3650:
                        return False, None, "❌ Date trop ancienne (plus de 10 ans)."
                    
                    # Retourne au format standard YYYY-MM-DD
                    formatted_date = f"{year:04d}-{month:02d}-{day:02d}"
                    return True, formatted_date, None
                    
                except ValueError:
                    continue
        
        return False, None, "❌ Format de date invalide. Utilisez YYYY-MM-DD, DD/MM/YYYY ou DD-MM-YYYY"
    
    def _validate_room_sizes(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        try:
            # Extraction des nombres
            numbers = re.findall(r'\b\d+(?:[.,]\d+)?\b', answer)
            if not numbers:
                return False, None, "❌ Aucune superficie trouvée. Format: nombres séparés par des virgules"
            
            values = []
            for num_str in numbers:
                value = float(num_str.replace(',', '.'))
                if value <= 0:
                    return False, None, f"❌ Superficie invalide: {value}. Toutes les superficies doivent être positives."
                if value > 1000:
                    return False, None, f"❌ Superficie trop importante: {value} m². Vérifiez votre saisie."
                values.append(value)
            
            # Vérification cohérence avec nombre de pièces si disponible
            if "roomCount" in self.data and len(values) != self.data["roomCount"]:
                return False, None, f"❌ Incohérence: {self.data['roomCount']} pièces annoncées mais {len(values)} superficies données."
            
            return True, values, None
            
        except Exception as e:
            return False, None, f"❌ Erreur de format: {str(e)}. Utilisez le format: 25, 30, 15"
    
    def _validate_boolean(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        answer_lower = answer.lower()
        positive_responses = ["oui", "yes", "vrai", "true", "1", "o", "ok", "présent", "affiché"]
        negative_responses = ["non", "no", "faux", "false", "0", "n", "absent", "pas affiché"]
        
        for pos in positive_responses:
            if pos in answer_lower:
                return True, True, None
        
        for neg in negative_responses:
            if neg in answer_lower:
                return True, False, None
        
        return False, None, "❌ Répondez par 'oui' ou 'non' (ou équivalent)"
    
    def _validate_building_type(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        # Recherche de correspondance exacte ou approximative
        match = ValidationUtils.fuzzy_match(answer, BUILDING_TYPES)
        if match:
            return True, match, None
        
        # Suggestions basées sur des mots-clés
        suggestions = []
        answer_lower = answer.lower()
        if any(word in answer_lower for word in ["bureau", "office", "travail"]):
            suggestions.append("bureau")
        elif any(word in answer_lower for word in ["magasin", "boutique", "commerce"]):
            suggestions.append("commerce")
        elif any(word in answer_lower for word in ["résidence", "habitation", "domicile"]):
            suggestions.append("maison")
        
        error_msg = f"❌ Type de bâtiment non reconnu. Types acceptés: {', '.join(BUILDING_TYPES)}"
        if suggestions:
            error_msg += f"\n💡 Peut-être vouliez-vous dire: {', '.join(suggestions)} ?"
        
        return False, None, error_msg
    
    def _validate_building_usage(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        match = ValidationUtils.fuzzy_match(answer, BUILDING_USAGE)
        if match:
            return True, match, None
        
        return False, None, f"❌ Usage non reconnu. Usages acceptés: {', '.join(BUILDING_USAGE)}"
    
    def _validate_materials(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        materials = ValidationUtils.extract_materials(answer)
        
        if not materials:
            return False, None, f"❌ Aucun matériau reconnu. Matériaux acceptés: {', '.join(CONSTRUCTION_MATERIALS[:10])}..."
        
        # Avertissement si matériaux inflammables détectés
        flammable_materials = ["bois", "bois massif", "ossature bois"]
        if any(mat in materials for mat in flammable_materials):
            warning = "⚠️ Matériaux inflammables détectés. Attention particulière requise pour la sécurité incendie."
            return True, materials, warning
        
        return True, materials, None
    
    def _validate_text(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        if len(answer) < 2:
            return False, None, "❌ Réponse trop courte. Veuillez être plus précis."
        
        if len(answer) > 200:
            return False, None, "❌ Réponse trop longue. Soyez plus concis (max 200 caractères)."
        
        # Vérification de caractères suspects
        if re.search(r'[<>{}[\]\\]', answer):
            return False, None, "❌ Caractères non autorisés détectés."
        
        return True, answer.strip(), None

class FlameoChatbot:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0.7, model="gpt-4o-mini")
        
        system_prompt = """Tu es Flaméo 🔥, expert en sécurité incendie sympathique et professionnel.

NORMES DE SÉCURITÉ:
• 1 extincteur / 200 m²
• Min 2 sorties de secours
• 1 détecteur / pièce
• Pièces max 50 m²
• Plan d'évacuation obligatoire
• 2 formations/an minimum

MATÉRIAUX À RISQUE:
• Bois et dérivés: risque élevé
• Métal/béton: risque faible
• Alertes spéciales si matériaux inflammables

Tu personnalises tes questions selon les réponses précédentes et donnes des conseils adaptés.
Tu validates soigneusement toutes les réponses et guide l'utilisateur en cas d'erreur."""
        
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            MessagesPlaceholder(variable_name="history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        
        self.chat_history = SimpleChatMessageHistory()
        chain = self.prompt | self.llm | StrOutputParser()
        
        self.conversation = RunnableWithMessageHistory(
            chain,
            lambda session_id: self.chat_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        
        self.audit_state = AuditState()
        self.greeting_sent = False
    
    def convert_history(self, history):
        messages = []
        for entry in history:
            if isinstance(entry, dict) and "role" in entry:
                if entry["role"] == "user":
                    messages.append(HumanMessage(content=entry["content"]))
                elif entry["role"] == "assistant":
                    messages.append(AIMessage(content=entry["content"]))
        
        self.chat_history.messages = messages
        return messages
    
    def complete_audit(self):
        try:
            # Validation finale des données
            self._final_validation()
            
            result = evaluate_audit(self.audit_state.data)
            
            return self.conversation.invoke(
                {"input": f"""
                ✅ AUDIT TERMINÉ pour {self.audit_state.data.get('buildingName', 'votre bâtiment')}
                
                📊 STATUT: {result.status}
                📋 RÉSULTAT: {result.message}
                
                🎯 RECOMMANDATIONS:
                {result.recommendations}
                
                Des questions sur ces résultats ? Je suis là pour vous aider ! 😊
                """},
                {"configurable": {"session_id": "audit_session"}}
            )
        except Exception as e:
            return f"❌ Erreur lors de l'analyse: {str(e)}. Voulez-vous recommencer l'audit ?"
    
    def _final_validation(self):
        """Validation finale de cohérence des données"""
        data = self.audit_state.data
        
        # Vérification cohérence superficies
        if "roomSizes" in data and "buildingSize" in data:
            total_rooms = sum(data["roomSizes"])
            if total_rooms > data["buildingSize"] * 1.5:  # Marge de 50%
                raise ValueError("Incohérence: superficie totale des pièces trop importante par rapport au bâtiment")
        
        # Vérification cohérence équipements/superficie
        if "fireExtinguishers" in data and "buildingSize" in data:
            required_extinguishers = max(1, data["buildingSize"] // 200)
            if data["fireExtinguishers"] == 0 and data["buildingSize"] > 50:
                raise ValueError("Aucun extincteur dans un bâtiment de cette taille est dangereux")
    
    def chat_fn(self, message, history):
        self.convert_history(history)
        
        # Message d'accueil uniquement au premier message
        if not self.greeting_sent and (not history or len(history) == 0):
            self.greeting_sent = True
            return "👋 Salut ! Je suis **Flaméo**, votre expert en sécurité incendie ! 🔥\n\nJe vais vous poser quelques questions pour auditer votre bâtiment et vous donner des recommandations personnalisées.\n\n" + AUDIT_QUESTIONS[0].text
        
        # Conversation libre après audit
        if self.audit_state.complete:
            return self.conversation.invoke(
                {"input": message},
                {"configurable": {"session_id": "audit_session"}}
            )
        
        # Traitement des questions d'audit
        current_question = self.audit_state.get_current_question()
        if not current_question:
            self.audit_state.complete = True
            return self.complete_audit()
        
        # Validation de la réponse avec gestion des avertissements
        is_valid, parsed_value, error_or_warning = self.audit_state.validate_answer(current_question, message)
        
        if not is_valid:
            return f"{error_or_warning}\n\nPouvez-vous reformuler votre réponse pour : {current_question.text}"
        
        # Stockage de la réponse
        self.audit_state.store_answer(current_question.key, parsed_value)
        
        # Enregistrement dans l'historique
        self.conversation.invoke(
            {"input": f"Q: {current_question.text}, R: {message}"},
            {"configurable": {"session_id": "audit_session"}}
        )
        
        # Construction de la réponse avec avertissement éventuel
        response = "✅ Parfait !"
        if error_or_warning and error_or_warning.startswith("⚠️"):
            response += f"\n\n{error_or_warning}"
        
        # Vérification de fin d'audit
        if self.audit_state.advance():
            return self.complete_audit()
        
        # Question suivante personnalisée
        next_question = self.audit_state.get_current_question()
        
        try:
            personalized = self.conversation.invoke(
                {"input": f"Pose la question suivante de manière personnalisée: {next_question.text}"},
                {"configurable": {"session_id": "audit_session"}}
            )
            return f"{response}\n\n{personalized}"
        except:
            return f"{response}\n\n{next_question.text}"

def create_modern_interface():
    chatbot = FlameoChatbot()
    
    # CSS moderne avec thème sombre et animations
    custom_css = """
    .gradio-container {
        max-width: 900px !important;
        margin: 0 auto !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 1rem;
    }
    .main-container {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        padding: 2rem;
        margin: auto;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        backdrop-filter: blur(10px);
        width: 100%;
        max-width: 800px;
    }
    .header-section {
        text-align: center;
        margin-bottom: 2rem;
        padding: 1rem;
        background: linear-gradient(45deg, #ff6b6b, #ee5a24);
        border-radius: 15px;
        color: white;
        box-shadow: 0 8px 16px rgba(238, 90, 36, 0.3);
    }
    .chat-container {
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin: 0 auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100%;
    }
    .chat-container > * {
        width: 100%;
        max-width: 100%;
    }
    .chat-container h2,
    .chat-container .gr-markdown h1,
    .chat-container .gr-markdown h2,
    .chat-container .gr-markdown h3 {
        color: #2c3e50 !important;
        font-weight: bold !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1) !important;
    }
    [data-testid="chatinterface-title"],
    .chatinterface-title,
    .chat-interface-title {
        color: #2c3e50 !important;
        font-weight: bold !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1) !important;
    }
    .chat-container * {
        color: inherit;
    }
    .chat-container h1, .chat-container h2, .chat-container h3, 
    .chat-container h4, .chat-container h5, .chat-container h6 {
        color: #2c3e50 !important;
    }
    .examples-container {
        margin-top: 1rem;
    }
    .example-btn {
        background: linear-gradient(45deg, #4ecdc4, #3498db) !important;
        border: none !important;
        color: white !important;
        border-radius: 20px !important;
        padding: 0.5rem 1rem !important;
        margin: 0.25rem !important;
        transition: all 0.3s ease !important;
    }
    .example-btn:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 5px 15px rgba(52, 152, 219, 0.4) !important;
    }
    .back-btn {
        background: linear-gradient(45deg, #95a5a6, #7f8c8d) !important;
        color: white !important;
        border: none !important;
        border-radius: 25px !important;
        padding: 0.75rem 1.5rem !important;
        margin-top: 1rem !important;
        transition: all 0.3s ease !important;
    }
    .back-btn:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 5px 15px rgba(127, 140, 141, 0.4) !important;
    }
    """
    
    with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
        with gr.Column(elem_classes="main-container"):
            with gr.Row(elem_classes="header-section"):
                gr.Markdown("""
                # 🔥 Flaméo - Expert Sécurité Incendie
                ### Audit intelligent et recommandations personnalisées
                *Votre partenaire pour une sécurité optimale*
                """)
            
            with gr.Column(elem_classes="chat-container"):
                chatbot_interface = gr.ChatInterface(
                    chatbot.chat_fn,
                    chatbot=gr.Chatbot(
                        height=500,
                        label="💬 Conversation avec Flaméo"
                    ),
                    examples=[
                        "Je voudrais auditer mon bureau de 150 m²",
                        "Combien d'extincteurs faut-il pour un entrepôt ?",
                        "Quelles sont les normes pour les détecteurs de fumée ?"
                    ],
                    title="🔥 Assistant Sécurité Incendie"
                )
            
            with gr.Row():
                gr.Button(
                    "⬅️ Retour à l'accueil", 
                    variant="secondary",
                    elem_classes="back-btn"
                ).click(
                    None, None, None,
                    js="() => { window.location.href='/'; }"
                )
    
    return demo

# Montage de l'interface
app = gr.mount_gradio_app(app, create_modern_interface(), path="/audit-bot")
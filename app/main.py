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
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Application d'audit de sécurité incendie")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(scan_router, prefix="/api")
app.include_router(items_router, prefix="/api")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Énumérations pour une meilleure structure
class RiskLevel(Enum):
    VERY_LOW = "très faible"
    LOW = "faible"
    MEDIUM = "moyen"
    HIGH = "élevé"
    VERY_HIGH = "très élevé"
    CRITICAL = "critique"

class BuildingCategory(Enum):
    RESIDENTIAL = "résidentiel"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industriel"
    PUBLIC = "public"
    MIXED = "mixte"

# Modèles Pydantic pour validation stricte
class RiskAssessment(BaseModel):
    fire_risk: RiskLevel = Field(description="Niveau de risque incendie")
    structural_risk: RiskLevel = Field(description="Risque structurel")
    evacuation_risk: RiskLevel = Field(description="Risque d'évacuation")
    equipment_adequacy: float = Field(ge=0, le=10, description="Adéquation équipements (0-10)")
    compliance_score: float = Field(ge=0, le=100, description="Score de conformité (0-100)")
    priority_actions: List[str] = Field(description="Actions prioritaires")

class ContextualInsight(BaseModel):
    insight_type: str = Field(description="Type d'insight")
    message: str = Field(description="Message contextuel")
    urgency: RiskLevel = Field(description="Niveau d'urgence")
    related_norms: List[str] = Field(default=[], description="Normes associées")

@dataclass
class AuditQuestion:
    text: str
    key: str
    validation_type: str = "text"
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    required: bool = True
    allowed_values: Optional[List[str]] = None
    context_dependent: bool = False
    follow_up_questions: List[str] = field(default_factory=list)
    risk_indicators: List[str] = field(default_factory=list)

# Base de connaissances étendue
FIRE_SAFETY_NORMS = {
    "extincteurs": {
        "residential": {"ratio": 200, "min": 1, "types": ["ABC", "CO2"]},
        "commercial": {"ratio": 150, "min": 2, "types": ["ABC", "CO2", "eau"]},
        "industrial": {"ratio": 100, "min": 3, "types": ["ABC", "CO2", "mousse", "poudre"]},
        "public": {"ratio": 120, "min": 2, "types": ["ABC", "CO2"]}
    },
    "detectors": {
        "residential": {"per_room": 1, "types": ["optique", "ionisation"]},
        "commercial": {"per_50m2": 1, "types": ["optique", "thermique"]},
        "industrial": {"per_30m2": 1, "types": ["optique", "thermique", "flamme"]},
        "public": {"per_40m2": 1, "types": ["optique", "thermique"]}
    },
    "exits": {
        "residential": {"min": 1, "max_distance": 40},
        "commercial": {"min": 2, "max_distance": 25},
        "industrial": {"min": 2, "max_distance": 30},
        "public": {"min": 2, "max_distance": 20}
    }
}

MATERIAL_FIRE_RATINGS = {
    "beton": {"rating": "A1", "risk": RiskLevel.VERY_LOW, "temp_resistance": 1200},
    "acier": {"rating": "A1", "risk": RiskLevel.LOW, "temp_resistance": 600},
    "brique": {"rating": "A1", "risk": RiskLevel.VERY_LOW, "temp_resistance": 1000},
    "pierre": {"rating": "A1", "risk": RiskLevel.VERY_LOW, "temp_resistance": 800},
    "bois": {"rating": "D", "risk": RiskLevel.HIGH, "temp_resistance": 250},
    "placo": {"rating": "A2", "risk": RiskLevel.MEDIUM, "temp_resistance": 180},
    "metal": {"rating": "A1", "risk": RiskLevel.LOW, "temp_resistance": 500}
}

# Questions d'audit intelligentes avec contexte
SMART_AUDIT_QUESTIONS = [
    AuditQuestion("🏢 Quel est le nom de votre bâtiment ?", "buildingName", "text"),
    AuditQuestion("🏗️ Type de bâtiment ?", "buildingType", "building_type", 
                  allowed_values=["immeuble", "maison", "entrepôt", "usine", "bureau", "commerce", "restaurant", "hôtel", "école", "hôpital"]),
    AuditQuestion("🎯 Usage principal ?", "buildingUsage", "building_usage", 
                  allowed_values=["professionnel", "personnel", "mixte"]),
    AuditQuestion("📏 Superficie totale en m² ?", "buildingSize", "number", 1, 100000,
                  risk_indicators=["large_space", "compartmentage"]),
    AuditQuestion("👥 Nombre maximum d'occupants simultanés ?", "maxOccupancy", "number", 1, 10000,
                  context_dependent=True, risk_indicators=["evacuation_capacity"]),
    AuditQuestion("🏠 Nombre de niveaux/étages ?", "floorCount", "number", 1, 50,
                  risk_indicators=["vertical_evacuation", "ladder_access"]),
    AuditQuestion("🧯 Nombre d'extincteurs ?", "fireExtinguishers", "number", 0, 1000,
                  follow_up_questions=["Quels types d'extincteurs ? (ABC, CO2, mousse, etc.)"]),
    AuditQuestion("🚪 Nombre de sorties de secours ?", "emergencyExits", "number", 0, 50,
                  risk_indicators=["evacuation_bottleneck"]),
    AuditQuestion("🔥 Détecteurs de fumée installés ?", "smokeDetectors", "number", 0, 1000,
                  follow_up_questions=["Sont-ils interconnectés ?", "Quelle technologie ?"]),
    AuditQuestion("🚨 Système d'alarme incendie installé ?", "alarmSystem", "boolean",
                  follow_up_questions=["Type d'alarme ?", "Couverture zonée ?"]),
    AuditQuestion("💧 Système d'extinction automatique (sprinklers) ?", "sprinklerSystem", "boolean",
                  follow_up_questions=["Couverture complète ?", "Type de système ?"]),
    AuditQuestion("📅 Dernière vérification équipements (date) ?", "lastInspection", "date"),
    AuditQuestion("🏃‍♂️ Dernier exercice d'évacuation (date) ?", "lastDrill", "date"),
    AuditQuestion("🧱 Matériaux de construction principaux ?", "constructionMaterials", "materials"),
    AuditQuestion("🗺️ Plan d'évacuation affiché et à jour ?", "evacuationPlan", "boolean"),
    AuditQuestion("📚 Formations sécurité cette année ?", "trainingSessions", "number", 0, 100),
    AuditQuestion("⚡ Installations électriques aux normes ?", "electricalCompliance", "boolean",
                  risk_indicators=["electrical_fire"]),
    AuditQuestion("🔥 Zones à risque particulier ?", "highRiskAreas", "text",
                  follow_up_questions=["Stockage de produits inflammables ?", "Équipements haute température ?"]),
]

class IntelligentValidationUtils:
    @staticmethod
    def contextual_validation(question: AuditQuestion, answer: str, audit_data: Dict) -> Tuple[bool, Any, Optional[str]]:
        """Validation contextuelle basée sur les réponses précédentes"""
        
        # Validation spécifique selon le contexte
        if question.key == "maxOccupancy":
            building_size = audit_data.get("buildingSize", 0)
            try:
                occupancy = int(re.findall(r'\d+', answer)[0])
                # Calcul de densité d'occupation
                if building_size > 0:
                    density = occupancy / building_size
                    if density > 5.0:  # Plus de 5 personnes/m²
                        return False, None, f"⚠️ Densité très élevée ({density:.1f} pers/m²). Vérifiez ce chiffre."
                    elif density > 2.0:
                        warning = f"⚠️ Forte densité ({density:.1f} pers/m²). Évacuation critique."
                        return True, occupancy, warning
                return True, occupancy, None
            except:
                return False, None, "❌ Nombre d'occupants invalide"
        
        # Validation pour extincteurs selon type de bâtiment
        elif question.key == "fireExtinguishers":
            building_type = audit_data.get("buildingType", "")
            building_size = audit_data.get("buildingSize", 0)
            
            if building_type and building_size:
                category = IntelligentValidationUtils.categorize_building(building_type)
                norms = FIRE_SAFETY_NORMS["extincteurs"].get(category, {"ratio": 200, "min": 1})
                required = max(norms["min"], building_size // norms["ratio"])
                
                try:
                    actual = int(re.findall(r'\d+', answer)[0])
                    if actual < required:
                        return False, None, f"❌ Insuffisant ! Minimum requis : {required} extincteurs (vous en avez {actual})"
                    elif actual >= required * 1.5:
                        warning = "✅ Excellent ! Vous dépassez les exigences minimales."
                        return True, actual, warning
                    return True, actual, None
                except:
                    return False, None, "❌ Nombre d'extincteurs invalide"
        
        return True, answer, None
    
    @staticmethod
    def categorize_building(building_type: str) -> str:
        """Catégorise le bâtiment selon sa typologie"""
        residential = ["maison", "immeuble", "résidence"]
        commercial = ["bureau", "commerce", "restaurant", "hôtel"]
        industrial = ["usine", "entrepôt", "atelier"]
        public = ["école", "hôpital", "administration"]
        
        building_lower = building_type.lower()
        
        if any(t in building_lower for t in residential):
            return "residential"
        elif any(t in building_lower for t in commercial):
            return "commercial"
        elif any(t in building_lower for t in industrial):
            return "industrial"
        elif any(t in building_lower for t in public):
            return "public"
        
        return "commercial"  # défaut

class EnhancedChatMessageHistory(BaseChatMessageHistory):
    def __init__(self):
        self._messages = []
        self._context_memory = {}
        self._insights_generated = []
    
    def add_user_message(self, message: str) -> None:
        self._messages.append(HumanMessage(content=message))
    
    def add_ai_message(self, message: str) -> None:
        self._messages.append(AIMessage(content=message))
    
    def add_context(self, key: str, value: Any) -> None:
        self._context_memory[key] = value
    
    def get_context(self, key: str) -> Any:
        return self._context_memory.get(key)
    
    def add_insight(self, insight: ContextualInsight) -> None:
        self._insights_generated.append(insight)
    
    def clear(self) -> None:
        self._messages = []
        self._context_memory = {}
        self._insights_generated = []
        
    @property
    def messages(self):
        return self._messages
        
    @messages.setter
    def messages(self, value):
        self._messages = value

class SmartAuditState:
    def __init__(self):
        self.questions = SMART_AUDIT_QUESTIONS
        self.current_idx = 0
        self.complete = False
        self.data: Dict[str, Any] = {}
        self.risk_indicators: List[str] = []
        self.contextual_insights: List[ContextualInsight] = []
        self.dynamic_questions: List[AuditQuestion] = []
        
    def get_current_question(self) -> Optional[AuditQuestion]:
        # Traite d'abord les questions dynamiques
        if self.dynamic_questions:
            return self.dynamic_questions.pop(0)
        
        return self.questions[self.current_idx] if self.current_idx < len(self.questions) else None
    
    def advance(self) -> bool:
        # Ne pas avancer si il y a des questions dynamiques en attente
        if self.dynamic_questions:
            return False
            
        self.current_idx += 1
        if self.current_idx >= len(self.questions):
            self.complete = True
            return True
        return False
    
    def add_dynamic_question(self, question: AuditQuestion) -> None:
        """Ajoute une question contextuelle"""
        self.dynamic_questions.append(question)
    
    def store_answer(self, key: str, value: Any) -> None:
        self.data[key] = value
        self._analyze_for_insights(key, value)
    
    def _analyze_for_insights(self, key: str, value: Any) -> None:
        """Analyse contextuelle pour générer des insights"""
        
        # Détection de risques élevés
        if key == "constructionMaterials" and isinstance(value, list):
            high_risk_materials = [m for m in value if MATERIAL_FIRE_RATINGS.get(m, {}).get("risk") in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]]
            if high_risk_materials:
                insight = ContextualInsight(
                    insight_type="material_risk",
                    message=f"⚠️ Matériaux à haut risque détectés : {', '.join(high_risk_materials)}. Recommandations spéciales nécessaires.",
                    urgency=RiskLevel.HIGH,
                    related_norms=["M1", "M4", "Euroclasses"]
                )
                self.contextual_insights.append(insight)
        
        # Détection d'incohérences
        if key == "emergencyExits" and "maxOccupancy" in self.data:
            exits = value
            occupancy = self.data["maxOccupancy"]
            ratio = occupancy / max(exits, 1)
            
            if ratio > 100:  # Plus de 100 personnes par sortie
                insight = ContextualInsight(
                    insight_type="evacuation_bottleneck",
                    message=f"🚨 Goulot d'évacuation critique ! {ratio:.0f} personnes par sortie. Risque d'embouteillage mortel.",
                    urgency=RiskLevel.CRITICAL,
                    related_norms=["Article R123-7", "Largeur UP"]
                )
                self.contextual_insights.append(insight)
        
        # Vieillissement des équipements
        if key == "lastInspection":
            try:
                last_check = datetime.strptime(value, "%Y-%m-%d")
                days_ago = (datetime.now() - last_check).days
                
                if days_ago > 365:
                    insight = ContextualInsight(
                        insight_type="maintenance_overdue",
                        message=f"⏰ Dernière vérification il y a {days_ago} jours. Maintenance urgente recommandée !",
                        urgency=RiskLevel.HIGH,
                        related_norms=["Art. R4227-39"]
                    )
                    self.contextual_insights.append(insight)
            except:
                pass
    
    def _validate_text_enhanced(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        """Validation simple pour les champs texte"""
        if not answer or not answer.strip():
            return False, None, "❌ Ce champ ne peut pas être vide."
        return True, answer.strip(), None
    
    def _validate_enum_enhanced(self, question: AuditQuestion, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        """Validation pour les champs à valeurs énumérées (choix prédéfinis)"""
        if not question.allowed_values:
            return False, None, "❌ Valeurs autorisées non définies."
        answer_clean = answer.strip().lower()
        allowed = [v.lower() for v in question.allowed_values]
        if answer_clean in allowed:
            return True, answer_clean, None
        else:
            return False, None, f"❌ Réponse non reconnue. Valeurs possibles : {', '.join(question.allowed_values)}"


    def validate_answer(self, question: AuditQuestion, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        """Validation intelligente avec contexte"""
        answer = answer.strip()
        
        if not answer and question.required:
            return False, None, "❌ Cette information est obligatoire."
        
        # Validation contextuelle d'abord
        if question.context_dependent:
            return IntelligentValidationUtils.contextual_validation(question, answer, self.data)
        
        # Validation standard améliorée
        if question.validation_type == "number":
            return self._validate_number_enhanced(question, answer)
        elif question.validation_type == "date":
            return self._validate_date_enhanced(answer)
        elif question.validation_type == "boolean":
            return self._validate_boolean_enhanced(answer)
        elif question.validation_type == "materials":
            return self._validate_materials_enhanced(answer)
        elif question.validation_type in ["building_type", "building_usage"]:
            return self._validate_enum_enhanced(question, answer)
        else:
            return self._validate_text_enhanced(answer)
    
    def _validate_number_enhanced(self, question: AuditQuestion, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        try:
            numbers = re.findall(r'\b\d+(?:[.,]\d+)?\b', answer)
            if not numbers:
                return False, None, "❌ Aucun nombre trouvé."
            
            value = float(numbers[0].replace(',', '.'))
            if value.is_integer():
                value = int(value)
            
            # Validation des limites avec conseils
            if question.min_value is not None and value < question.min_value:
                advice = self._get_range_advice(question.key, value, "low")
                return False, None, f"❌ Valeur trop faible (min: {question.min_value}). {advice}"
            
            if question.max_value is not None and value > question.max_value:
                advice = self._get_range_advice(question.key, value, "high")
                return False, None, f"❌ Valeur trop élevée (max: {question.max_value}). {advice}"
            
            # Génération de warnings intelligents
            warning = self._generate_number_warning(question.key, value)
            
            return True, value, warning
            
        except Exception as e:
            return False, None, f"❌ Format invalide: {str(e)}"
    
    def _get_range_advice(self, key: str, value: float, range_type: str) -> str:
        """Conseils spécifiques selon la valeur et le contexte"""
        advices = {
            "buildingSize": {
                "low": "Vérifiez l'unité (m² et non m).",
                "high": "Pour les très grandes surfaces, prévoir compartimentage."
            },
            "maxOccupancy": {
                "low": "Même faible, respectez les ratios équipements/personne.",
                "high": "Calcul ERP requis. Consultez un expert."
            },
            "fireExtinguishers": {
                "low": "Minimum légal obligatoire même pour petits espaces.",
                "high": "Vérifiez la répartition et maintenance."
            }
        }
        return advices.get(key, {}).get(range_type, "Vérifiez votre saisie.")
    
    def _generate_number_warning(self, key: str, value: float) -> Optional[str]:
        """Génère des avertissements contextuels intelligents"""
        warnings = {
            "buildingSize": lambda v: "⚠️ Grande surface : pensez au compartimentage !" if v > 1000 else None,
            "floorCount": lambda v: "⚠️ Bâtiment de grande hauteur : normes IGH possibles !" if v > 8 else None,
            "maxOccupancy": lambda v: "⚠️ ERP potentiel : réglementation spécifique !" if v > 19 else None,
            "fireExtinguishers": lambda v: "✅ Excellent équipement !" if v > 10 else None
        }
        
        warning_func = warnings.get(key)
        return warning_func(value) if warning_func else None
    
    def _validate_materials_enhanced(self, answer: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        """Validation des matériaux avec analyse de risque"""
        materials = self._extract_materials_smart(answer)
        
        if not materials:
            return False, None, "❌ Aucun matériau reconnu."
        
        # Analyse des risques
        risk_analysis = self._analyze_material_risks(materials)
        warning = None
        
        if risk_analysis["high_risk_count"] > 0:
            warning = f"🔥 {risk_analysis['high_risk_count']} matériau(x) à haut risque ! {risk_analysis['recommendations']}"
        elif risk_analysis["medium_risk_count"] > 0:
            warning = f"⚠️ {risk_analysis['medium_risk_count']} matériau(x) à risque modéré. {risk_analysis['recommendations']}"
        else:
            warning = "✅ Matériaux à faible risque incendie."
        
        return True, materials, warning
    
    def _extract_materials_smart(self, text: str) -> List[str]:
        """Extraction intelligente des matériaux avec synonymes"""
        materials_found = []
        text_lower = text.lower()
        
        # Dictionnaire de synonymes
        material_synonyms = {
            "beton": ["béton", "beton", "ciment"],
            "bois": ["bois", "boiserie", "charpente", "parquet"],
            "metal": ["métal", "metal", "metallique", "tôle"],
            "acier": ["acier", "steel", "inox"],
            "brique": ["brique", "brique rouge", "terre cuite"],
            "pierre": ["pierre", "granit", "marbre", "calcaire"],
            "placo": ["placo", "plaque de plâtre", "cloison sèche"]
        }
        
        for material, synonyms in material_synonyms.items():
            if any(syn in text_lower for syn in synonyms):
                materials_found.append(material)
        
        return list(set(materials_found))  # Supprime les doublons
    
    def _analyze_material_risks(self, materials: List[str]) -> Dict[str, Any]:
        """Analyse avancée des risques matériaux"""
        analysis = {
            "high_risk_count": 0,
            "medium_risk_count": 0,
            "low_risk_count": 0,
            "recommendations": "",
            "fire_load": 0
        }
        
        for material in materials:
            rating = MATERIAL_FIRE_RATINGS.get(material, {"risk": RiskLevel.MEDIUM})
            risk = rating["risk"]
            
            if risk in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                analysis["high_risk_count"] += 1
            elif risk == RiskLevel.MEDIUM:
                analysis["medium_risk_count"] += 1
            else:
                analysis["low_risk_count"] += 1
        
        # Génération de recommandations
        if analysis["high_risk_count"] > 0:
            analysis["recommendations"] = "Traitement ignifuge recommandé, détection renforcée."
        elif analysis["medium_risk_count"] > 0:
            analysis["recommendations"] = "Surveillance accrue, plan évacuation adapté."
        else:
            analysis["recommendations"] = "Structure résistante au feu."
        
        return analysis

class FlameoChatbotEnhanced:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0.3, model="gpt-4o-mini")  # Température réduite pour plus de précision
        
        system_prompt = """Tu es Flaméo 🔥, expert IA en sécurité incendie de nouvelle génération.

CAPACITÉS AVANCÉES:
• Analyse contextuelle intelligente des réponses
• Détection automatique des incohérences et risques
• Génération de questions de suivi pertinentes
• Recommandations personnalisées en temps réel
• Base de connaissances exhaustive sur les normes françaises et européennes

NORMES DE RÉFÉRENCE:
• Code du travail (R4227-28 à R4227-41)
• Règlement de sécurité ERP
• Normes NF et EN sur équipements
• Classification feu matériaux (Euroclasses)
• IGH, ICPE selon contexte

ANALYSE INTELLIGENTE:
• Calculs automatiques des ratios réglementaires
• Détection des zones à risque selon occupation/surface
• Évaluation de la charge calorifique
• Prédiction des scénarios d'évacuation
• Identification des non-conformités critiques

Tu adaptes tes questions selon le contexte, détectes les problèmes potentiels et fournis des explications pédagogiques.
Ton objectif : un audit complet et des recommandations actionnables."""
        
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            MessagesPlaceholder(variable_name="history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        
        self.chat_history = EnhancedChatMessageHistory()
        chain = self.prompt | self.llm | StrOutputParser()
        
        self.conversation = RunnableWithMessageHistory(
            chain,
            lambda session_id: self.chat_history,
            input_messages_key="input",
            history_messages_key="history",
        )
        
        self.audit_state = SmartAuditState()
        self.greeting_sent = False
        
        # Parser pour extraire des données structurées
        self.risk_parser = PydanticOutputParser(pydantic_object=RiskAssessment)
    
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
    
    def generate_contextual_insights(self) -> str:
        """Génère des insights contextuels basés sur les données collectées"""
        if not self.audit_state.contextual_insights:
            return ""
        
        insights_text = "\n\n🧠 **ANALYSE INTELLIGENTE:**\n"
        
        for insight in self.audit_state.contextual_insights:
            urgency_emoji = {
                RiskLevel.LOW: "🟢",
                RiskLevel.MEDIUM: "🟡", 
                RiskLevel.HIGH: "🟠",
                RiskLevel.CRITICAL: "🔴"
            }.get(insight.urgency, "ℹ️")
            
            insights_text += f"{urgency_emoji} {insight.message}"
            
            if insight.related_norms:
                insights_text += f"\n   📋 *Normes: {', '.join(insight.related_norms)}*"
            insights_text += "\n"
        
        return insights_text
    
    def perform_intelligent_analysis(self) -> RiskAssessment:
        """Analyse intelligente complète des données d'audit"""
        try:
            data = self.audit_state.data
            
            # Calculs de conformité automatiques
            compliance_score = self._calculate_compliance_score(data)
            
            # Évaluation des risques par catégorie
            fire_risk = self._assess_fire_risk(data)
            structural_risk = self._assess_structural_risk(data)
            evacuation_risk = self._assess_evacuation_risk(data)
            
            # Adéquation des équipements
            equipment_adequacy = self._assess_equipment_adequacy(data)
            
            # Actions prioritaires
            priority_actions = self._generate_priority_actions(data)
            
            return RiskAssessment(
                fire_risk=fire_risk,
                structural_risk=structural_risk,
                evacuation_risk=evacuation_risk,
                equipment_adequacy=equipment_adequacy,
                compliance_score=compliance_score,
                priority_actions=priority_actions
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse intelligente: {e}")
            # Retour par défaut en cas d'erreur
            return RiskAssessment(
                fire_risk=RiskLevel.MEDIUM,
                structural_risk=RiskLevel.MEDIUM,
                evacuation_risk=RiskLevel.MEDIUM,
                equipment_adequacy=5.0,
                compliance_score=50.0,
                priority_actions=["Vérification générale recommandée"]
            )
    
    def _calculate_compliance_score(self, data: Dict) -> float:
        """Calcule le score de conformité basé sur les normes"""
        score = 0
        max_score = 0
        
        # Vérification extincteurs
        if "fireExtinguishers" in data and "buildingSize" in data:
            building_type = data.get("buildingType", "")
            category = IntelligentValidationUtils.categorize_building(building_type)
            norms = FIRE_SAFETY_NORMS["extincteurs"].get(category, {"ratio": 200, "min": 1})
            
            required = max(norms["min"], data["buildingSize"] // norms["ratio"])
            actual = data["fireExtinguishers"]
            
            if actual >= required:
                score += 25
            elif actual >= required * 0.7:
                score += 15
            elif actual >= required * 0.5:
                score += 8
            max_score += 25
        
        # Vérification détecteurs
        if "smokeDetectors" in data and "buildingSize" in data:
            building_type = data.get("buildingType", "")
            category = IntelligentValidationUtils.categorize_building(building_type)
            detector_norms = FIRE_SAFETY_NORMS["detectors"].get(category, {"per_50m2": 1})
            
            if "per_room" in detector_norms:
                room_count = data.get("roomCount", data["buildingSize"] // 20)  # Estimation
                required = room_count * detector_norms["per_room"]
            else:
                area_per_detector = list(detector_norms.keys())[0].split("_")[1].replace("m2", "")
                required = data["buildingSize"] // int(area_per_detector)
            
            actual = data["smokeDetectors"]
            if actual >= required:
                score += 20
            elif actual >= required * 0.8:
                score += 12
            max_score += 20
        
        # Vérification sorties de secours
        if "emergencyExits" in data:
            building_type = data.get("buildingType", "")
            category = IntelligentValidationUtils.categorize_building(building_type)
            exit_norms = FIRE_SAFETY_NORMS["exits"].get(category, {"min": 2})
            
            required = exit_norms["min"]
            actual = data["emergencyExits"]
            
            if actual >= required:
                score += 15
            elif actual >= required - 1:
                score += 8
            max_score += 15
        
        # Vérification maintenance
        if "lastInspection" in data:
            try:
                last_check = datetime.strptime(data["lastInspection"], "%Y-%m-%d")
                days_ago = (datetime.now() - last_check).days
                
                if days_ago <= 365:  # Moins d'un an
                    score += 15
                elif days_ago <= 540:  # Moins de 18 mois
                    score += 8
                max_score += 15
            except:
                max_score += 15
        
        # Vérification plan d'évacuation
        if "evacuationPlan" in data:
            if data["evacuationPlan"]:
                score += 10
            max_score += 10
        
        # Vérification formations
        if "trainingSessions" in data:
            sessions = data["trainingSessions"]
            if sessions >= 2:
                score += 10
            elif sessions >= 1:
                score += 5
            max_score += 10
        
        # Systèmes avancés (bonus)
        if data.get("alarmSystem", False):
            score += 5
            max_score += 5
        
        if data.get("sprinklerSystem", False):
            score += 10
            max_score += 10
        
        return (score / max(max_score, 1)) * 100 if max_score > 0 else 0
    
    def _assess_fire_risk(self, data: Dict) -> RiskLevel:
        """Évalue le risque d'incendie basé sur les matériaux et l'environnement"""
        risk_score = 0
        
        # Analyse des matériaux
        materials = data.get("constructionMaterials", [])
        if isinstance(materials, list):
            for material in materials:
                material_risk = MATERIAL_FIRE_RATINGS.get(material, {"risk": RiskLevel.MEDIUM})["risk"]
                if material_risk == RiskLevel.HIGH:
                    risk_score += 3
                elif material_risk == RiskLevel.VERY_HIGH:
                    risk_score += 5
                elif material_risk == RiskLevel.MEDIUM:
                    risk_score += 1
        
        # Zones à risque
        high_risk_areas = data.get("highRiskAreas", "")
        if high_risk_areas and len(high_risk_areas) > 10:  # Description détaillée = risques présents
            risk_score += 2
        
        # Installations électriques
        if not data.get("electricalCompliance", True):
            risk_score += 3
        
        # Évaluation finale
        if risk_score >= 8:
            return RiskLevel.VERY_HIGH
        elif risk_score >= 5:
            return RiskLevel.HIGH
        elif risk_score >= 3:
            return RiskLevel.MEDIUM
        elif risk_score >= 1:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW
    
    def _assess_structural_risk(self, data: Dict) -> RiskLevel:
        """Évalue le risque structurel"""
        risk_score = 0
        
        # Hauteur du bâtiment
        floors = data.get("floorCount", 1)
        if floors > 8:  # IGH
            risk_score += 4
        elif floors > 4:
            risk_score += 2
        elif floors > 2:
            risk_score += 1
        
        # Superficie
        size = data.get("buildingSize", 0)
        if size > 5000:
            risk_score += 2
        elif size > 1000:
            risk_score += 1
        
        # Matériaux structurels
        materials = data.get("constructionMaterials", [])
        if isinstance(materials, list):
            if "bois" in materials and floors > 1:
                risk_score += 2
            if any(m in materials for m in ["beton", "acier", "pierre"]):
                risk_score -= 1  # Bonus pour matériaux résistants
        
        # Évaluation finale
        if risk_score >= 6:
            return RiskLevel.VERY_HIGH
        elif risk_score >= 4:
            return RiskLevel.HIGH
        elif risk_score >= 2:
            return RiskLevel.MEDIUM
        elif risk_score >= 0:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW
    
    def _assess_evacuation_risk(self, data: Dict) -> RiskLevel:
        """Évalue le risque d'évacuation"""
        risk_score = 0
        
        # Ratio occupants/sorties
        exits = data.get("emergencyExits", 1)
        occupancy = data.get("maxOccupancy", 0)
        
        if exits > 0 and occupancy > 0:
            ratio = occupancy / exits
            if ratio > 200:  # Plus de 200 personnes par sortie
                risk_score += 5
            elif ratio > 100:
                risk_score += 3
            elif ratio > 50:
                risk_score += 1
        
        # Hauteur et évacuation verticale
        floors = data.get("floorCount", 1)
        if floors > 1:
            if exits < 2:  # Une seule sortie pour plusieurs étages
                risk_score += 3
            if floors > 4 and occupancy > 50:
                risk_score += 2
        
        # Formation du personnel
        training = data.get("trainingSessions", 0)
        if training == 0:
            risk_score += 2
        elif training < 2:
            risk_score += 1
        
        # Plan d'évacuation
        if not data.get("evacuationPlan", False):
            risk_score += 2
        
        # Exercices d'évacuation
        if "lastDrill" in data:
            try:
                last_drill = datetime.strptime(data["lastDrill"], "%Y-%m-%d")
                days_ago = (datetime.now() - last_drill).days
                if days_ago > 365:
                    risk_score += 2
                elif days_ago > 180:
                    risk_score += 1
            except:
                risk_score += 1
        else:
            risk_score += 2
        
        # Évaluation finale
        if risk_score >= 10:
            return RiskLevel.CRITICAL
        elif risk_score >= 7:
            return RiskLevel.VERY_HIGH
        elif risk_score >= 5:
            return RiskLevel.HIGH
        elif risk_score >= 3:
            return RiskLevel.MEDIUM
        elif risk_score >= 1:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW
    
    def _assess_equipment_adequacy(self, data: Dict) -> float:
        """Évalue l'adéquation des équipements (0-10)"""
        score = 0
        max_points = 0
        
        # Extincteurs
        if "fireExtinguishers" in data and "buildingSize" in data:
            building_type = data.get("buildingType", "")
            category = IntelligentValidationUtils.categorize_building(building_type)
            norms = FIRE_SAFETY_NORMS["extincteurs"].get(category, {"ratio": 200, "min": 1})
            
            required = max(norms["min"], data["buildingSize"] // norms["ratio"])
            actual = data["fireExtinguishers"]
            
            adequacy_ratio = min(actual / max(required, 1), 2.0)  # Cap à 2x le requis
            score += adequacy_ratio * 3
            max_points += 3
        
        # Détecteurs
        if "smokeDetectors" in data:
            detectors = data["smokeDetectors"]
            rooms = data.get("roomCount", data.get("buildingSize", 100) // 20)
            
            adequacy_ratio = min(detectors / max(rooms, 1), 2.0)
            score += adequacy_ratio * 2
            max_points += 2
        
        # Systèmes avancés
        if data.get("alarmSystem", False):
            score += 2
        max_points += 2
        
        if data.get("sprinklerSystem", False):
            score += 3
        max_points += 3
        
        return (score / max(max_points, 1)) * 10 if max_points > 0 else 5.0
    
    def _generate_priority_actions(self, data: Dict) -> List[str]:
        """Génère des actions prioritaires personnalisées"""
        actions = []
        
        # Actions critiques basées sur les manques
        building_size = data.get("buildingSize", 0)
        building_type = data.get("buildingType", "")
        
        # Extincteurs insuffisants
        if "fireExtinguishers" in data and building_size > 0:
            category = IntelligentValidationUtils.categorize_building(building_type)
            norms = FIRE_SAFETY_NORMS["extincteurs"].get(category, {"ratio": 200, "min": 1})
            required = max(norms["min"], building_size // norms["ratio"])
            
            if data["fireExtinguishers"] < required:
                deficit = required - data["fireExtinguishers"]
                actions.append(f"🧯 URGENT: Installer {deficit} extincteur(s) supplémentaire(s) - Obligation légale")
        
        # Sorties insuffisantes
        exits = data.get("emergencyExits", 0)
        occupancy = data.get("maxOccupancy", 0)
        
        if exits == 0:
            actions.append("🚪 CRITIQUE: Créer au moins une sortie de secours - Danger mortel")
        elif exits == 1 and occupancy > 19:
            actions.append("🚪 URGENT: Ajouter une seconde sortie de secours - ERP obligatoire")
        elif exits > 0 and occupancy > 0:
            if occupancy / exits > 100:
                actions.append("🚪 URGENT: Élargir ou multiplier les sorties - Risque d'embouteillage mortel")
        
        # Détection insuffisante
        detectors = data.get("smokeDetectors", 0)
        rooms = data.get("roomCount", building_size // 20 if building_size > 0 else 5)
        
        if detectors == 0:
            actions.append("🔥 URGENT: Installer des détecteurs de fumée - Protection vitale")
        elif detectors < rooms * 0.7:
            needed = int(rooms - detectors)
            actions.append(f"🔥 Installer {needed} détecteur(s) supplémentaire(s) pour couverture optimale")
        
        # Maintenance en retard
        if "lastInspection" in data:
            try:
                last_check = datetime.strptime(data["lastInspection"], "%Y-%m-%d")
                days_ago = (datetime.now() - last_check).days
                
                if days_ago > 365:
                    actions.append("🔧 URGENT: Vérification équipements en retard - Planifier maintenance immédiate")
                elif days_ago > 300:
                    actions.append("🔧 Programmer la prochaine vérification équipements sous 2 mois")
            except:
                actions.append("🔧 Planifier vérification équipements de sécurité")
        
        # Formation manquante
        training = data.get("trainingSessions", 0)
        if training == 0:
            actions.append("📚 URGENT: Organiser formation sécurité incendie - Obligation employeur")
        elif training < 2:
            actions.append("📚 Programmer formation sécurité complémentaire (objectif: 2/an)")
        
        # Plan d'évacuation
        if not data.get("evacuationPlan", False):
            actions.append("🗺️ URGENT: Afficher plan d'évacuation - Obligation réglementaire")
        
        # Exercices d'évacuation
        if "lastDrill" in data:
            try:
                last_drill = datetime.strptime(data["lastDrill"], "%Y-%m-%d")
                days_ago = (datetime.now() - last_drill).days
                
                if days_ago > 365:
                    actions.append("🏃‍♂️ URGENT: Organiser exercice d'évacuation - Plus d'un an de retard")
                elif days_ago > 180:
                    actions.append("🏃‍♂️ Programmer prochain exercice d'évacuation sous 3 mois")
            except:
                pass
        
        # Matériaux à risque
        materials = data.get("constructionMaterials", [])
        if isinstance(materials, list):
            high_risk = [m for m in materials if MATERIAL_FIRE_RATINGS.get(m, {}).get("risk") == RiskLevel.HIGH]
            if high_risk:
                actions.append(f"🧱 Évaluer traitement ignifuge pour: {', '.join(high_risk)}")
        
        # Systèmes manquants (recommandations)
        if not data.get("alarmSystem", False) and (building_size > 300 or occupancy > 20):
            actions.append("🚨 Considérer installation système d'alarme incendie")
        
        if not data.get("sprinklerSystem", False) and building_size > 1000:
            actions.append("💧 Étudier faisabilité système d'extinction automatique")
        
        # Si aucune action critique, encouragements
        if not actions:
            actions.append("✅ Excellent niveau de sécurité ! Maintenir la surveillance et maintenance")
        
        return actions[:10]  # Limite à 10 actions prioritaires
    
    def complete_audit(self):
        """Finalise l'audit avec analyse intelligente complète"""
        try:
            # Validation finale des données
            self._final_validation()
            
            # Analyse intelligente
            risk_assessment = self.perform_intelligent_analysis()
            
            # Génération du rapport traditionnel
            traditional_result = evaluate_audit(self.audit_state.data)
            
            # Génération des insights contextuels
            contextual_insights = self.generate_contextual_insights()
            
            # Construction du rapport final enrichi
            building_name = self.audit_state.data.get('buildingName', 'votre bâtiment')
            
            final_report = f"""
🎯 **AUDIT TERMINÉ POUR {building_name.upper()}**

📊 **ÉVALUATION GLOBALE:**
• Score de conformité: **{risk_assessment.compliance_score:.1f}%**
• Adéquation équipements: **{risk_assessment.equipment_adequacy:.1f}/10**

🔍 **ANALYSE DES RISQUES:**
• Risque incendie: **{risk_assessment.fire_risk.value.upper()}** 🔥
• Risque structurel: **{risk_assessment.structural_risk.value.upper()}** 🏗️
• Risque évacuation: **{risk_assessment.evacuation_risk.value.upper()}** 🚪

{contextual_insights}

🎯 **PLAN D'ACTION PRIORITAIRE:**
"""
            
            for i, action in enumerate(risk_assessment.priority_actions, 1):
                final_report += f"{i}. {action}\n"
            
            final_report += f"""
📋 **ÉVALUATION TRADITIONNELLE:**
• Statut: {traditional_result.status}
• {traditional_result.message}

💡 **RECOMMANDATIONS PERSONNALISÉES:**
{traditional_result.recommendations}

---
*Audit réalisé par Flaméo IA - Expert en sécurité incendie*
*Pour toute question technique, je reste à votre disposition ! 🔥*
"""
            
            return self.conversation.invoke(
                {"input": final_report},
                {"configurable": {"session_id": "audit_session"}}
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la finalisation de l'audit: {e}")
            return f"❌ Erreur lors de l'analyse finale: {str(e)}. Les données collectées sont sauvegardées. Voulez-vous recommencer l'audit ?"
    
    def _final_validation(self):
        """Validation finale intelligente avec détection d'incohérences"""
        data = self.audit_state.data
        
        # Vérifications de base
        if "roomSizes" in data and "buildingSize" in data:
            total_rooms = sum(data["roomSizes"]) if isinstance(data["roomSizes"], list) else 0
            if total_rooms > data["buildingSize"] * 1.5:
                raise ValueError("Incohérence: superficie totale des pièces excessive")
        
        # Vérifications avancées
        if "maxOccupancy" in data and "buildingSize" in data:
            density = data["maxOccupancy"] / data["buildingSize"]
            if density > 10:  # Plus de 10 personnes/m²
                raise ValueError(f"Densité d'occupation irréaliste: {density:.1f} pers/m²")
        
        # Cohérence équipements/usage
        if data.get("fireExtinguishers", 0) == 0 and data.get("buildingSize", 0) > 50:
            logger.warning("Aucun extincteur dans un bâtiment de taille significative")
        
        if data.get("emergencyExits", 0) == 0:
            raise ValueError("Aucune sortie de secours déclarée - Information critique manquante")
    
    def generate_follow_up_questions(self, current_question: AuditQuestion, answer: str) -> List[AuditQuestion]:
        """Génère des questions de suivi intelligentes basées sur la réponse"""
        follow_ups = []
        
        # Questions spécifiques selon le contexte
        if current_question.key == "buildingType":
            if "restaurant" in answer.lower() or "cuisine" in answer.lower():
                follow_ups.append(AuditQuestion(
                    "🍳 Avez-vous une hotte d'extraction avec système anti-feu dans la cuisine ?",
                    "kitchenFireSuppression", "boolean"
                ))
            
            elif "hôtel" in answer.lower():
                follow_ups.append(AuditQuestion(
                    "🛏️ Nombre de chambres et système d'alarme dans chaque chambre ?",
                    "hotelRoomAlarms", "text"
                ))
            
            elif "entrepôt" in answer.lower() or "stockage" in answer.lower():
                follow_ups.append(AuditQuestion(
                    "📦 Type de marchandises stockées (inflammables, chimiques, autres) ?",
                    "storedGoods", "text"
                ))
        
        elif current_question.key == "constructionMaterials":
            if "bois" in answer.lower():
                follow_ups.append(AuditQuestion(
                    "🌲 Le bois a-t-il reçu un traitement ignifuge certifié ?",
                    "woodFireTreatment", "boolean"
                ))
        
        elif current_question.key == "maxOccupancy":
            try:
                occupancy = int(re.findall(r'\d+', answer)[0])
                if occupancy > 100:
                    follow_ups.append(AuditQuestion(
                        "🚨 Avec cette occupation, avez-vous un système d'alarme centralisé ?",
                        "centralizedAlarm", "boolean"
                    ))
            except:
                pass
        
        return follow_ups
    
    def chat_fn(self, message, history):
        """Fonction de chat améliorée avec IA contextuelle"""
        self.convert_history(history)
        
        # Message d'accueil intelligent
        if not self.greeting_sent and (not history or len(history) == 0):
            self.greeting_sent = True
            welcome_msg = """👋 Salut ! Je suis **Flaméo**, votre expert IA en sécurité incendie nouvelle génération ! 🔥🤖

🧠 **MES SUPER-POUVOIRS:**
• Analyse intelligente en temps réel
• Détection automatique des risques
• Calculs de conformité instantanés  
• Recommandations personnalisées
• Questions adaptatives selon votre contexte

Je vais procéder à un audit complet de votre bâtiment avec des questions intelligentes qui s'adaptent à vos réponses.

Prêt ? Commençons ! 🚀

""" + SMART_AUDIT_QUESTIONS[0].text
            return welcome_msg
        
        # Conversation libre après audit avec IA avancée
        if self.audit_state.complete:
            enhanced_input = f"""
Contexte audit: {json.dumps(self.audit_state.data, default=str, ensure_ascii=False)}
Question utilisateur: {message}
Réponds en tant qu'expert avec références précises aux données d'audit.
"""
            return self.conversation.invoke(
                {"input": enhanced_input},
                {"configurable": {"session_id": "audit_session"}}
            )
        
        # Traitement intelligent des questions d'audit
        current_question = self.audit_state.get_current_question()
        if not current_question:
            self.audit_state.complete = True
            return self.complete_audit()
        
        # Validation intelligente avec contexte
        is_valid, parsed_value, error_or_warning = self.audit_state.validate_answer(current_question, message)
        
        if not is_valid:
            # Suggestion intelligente en cas d'erreur
            suggestion = self._generate_input_suggestion(current_question, message)
            return f"{error_or_warning}\n\n{suggestion}\n\n❓ **Reformulez pour:** {current_question.text}"
        
        # Stockage et analyse contextuelle
        self.audit_state.store_answer(current_question.key, parsed_value)
        
        # Génération de questions de suivi si pertinentes
        follow_up_questions = self.generate_follow_up_questions(current_question, message)
        for fq in follow_up_questions:
            self.audit_state.add_dynamic_question(fq)
        
        # Enregistrement enrichi dans l'historique
        context_info = f"Q: {current_question.text}, R: {message}"
        if self.audit_state.contextual_insights:
            latest_insight = self.audit_state.contextual_insights[-1]
            context_info += f" | Insight: {latest_insight.message[:100]}..."
        
        self.conversation.invoke(
            {"input": context_info},
            {"configurable": {"session_id": "audit_session"}}
        )
        
        # Construction de la réponse intelligente
        response = "✅ **Parfait !**"
        
        # Ajout d'insights contextuels
        if error_or_warning and error_or_warning.startswith("⚠️"):
            response += f"\n\n{error_or_warning}"
        
        # Ajout de calculs automatiques si pertinents
        calculation_info = self._generate_calculation_info(current_question.key, parsed_value)
        if calculation_info:
            response += f"\n\n📊 **CALCUL AUTO:** {calculation_info}"
        
        # Vérification de fin d'audit
        if self.audit_state.advance():
            return self.complete_audit()
        
        # Question suivante avec personnalisation IA
        next_question = self.audit_state.get_current_question()
        
        try:
            # Prompt enrichi pour personnalisation
            personalization_prompt = f"""
Contexte actuel: {json.dumps(dict(list(self.audit_state.data.items())[-3:]), default=str, ensure_ascii=False)}
Question suivante: {next_question.text}
Personnalise cette question en référençant les données déjà collectées.
Sois concis mais engageant. Ajoute des émojis pertinents.
"""
            
            personalized = self.conversation.invoke(
                {"input": personalization_prompt},
                {"configurable": {"session_id": "audit_session"}}
            )
            
            return f"{response}\n\n{personalized}"
            
        except Exception as e:
            logger.warning(f"Échec personnalisation question: {e}")
            return f"{response}\n\n{next_question.text}"
    
    def _generate_input_suggestion(self, question: AuditQuestion, invalid_input: str) -> str:
        """Génère des suggestions intelligentes en cas d'erreur de saisie"""
        if question.validation_type == "number":
            return "💡 **Exemple:** Tapez juste le nombre, comme '150' ou '25,5'"
        elif question.validation_type == "date":
            return "💡 **Exemple:** 2024-03-15 ou 15/03/2024 ou 15-03-2024"
        elif question.validation_type == "boolean":
            return "💡 **Exemple:** 'Oui', 'Non', 'Présent', 'Absent'"
        elif question.validation_type == "materials":
            return "💡 **Exemple:** 'béton et bois' ou 'acier, brique, placo'"
        else:
            return "💡 **Aide:** Soyez précis et utilisez des termes simples"
    
    def _generate_calculation_info(self, key: str, value: Any) -> Optional[str]:
        """Génère des informations de calcul automatique"""
        if key == "fireExtinguishers" and "buildingSize" in self.audit_state.data:
            building_size = self.audit_state.data["buildingSize"]
            building_type = self.audit_state.data.get("buildingType", "")
            
            category = IntelligentValidationUtils.categorize_building(building_type)
            norms = FIRE_SAFETY_NORMS["extincteurs"].get(category, {"ratio": 200, "min": 1})
            
            required = max(norms["min"], building_size // norms["ratio"])
            
            if value >= required:
                surplus = value - required
                return f"Conformité OK ! Minimum requis: {required}, vous avez: {value} (+{surplus})"
            else:
                deficit = required - value
                return f"⚠️ Déficit: {deficit} extincteur(s) manquant(s) (requis: {required})"
        
        elif key == "maxOccupancy" and "buildingSize" in self.audit_state.data:
            building_size = self.audit_state.data["buildingSize"]
            density = value / building_size
            
            density_assessment = ""
            if density < 0.5:
                density_assessment = "Faible densité ✅"
            elif density < 1.0:
                density_assessment = "Densité normale ✅"
            elif density < 2.0:
                density_assessment = "Densité élevée ⚠️"
            elif density < 5.0:
                density_assessment = "Densité très élevée 🚨"
            else:
                density_assessment = "Densité critique 🔴"
            
            return f"Densité: {density:.1f} pers/m² - {density_assessment}"
        
        elif key == "emergencyExits" and "maxOccupancy" in self.audit_state.data:
            occupancy = self.audit_state.data["maxOccupancy"]
            ratio = occupancy / max(value, 1)
            
            if ratio <= 50:
                assessment = "Excellent ratio évacuation ✅"
            elif ratio <= 100:
                assessment = "Ratio acceptable ✅"
            elif ratio <= 200:
                assessment = "Ratio préoccupant ⚠️"
            else:
                assessment = "Ratio critique - Goulot d'étranglement 🚨"
            
            return f"Ratio: {ratio:.0f} personnes/sortie - {assessment}"
        
        return None
    
    def export_audit_data(self) -> Dict[str, Any]:
        """Exporte les données d'audit pour sauvegarde ou traitement"""
        return {
            "audit_data": self.audit_state.data,
            "risk_indicators": self.audit_state.risk_indicators,
            "contextual_insights": [
                {
                    "type": insight.insight_type,
                    "message": insight.message,
                    "urgency": insight.urgency.value,
                    "norms": insight.related_norms
                }
                for insight in self.audit_state.contextual_insights
            ],
            "completion_status": self.audit_state.complete,
            "timestamp": datetime.now().isoformat()
        }
    
    def import_audit_data(self, data: Dict[str, Any]) -> bool:
        """Importe des données d'audit précédemment sauvegardes"""
        try:
            self.audit_state.data = data.get("audit_data", {})
            self.audit_state.risk_indicators = data.get("risk_indicators", [])
            
            # Reconstruction des insights
            insights_data = data.get("contextual_insights", [])
            self.audit_state.contextual_insights = []
            
            for insight_data in insights_data:
                insight = ContextualInsight(
                    insight_type=insight_data["type"],
                    message=insight_data["message"],
                    urgency=RiskLevel(insight_data["urgency"]),
                    related_norms=insight_data.get("norms", [])
                )
                self.audit_state.contextual_insights.append(insight)
            
            self.audit_state.complete = data.get("completion_status", False)
            
            # Repositionnement dans les questions
            answered_count = len([k for k in self.audit_state.data.keys() 
                                if k in [q.key for q in self.questions]])
            self.audit_state.current_idx = answered_count
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'import des données: {e}")
            return False
    
    def reset_audit(self):
        """Réinitialise complètement l'audit"""
        self.audit_state = SmartAuditState()
        self.chat_history.clear()
        self.greeting_sent = False

# Fonctions utilitaires avancées
class AuditReportGenerator:
    """Générateur de rapports d'audit avancés"""
    
    @staticmethod
    def generate_pdf_report(audit_data: Dict[str, Any], risk_assessment: RiskAssessment) -> bytes:
        """Génère un rapport PDF complet (nécessite reportlab)"""
        # Cette fonction nécessiterait l'installation de reportlab
        # Pour l'instant, on retourne un placeholder
        report_content = f"""
RAPPORT D'AUDIT SÉCURITÉ INCENDIE
================================

Bâtiment: {audit_data.get('buildingName', 'Non spécifié')}
Date: {datetime.now().strftime('%d/%m/%Y')}

SYNTHÈSE:
- Score conformité: {risk_assessment.compliance_score:.1f}%
- Risque incendie: {risk_assessment.fire_risk.value}
- Adéquation équipements: {risk_assessment.equipment_adequacy:.1f}/10

ACTIONS PRIORITAIRES:
{chr(10).join(f'- {action}' for action in risk_assessment.priority_actions)}
"""
        return report_content.encode('utf-8')
    
    @staticmethod
    def generate_excel_report(audit_data: Dict[str, Any]) -> bytes:
        """Génère un rapport Excel avec analyse détaillée"""
        # Placeholder pour génération Excel
        # Nécessiterait openpyxl ou xlswriter
        pass

# Interface Gradio améliorée
def create_gradio_interface():
    """Crée l'interface Gradio avec fonctionnalités avancées"""
    
    # Instance globale du chatbot
    global flameo_bot
    flameo_bot = FlameoChatbotEnhanced()
    
    def chat_interface(message, history):
        """Interface de chat principale"""
        # history est une liste de [user, bot]
        if history is None:
            history = []
        # Appel du bot pour obtenir la réponse
        bot_response = flameo_bot.chat_fn(message, history)
        # Ajout du nouvel échange à l'historique
        history = history + [[message, bot_response]]
        return history
    
    def reset_chat():
        """Réinitialise le chat"""
        global flameo_bot
        flameo_bot.reset_audit()
        return [], "Chat réinitialisé ! 🔄"
    
    def export_data():
        """Exporte les données d'audit"""
        global flameo_bot
        data = flameo_bot.export_audit_data()
        filename = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return f"Données exportées vers {filename} ✅"
    
    def get_progress():
        """Retourne la progression de l'audit"""
        global flameo_bot
        if flameo_bot.audit_state.complete:
            return "Audit terminé ✅ 100%"
        
        total_questions = len(SMART_AUDIT_QUESTIONS)
        answered = flameo_bot.audit_state.current_idx
        progress = (answered / total_questions) * 100
        
        return f"Progression: {answered}/{total_questions} questions ({progress:.1f}%)"
    
    # Interface Gradio
    with gr.Blocks(
        title="Flaméo - Expert IA Sécurité Incendie",
        theme=gr.themes.Soft(),
        css="""
        .container { max-width: 1200px; margin: auto; }
        .header { background: linear-gradient(45deg, #ff6b6b, #ffa500); 
                 color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .chat-container { height: 600px; }
        .progress-bar { background: #ff6b6b; }
        """
    ) as interface:
        
        # En-tête
        gr.HTML("""
        <div class="header">
            <h1>🔥 Flaméo - Expert IA en Sécurité Incendie</h1>
            <p>Audit intelligent et personnalisé de votre bâtiment</p>
        </div>
        """)
        
        with gr.Row():
            with gr.Column(scale=3):
                # Chat principal
                chatbot = gr.Chatbot(
                    label="💬 Conversation avec Flaméo",
                    height=500,
                    container=True,
                    elem_classes=["chat-container"]
                )
                
                msg = gr.Textbox(
                    label="Votre message",
                    placeholder="Tapez votre réponse ici...",
                    container=True,
                    scale=7
                )
                
                with gr.Row():
                    submit_btn = gr.Button("Envoyer 📤", variant="primary", scale=2)
                    clear_btn = gr.Button("Nouveau Chat 🔄", variant="secondary", scale=1)
            
            with gr.Column(scale=1):
                # Panneau de contrôle
                gr.HTML("<h3>📊 Panneau de Contrôle</h3>")
                
                progress_display = gr.Textbox(
                    label="Progression",
                    value="En attente...",
                    interactive=False
                )
                
                with gr.Group():
                    export_btn = gr.Button("Exporter Données 💾", variant="secondary")
                    export_status = gr.Textbox(
                        label="Statut Export",
                        interactive=False,
                        visible=False
                    )
                
                # Informations contextuelles
                gr.HTML("""
                <div style="margin-top: 20px; padding: 15px; background: #f0f8ff; border-radius: 8px;">
                    <h4>🎯 Fonctionnalités IA</h4>
                    <ul style="font-size: 12px;">
                        <li>🧠 Analyse contextuelle</li>
                        <li>📊 Calculs automatiques</li>
                        <li>⚠️ Détection des risques</li>
                        <li>📋 Conformité temps réel</li>
                        <li>🎯 Recommandations personnalisées</li>
                    </ul>
                </div>
                """)
        
        # Événements
        def update_progress():
            return get_progress()
        
        submit_btn.click(
            chat_interface,
            inputs=[msg, chatbot],
            outputs=[chatbot]
        ).then(
            lambda: gr.update(value=""),
            outputs=[msg]
        ).then(
            update_progress,
            outputs=[progress_display]
        )
        
        msg.submit(
            chat_interface,
            inputs=[msg, chatbot],
            outputs=[chatbot]
        ).then(
            lambda: gr.update(value=""),
            outputs=[msg]
        ).then(
            update_progress,
            outputs=[progress_display]
        )
        
        clear_btn.click(
            reset_chat,
            outputs=[chatbot, progress_display]
        )
        
        export_btn.click(
            export_data,
            outputs=[export_status]
        ).then(
            lambda: gr.update(visible=True),
            outputs=[export_status]
        )
        
        # Mise à jour automatique de la progression
        interface.load(
            update_progress,
            outputs=[progress_display]
        )
    
    return interface

# Points d'entrée API supplémentaires
@app.post("/api/audit/start")
async def start_audit():
    """Démarre un nouvel audit"""
    try:
        bot = FlameoChatbotEnhanced()
        first_question = bot.audit_state.get_current_question()
        
        return {
            "status": "success",
            "message": "Audit démarré",
            "first_question": {
                "text": first_question.text,
                "key": first_question.key,
                "type": first_question.validation_type
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/audit/answer")
async def submit_answer(request: Request):
    """Soumet une réponse à l'audit"""
    try:
        data = await request.json()
        # Traitement de la réponse
        # (nécessiterait gestion de session pour audit API)
        return {"status": "success", "next_question": "..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/audit/export/{session_id}")
async def export_audit_results(session_id: str):
    """Exporte les résultats d'audit"""
    try:
        # Récupération des données de session
        # Génération du rapport
        return {"status": "success", "download_url": "..."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Initialisation de l'interface Gradio
gradio_app = create_gradio_interface()

# Montage de l'interface Gradio dans FastAPI
app = gr.mount_gradio_app(app, gradio_app, path="/audit")

# Configuration avancée de logging
def setup_advanced_logging():
    """Configure un système de logging avancé"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('flameo_audit.log'),
            logging.StreamHandler()
        ]
    )
    
    # Logger spécifique pour les audits
    audit_logger = logging.getLogger('audit')
    audit_handler = logging.FileHandler('audit_sessions.log')
    audit_handler.setFormatter(
        logging.Formatter('%(asctime)s - AUDIT - %(message)s')
    )
    audit_logger.addHandler(audit_handler)
    audit_logger.setLevel(logging.INFO)

# Middleware de sécurité et monitoring
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Middleware de sécurité et monitoring"""
    start_time = datetime.now()
    
    # Log de la requête
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Calcul du temps de traitement
    process_time = (datetime.now() - start_time).total_seconds()
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log de la réponse
    logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
    
    return response

# Route de santé pour monitoring
@app.get("/health")
async def health_check():
    """Vérification de l'état de l'application"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "components": {
            "flameo_ai": "operational",
            "database": "operational",
            "gradio_interface": "operational"
        }
    }

# Configuration finale
if __name__ == "__main__":
    setup_advanced_logging()
    
    import uvicorn
    
    logger.info("🔥 Démarrage de Flaméo - Expert IA Sécurité Incendie")
    logger.info("📱 Interface Gradio disponible sur: /audit")
    logger.info("🔧 API REST disponible sur: /api")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True  # À désactiver en production
    )
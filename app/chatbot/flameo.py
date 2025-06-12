from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers.items import router as items_router
from app.services.audit_service import evaluate_audit
from app.models.schemas import RiskAssessment

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

from app.chatbot.audit_state import SmartAuditState

load_dotenv()

class EnhancedChatMessageHistory(BaseChatMessageHistory):
    def __init__(self):
        self.messages = []

    def add_message(self, message):
        self.messages.append(message)

    def clear(self):
        self.messages = []

class FlameoChatbotEnhanced:
    def __init__(self):
        self.llm = ChatOpenAI(temperature=0.3, model="gpt-4o-mini")
        
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
• Évaluation de la charge calorique
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
        try:
            data = self.audit_state.data
            
            compliance_score = self._calculate_compliance_score(data)
            fire_risk = self._assess_fire_risk(data)
            structural_risk = self._assess_structural_risk(data)
            evacuation_risk = self._assess_evacuation_risk(data)
            equipment_adequacy = self._assess_equipment_adequacy(data)
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
            return RiskAssessment(
                fire_risk=RiskLevel.MEDIUM,
                structural_risk=RiskLevel.MEDIUM,
                evacuation_risk=RiskLevel.MEDIUM,
                equipment_adequacy=5.0,
                compliance_score=50.0,
                priority_actions=["Vérification générale recommandée"]
            )
    
    def complete_audit(self):
        try:
            self._final_validation()
            risk_assessment = self.perform_intelligent_analysis()
            traditional_result = evaluate_audit(self.audit_state.data)
            contextual_insights = self.generate_contextual_insights()
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
        data = self.audit_state.data
        
        if "roomSizes" in data and "buildingSize" in data:
            total_rooms = sum(data["roomSizes"]) if isinstance(data["roomSizes"], list) else 0
            if total_rooms > data["buildingSize"] * 1.5:
                raise ValueError("Incohérence: superficie totale des pièces excessive")
        
        if "maxOccupancy" in data and "buildingSize" in data:
            density = data["maxOccupancy"] / data["buildingSize"]
            if density > 10:
                raise ValueError(f"Densité d'occupation irréaliste: {density:.1f} pers/m²")
        
        if data.get("fireExtinguishers", 0) == 0 and data.get("buildingSize", 0) > 50:
            logger.warning("Aucun extincteur dans un bâtiment de taille significative")
        
        if data.get("emergencyExits", 0) == 0:
            raise ValueError("Aucune sortie de secours déclarée - Information critique manquante")
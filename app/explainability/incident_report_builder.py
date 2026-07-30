from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

# Dans ton vrai code, tu importeras ces classes depuis leurs fichiers respectifs
# from .explanation_engine import Explanation
# from .recommendation_engine import Recommendation

@dataclass
class IncidentReport:
    """Document structuré représentant un incident complet, expliqué et actionnable."""
    plant: str
    date: datetime
    priority: str
    confidence: float
    diagnosis: str
    triggered_rules: List[str]
    feature_values: Dict[str, Any]
    explanation: str
    recommendation: List[str]
    status: str

    def to_dict(self) -> dict:
        """Prêt à être envoyé à une API frontend ou sauvegardé en BDD (JSON)."""
        return {
            "plant": self.plant,
            "date": self.date.isoformat(),
            "priority": self.priority,
            "confidence": self.confidence,
            "diagnosis": self.diagnosis,
            "triggered_rules": self.triggered_rules,
            "feature_values": self.feature_values,
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "status": self.status
        }

    def to_markdown(self) -> str:
        """Génère un rapport texte lisible (idéal pour un email automatique ou un ticket JIRA/Zendesk)."""
        rules_str = "\n".join([f"  {r}" for r in self.triggered_rules])
        features_str = "\n".join([f"  - {k}: {v}" for k, v in self.feature_values.items()])
        reco_str = "\n".join([f"  {i+1}. {r}" for i, r in enumerate(self.recommendation)])
        
        return f"""
 **RAPPORT D'INCIDENT : {self.plant}** 
=========================================
**Date**        : {self.date.strftime('%Y-%m-%d %H:%M:%S')}
**Statut**      : {self.status}
**Priorité**    : {self.priority}
**Diagnostic**  : {self.diagnosis}
**Confiance**   : {self.confidence * 100:.0f}%

 **EXPLICATION**
-----------------------------------------
{self.explanation}

**Règles déclenchées :**
{rules_str}

**Contexte des données (Preuves) :**
{features_str}

 **PLAN D'ACTION RECOMMANDÉ**
-----------------------------------------
{reco_str}
=========================================
"""


class IncidentReportBuilder:
    """
    Assemble les différentes parties évaluées par le système 
    pour générer un rapport d'incident complet.
    """

    def build_report(
        self,
        plant_name: str,
        detection_date: datetime,
        diagnosis: str,
        explanation,     # Type: Explanation
        recommendation,  # Type: Recommendation
        status: str = "OPEN"
    ) -> IncidentReport:
        """
        Construit l'objet IncidentReport final.
        Remarque : La 'priority' est astucieusement déduite de la 'severity' 
        renvoyée par le RecommendationEngine.
        """
        
        return IncidentReport(
            plant=plant_name,
            date=detection_date,
            priority=recommendation.severity,  # Hérité de la Knowledge Base
            confidence=explanation.confidence,
            diagnosis=diagnosis,
            triggered_rules=explanation.triggered_rules,
            feature_values=explanation.evidence,
            explanation=explanation.reasoning,
            recommendation=recommendation.actions,
            status=status
        )
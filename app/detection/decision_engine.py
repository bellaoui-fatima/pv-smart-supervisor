"""
Module du Moteur de Décision (Decision Engine).
Chef d'orchestre global du pipeline de détection et d'explicabilité.
Il orchestre séquentiellement :
1. Détection : RulesEngine, ScoringEngine, PriorityEngine, DiagnosisEngine
2. Explicabilité : ExplanationEngine, RecommendationEngine, IncidentReportBuilder
"""

from typing import Dict, Any, Optional
from datetime import datetime

# Ancien pipeline (Détection)
from app.detection.rules_engine import RulesEngine
from app.detection.scoring_engine import ScoringEngine
from app.detection.priority_engine import PriorityEngine
from app.detection.diagnosis_engine import DiagnosisEngine

# Nouveau pipeline Milestone 3.5 (Explicabilité & Rapportation)
from app.explainability.explanation_engine import ExplanationEngine
from app.explainability.recommendation_engine import RecommendationEngine
from app.explainability.incident_report_builder import IncidentReportBuilder, IncidentReport

from app.utils.logger import logger


class DecisionEngine:
    """Orchestrateur principal de la détection et de l'explicabilité métier."""

    def __init__(self) -> None:
        # Briques de détection brute
        self.rules_engine = RulesEngine()
        self.scoring_engine = ScoringEngine()
        self.priority_engine = PriorityEngine()
        self.diagnosis_engine = DiagnosisEngine()

        # Briques d'explicabilité (Milestone 3.5)
        self.explanation_engine = ExplanationEngine()
        self.recommendation_engine = RecommendationEngine()
        self.incident_report_builder = IncidentReportBuilder()

    def evaluate(
        self, 
        plant_id: int, 
        features: Dict[str, Any], 
        plant_name: Optional[str] = None
    ) -> Optional[IncidentReport]:
        """
        Évalue un vecteur de features pour une centrale donnée, applique le pipeline 
        d'explicabilité et retourne un rapport d'incident complet si nécessaire.

        :param plant_id: Identifiant unique de la centrale.
        :param features: Dictionnaire de variables du jour (issues du Feature Store).
        :param plant_name: Nom lisible de la centrale (optionnel pour l'affichage).
        :return: Instance d'IncidentReport s'il y a des anomalies, sinon None.
        """
        display_name = plant_name or f"Centrale #{plant_id}"
        logger.info(f"DecisionEngine: Évaluation des features en cours pour {display_name}...")

        # ---------------------------------------------------------------------
        # PHASE 1 : DÉTECTION & DIAGNOSTIC
        # ---------------------------------------------------------------------

        # 1. Évaluation brute des règles métier
        rule_evaluations = self.rules_engine.evaluate_all(features)

        # 2. Agrégation et calcul du score de confiance
        score_result = self.scoring_engine.calculate_score(rule_evaluations)

        # Si aucune règle ne s'est déclenchée, le site est sain
        if not score_result.has_anomalies:
            logger.info(f"DecisionEngine: Site sain. Aucune anomalie pour {display_name}.")
            return None

        # 3. Détermination de la priorité d'impact
        priority = self.priority_engine.evaluate(score_result)

        # 4. Déduction du diagnostic technique (ex: "production_anomaly", "offline_inverter")
        diagnosis = self.diagnosis_engine.evaluate(score_result)
        diagnosis_key = getattr(diagnosis, "code", str(diagnosis))

        # ---------------------------------------------------------------------
        # PHASE 2 : EXPLICABILITÉ & RECOMMANDATION (Milestone 3.5)
        # ---------------------------------------------------------------------

        # Extraction des noms des règles effectivement déclenchées
        triggered_rule_names = [
            rule.rule_name for rule in rule_evaluations 
            if getattr(rule, "is_triggered", False) or getattr(rule, "triggered", False)
        ]

        # 5. Génération de l'explication compréhensible pour un opérateur
        explanation = self.explanation_engine.generate_explanation(
            diagnosis=diagnosis_key,
            feature_vector=features,
            evaluated_rules=triggered_rule_names,
            score_result=getattr(score_result, "score", 0.90)
        )

        # 6. Extraction du plan d'action (Recommandations métiers)
        recommendation = self.recommendation_engine.generate_recommendation(
            diagnosis=diagnosis_key,
            context=features  # Permet d'injecter du contexte dynamique (ex: {equipment_id})
        )

        # ---------------------------------------------------------------------
        # PHASE 3 : ASSEMBLAGE DU RAPPORT
        # ---------------------------------------------------------------------

        # 7. Création du rapport enrichi final
        incident_report = self.incident_report_builder.build_report(
            plant_name=display_name,
            detection_date=datetime.now(),
            diagnosis=diagnosis_key,
            explanation=explanation,
            recommendation=recommendation,
            status="OPEN"
        )

        logger.warning(
            f"DecisionEngine: Nouvel incident enrichi pour {display_name} -> "
            f"Priorité: [{incident_report.priority}] | "
            f"Diagnostic: {incident_report.diagnosis} | "
            f"Confiance: {incident_report.confidence * 100:.0f}%"
        )

        return incident_report
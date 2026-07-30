"""
Module du Moteur de Diagnostic (Diagnosis Engine).
Croise le résultat du Moteur de Règles avec la Base de Connaissances Experte
pour générer un diagnostic qualifié et explicable (XAI).
"""

from typing import List, Optional
from app.models.domain import ScoreResult, Diagnosis
from app.detection.diagnosis_rules import EXPERT_KNOWLEDGE_BASE, ExpertRule
from app.utils.logger import logger


class DiagnosisEngine:
    """Générateur de diagnostics et d'explicabilité (XAI)."""

    def __init__(self) -> None:
        self.knowledge_base = EXPERT_KNOWLEDGE_BASE

    def evaluate(self, score_result: ScoreResult) -> Diagnosis:
        """
        Analyse les règles déclenchées pour déterminer le diagnostic le plus pertinent.
        Construit un texte d'explicabilité pour la transparence de la décision.
        """
        triggered_codes = set(score_result.get_triggered_codes())
        
        # 1. Recherche d'une correspondance dans la base experte
        matched_rule = self._find_best_match(triggered_codes)

        # 2. Définition des éléments du diagnostic
        if matched_rule:
            title = matched_rule.title
            incident_type = matched_rule.incident_type
            root_cause = matched_rule.root_cause
            action = matched_rule.recommended_action
        else:
            # Fallback générique si aucune combinaison experte n'est reconnue
            title = "Anomalie de production ou de performance détectée"
            incident_type = "General Anomaly"
            root_cause = "Dégradation multifactorielle non cataloguée (Combinaison d'écarts mineurs)."
            action = "Analyse approfondie requise via le dashboard de supervision de la centrale."

        # 3. Génération de l'explicabilité (XAI)
        summary_text = self._generate_explanation(score_result, title)

        logger.info(f"DiagnosisEngine: Diagnostic généré -> {incident_type} | {title}")

        return Diagnosis(
            title=title,
            incident_type=incident_type,
            root_cause=root_cause,
            recommended_action=action,
            affected_components=self._extract_components(score_result),
            summary_text=summary_text
        )

    def _find_best_match(self, triggered_codes: set) -> Optional[ExpertRule]:
        """Trouve la première règle experte correspondant exactement à la signature d'anomalies."""
        for rule in self.knowledge_base:
            # Vérifier que tous les required_codes sont présents
            if not all(req in triggered_codes for req in rule.required_codes):
                continue
            
            # Vérifier qu'aucun excluded_codes n'est présent
            if any(exc in triggered_codes for exc in rule.excluded_codes):
                continue
                
            return rule
            
        return None

    def _generate_explanation(self, score_result: ScoreResult, title: str) -> str:
        """Génère un résumé explicable naturel (XAI) justifiant la décision de l'IA."""
        if not score_result.triggered_rules:
            return "Aucune anomalie mathématique détectée."

        lines = [
            f"L'IA a diagnostiqué : '{title}' avec un niveau de confiance de {score_result.confidence_score}%.",
            "Ce constat est basé sur les observations suivantes :"
        ]

        for rule in score_result.triggered_rules:
            # Ajout des descriptions spécifiques de chaque règle déclenchée
            lines.append(f"- {rule.rule_name} (Poids: {rule.weight}) : {rule.description}")

        return "\n".join(lines)

    def _extract_components(self, score_result: ScoreResult) -> List[str]:
        """Extrait la liste des équipements concernés selon les règles."""
        components = set()
        codes = score_result.get_triggered_codes()
        
        if "R01_COMM_LOSS" in codes:
            components.add("Datalogger / Routeur")
        if any(c in codes for c in ["R05_INVERTER_FAILURE", "R02_TOTAL_SHUTDOWN"]):
            components.add("Onduleurs")
        if "R06_STRING_FAILURE" in codes:
            components.add("Chaînes / Strings")
        if any(c in codes for c in ["R03_MAJOR_PR_DROP", "R04_MINOR_PR_DROP", "R08_DRIFT_DETECTION", "R07_WEATHER_ANOMALY"]):
            components.add("Modules PV (Panneaux)")
            
        return list(components)
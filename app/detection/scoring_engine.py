"""
Module du Moteur de Scoring.
Agrège les résultats du RulesEngine, normalise le score global,
calcule l'indice de confiance et qualifie le niveau de priorité.
"""

from typing import List, Optional, Tuple
from app.config.detection_config import DETECTION_CONFIG, DetectionConfig
from app.models.domain import RuleEvaluation, ScoreResult, Priority
from app.utils.logger import logger


class ScoringEngine:
    """Moteur de centralisation du scoring et qualification de priorité."""

    def __init__(self, config: Optional[DetectionConfig] = None) -> None:
        self.config = config or DETECTION_CONFIG

    def calculate_score(self, rule_evaluations: List[RuleEvaluation]) -> ScoreResult:
        """
        Calcule le score global d'incident et l'indice de confiance
        à partir de la liste des évaluations de règles.
        
        :param rule_evaluations: Liste des RuleEvaluation produites par le RulesEngine
        :return: Objet ScoreResult structuré
        """
        triggered = [r for r in rule_evaluations if r.is_triggered]
        raw_score = sum(r.score for r in triggered)
        max_possible_score = self.config.MAX_TOTAL_SCORE

        # Normalisation plafonnée à MAX_TOTAL_SCORE (100.0)
        normalized_score = min(raw_score, max_possible_score)

        # Calcul de la confiance en fonction de la complétude des données évaluées
        total_rules = len(rule_evaluations)
        evaluated_valid = sum(1 for r in rule_evaluations if r.details and not any(v is None for v in r.details.values()))
        
        completeness_ratio = (evaluated_valid / total_rules) if total_rules > 0 else 1.0
        confidence_score = round(self.config.CONFIDENCE_BASE_PERCENT * completeness_ratio, 1)

        result = ScoreResult(
            total_score=normalized_score,
            max_score=max_possible_score,
            confidence_score=confidence_score,
            triggered_rules=triggered,
            evaluated_rules=rule_evaluations
        )

        logger.info(
            f"ScoringEngine: Score global = {normalized_score}/{max_possible_score} | "
            f"Règles déclenchées = {len(triggered)}/{total_rules} | Confiance = {confidence_score}%"
        )
        return result

    def determine_priority(self, score_result: ScoreResult) -> Priority:
        """
        Détermine la priorité de l'incident en fonction des seuils de score
        et de la nature spécifique de certaines règles (Override critique).
        
        :param score_result: Objet ScoreResult calculé
        :return: Enum Priority (CRITICAL, HIGH, MEDIUM, LOW, INFO)
        """
        triggered_codes = score_result.get_triggered_codes()
        score = score_result.total_score
        p_thresholds = self.config.priority_thresholds

        # 1. Override Métier : Arrêt total ou Perte de com = Priorité Élevée/Critique immédiate
        if "R02_TOTAL_SHUTDOWN" in triggered_codes or "R01_COMM_LOSS" in triggered_codes:
            if score >= p_thresholds.CRITICAL_SCORE or "R02_TOTAL_SHUTDOWN" in triggered_codes:
                return Priority.CRITICAL
            return Priority.HIGH

        # 2. Qualification basée sur le Score Cumulé
        if score >= p_thresholds.CRITICAL_SCORE:
            return Priority.CRITICAL
        elif score >= p_thresholds.HIGH_SCORE:
            return Priority.HIGH
        elif score >= p_thresholds.MEDIUM_SCORE:
            return Priority.MEDIUM
        elif score >= p_thresholds.LOW_SCORE:
            return Priority.LOW
        
        return Priority.INFO
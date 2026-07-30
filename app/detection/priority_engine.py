"""
Module du Moteur de Priorité (Priority Engine).
Isole la logique complexe d'attribution des priorités d'un incident en croisant
le score mathématique et des matrices d'impact opérationnel (Overrides).
"""

from typing import Optional
from app.config.detection_config import DETECTION_CONFIG, DetectionConfig
from app.models.domain import ScoreResult, Priority
from app.utils.logger import logger


class PriorityEngine:
    """Moteur dédié à la qualification de la sévérité et de la priorité d'un incident."""

    def __init__(self, config: Optional[DetectionConfig] = None) -> None:
        self.config = config or DETECTION_CONFIG

    def evaluate(self, score_result: ScoreResult) -> Priority:
        """
        Évalue la priorité finale en appliquant les seuils de score et les 
        règles d'escalade automatique (Overrides).
        """
        triggered_codes = score_result.get_triggered_codes()
        score = score_result.total_score
        thresholds = self.config.priority_thresholds

        # 1. Règles d'Escalade Automatique (Overrides Opérationnels)
        # Un arrêt total de la centrale est toujours critique, peu importe le score cumulé.
        if "R02_TOTAL_SHUTDOWN" in triggered_codes:
            logger.info("PriorityEngine: Escalade CRITICAL déclenchée (Arrêt Total).")
            return Priority.CRITICAL

        # Une perte de communication masque la visibilité, priorité haute immédiate.
        if "R01_COMM_LOSS" in triggered_codes:
            if score >= thresholds.CRITICAL_SCORE:
                return Priority.CRITICAL
            logger.info("PriorityEngine: Escalade HIGH déclenchée (Perte de Com).")
            return Priority.HIGH

        # 2. Évaluation Standard par Score
        if score >= thresholds.CRITICAL_SCORE:
            return Priority.CRITICAL
        if score >= thresholds.HIGH_SCORE:
            return Priority.HIGH
        if score >= thresholds.MEDIUM_SCORE:
            return Priority.MEDIUM
        if score >= thresholds.LOW_SCORE:
            return Priority.LOW
        
        return Priority.INFO
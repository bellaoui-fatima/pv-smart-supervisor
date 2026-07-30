"""
Module du Moteur de Règles (Rules Engine).
Évalue mathématiquement les métriques photovoltaïques par rapport aux seuils
définis pour détecter les anomalies et pannes.
"""

from typing import Dict, Any, List, Optional
import math
from app.config.detection_config import DETECTION_CONFIG, DetectionConfig
from app.models.domain import RuleEvaluation
from app.utils.logger import logger


class RulesEngine:
    """Évaluateur déterministe des règles métier photovoltaïques."""

    def __init__(self, config: Optional[DetectionConfig] = None) -> None:
        self.config = config or DETECTION_CONFIG

    def evaluate_all(self, features: Dict[str, Any]) -> List[RuleEvaluation]:
        """
        Exécute l'ensemble des règles métier sur un vecteur de features.
        
        :param features: Dictionnaire de features (issuance du FeatureStore ou DailyMeasure)
        :return: Liste des évaluations individuelles de chaque règle.
        """
        evaluations: List[RuleEvaluation] = []

        evaluations.append(self._eval_comm_loss(features))
        evaluations.append(self._eval_total_shutdown(features))
        evaluations.extend(self._eval_pr_drops(features))
        evaluations.append(self._eval_inverter_failures(features))
        evaluations.append(self._eval_string_failures(features))
        evaluations.append(self._eval_weather_anomaly(features))
        evaluations.append(self._eval_drift_detection(features))

        return evaluations

    # --- Règles Individuelles ---

    def _eval_comm_loss(self, features: Dict[str, Any]) -> RuleEvaluation:
        """R01 : Perte totale de communication avec la centrale."""
        comm_status = features.get("communication_status")
        # Si communication_status est explicitement False
        is_triggered = comm_status is False or comm_status == 0
        weight = self.config.weights.COMMUNICATION_LOSS

        return RuleEvaluation(
            rule_code="R01_COMM_LOSS",
            rule_name="Perte de Télécommunication",
            is_triggered=bool(is_triggered),
            score=weight if is_triggered else 0.0,
            weight=weight,
            description="La centrale ne transmet plus de données de communication.",
            details={"communication_status": comm_status}
        )

    def _eval_total_shutdown(self, features: Dict[str, Any]) -> RuleEvaluation:
        """R02 : Arrêt total de production malgré un ensoleillement suffisant."""
        prod = features.get("production")
        irrad = features.get("irradiation", 0.0) or 0.0
        
        min_irrad = self.config.thresholds.IRRADIANCE_MIN_KW_M2
        is_triggered = False
        
        if irrad >= min_irrad and prod is not None and prod <= 0.01:
            is_triggered = True

        weight = self.config.weights.TOTAL_PLANT_SHUTDOWN

        return RuleEvaluation(
            rule_code="R02_TOTAL_SHUTDOWN",
            rule_name="Arrêt Total de Production",
            is_triggered=is_triggered,
            score=weight if is_triggered else 0.0,
            weight=weight,
            description=f"Production nulle ({prod} kWh) avec irradiation adéquate ({irrad} kW/m²).",
            details={"production": prod, "irradiation": irrad, "min_irradiance_threshold": min_irrad}
        )

    def _eval_pr_drops(self, features: Dict[str, Any]) -> List[RuleEvaluation]:
        """R03 & R04 : Chutes majeure ou modérée du Performance Ratio (PR)."""
        pr = features.get("performance_ratio")
        pr_crit = self.config.thresholds.PR_CRITICAL
        pr_warn = self.config.thresholds.PR_WARNING

        r_major_triggered = False
        r_minor_triggered = False

        if pr is not None:
            if pr < pr_crit:
                r_major_triggered = True
            elif pr < pr_warn:
                r_minor_triggered = True

        w_major = self.config.weights.MAJOR_PR_DROP
        w_minor = self.config.weights.MINOR_PR_DROP

        return [
            RuleEvaluation(
                rule_code="R03_MAJOR_PR_DROP",
                rule_name="Chute Majeure du PR",
                is_triggered=r_major_triggered,
                score=w_major if r_major_triggered else 0.0,
                weight=w_major,
                description=f"Performance Ratio sous le seuil critique ({pr:.2f} < {pr_crit})." if pr is not None else "PR non disponible.",
                details={"performance_ratio": pr, "critical_threshold": pr_crit}
            ),
            RuleEvaluation(
                rule_code="R04_MINOR_PR_DROP",
                rule_name="Chute Modérée du PR",
                is_triggered=r_minor_triggered,
                score=w_minor if r_minor_triggered else 0.0,
                weight=w_minor,
                description=f"Performance Ratio sous le seuil d'avertissement ({pr:.2f} < {pr_warn})." if pr is not None else "PR non disponible.",
                details={"performance_ratio": pr, "warning_threshold": pr_warn}
            )
        ]

    def _eval_inverter_failures(self, features: Dict[str, Any]) -> RuleEvaluation:
        """R05 : Onduleurs déconnectés ou en panne."""
        offline_inv = features.get("offline_inverters") or 0
        is_triggered = offline_inv > 0
        weight = self.config.weights.INVERTER_FAILURE

        return RuleEvaluation(
            rule_code="R05_INVERTER_FAILURE",
            rule_name="Panne d'Onduleur",
            is_triggered=is_triggered,
            score=weight if is_triggered else 0.0,
            weight=weight,
            description=f"{offline_inv} onduleur(s) détécté(s) hors-ligne ou défaillant(s).",
            details={"offline_inverters": offline_inv}
        )

    def _eval_string_failures(self, features: Dict[str, Any]) -> RuleEvaluation:
        """R06 : Chaînes de panneaux (strings) défaillantes."""
        failed_strings = features.get("failed_strings") or 0
        threshold = self.config.thresholds.FAILED_STRINGS_THRESHOLD
        is_triggered = failed_strings >= threshold
        weight = self.config.weights.STRING_FAILURE

        return RuleEvaluation(
            rule_code="R06_STRING_FAILURE",
            rule_name="Défaillance de Chaînes/Strings",
            is_triggered=is_triggered,
            score=weight if is_triggered else 0.0,
            weight=weight,
            description=f"{failed_strings} chaîne(s) défaillante(s) (Seuil >= {threshold}).",
            details={"failed_strings": failed_strings, "threshold": threshold}
        )

    def _eval_weather_anomaly(self, features: Dict[str, Any]) -> RuleEvaluation:
        """R07 : Incohérence entre conditions météo et production (ex: surchauffe majeure)."""
        temp_gap = features.get("temperature_gap") or 0.0
        irrad_ratio = features.get("irradiation_ratio") or 1.0
        max_temp_gap = self.config.thresholds.TEMP_GAP_MAX_CELSIUS

        # Anomalie si écart de température excessif avec bon ensoleillement
        is_triggered = temp_gap > max_temp_gap and irrad_ratio > 0.8
        weight = self.config.weights.WEATHER_ANOMALY

        return RuleEvaluation(
            rule_code="R07_WEATHER_ANOMALY",
            rule_name="Anomalie Météo / Température",
            is_triggered=is_triggered,
            score=weight if is_triggered else 0.0,
            weight=weight,
            description=f"Écart de température anormal ({temp_gap:.1f}°C > {max_temp_gap}°C).",
            details={"temperature_gap": temp_gap, "irradiation_ratio": irrad_ratio}
        )

    def _eval_drift_detection(self, features: Dict[str, Any]) -> RuleEvaluation:
        """R08 : Dérive progressive de production détectée sur l'historique 7 jours."""
        prod = features.get("production")
        mean_7d = features.get("rolling_mean_7d")
        std_7d = features.get("rolling_std_7d")
        multiplier = self.config.thresholds.STD_DEV_MULTIPLIER

        is_triggered = False
        z_score = 0.0

        if prod is not None and mean_7d is not None and std_7d is not None and std_7d > 0:
            z_score = abs(prod - mean_7d) / std_7d
            if z_score > multiplier and prod < mean_7d:
                is_triggered = True

        weight = self.config.weights.DRIFT_DETECTION

        return RuleEvaluation(
            rule_code="R08_DRIFT_DETECTION",
            rule_name="Dérive de Production (7j)",
            is_triggered=is_triggered,
            score=weight if is_triggered else 0.0,
            weight=weight,
            description=f"Production sous la moyenne 7j de plus de {multiplier} écarts-types (Z-Score: {z_score:.2f}).",
            details={"production": prod, "rolling_mean_7d": mean_7d, "rolling_std_7d": std_7d, "z_score": z_score}
        )
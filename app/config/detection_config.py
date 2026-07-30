"""
Module de Configuration de la Détection et du Moteur de Décision.
Centralise les seuils métier photovoltaïques, les poids d'impact des règles,
les règles de qualification des priorités et la configuration globale du Scoring.
"""

from typing import Dict, Any
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ThresholdsConfig:
    """Seuils métier photovoltaïques pour la détection d'anomalies."""
    # Performance Ratio (PR)
    PR_CRITICAL: float = 0.50  # En dessous de 50%, anomalie critique
    PR_WARNING: float = 0.75   # En dessous de 75%, dégradation suspecte
    
    # Delta Production (Écart Réel vs Attendu)
    DELTA_PROD_CRITICAL_PCT: float = 0.40  # Perte > 40% de la prod attendue
    DELTA_PROD_WARNING_PCT: float = 0.20   # Perte > 20% de la prod attendue

    # Onduleurs & Équipements
    OFFLINE_INVERTER_RATIO_CRITICAL: float = 0.30  # > 30% des onduleurs Hors-Ligne
    FAILED_STRINGS_THRESHOLD: int = 2              # >= 2 chaînes défaillantes

    # Météo & Pertes
    IRRADIANCE_MIN_KW_M2: float = 0.15             # Seuil min d'irradiation pour valider une baisse de prod
    TEMP_GAP_MAX_CELSIUS: float = 15.0             # Écart temp. mesurée vs référence max toléré
    LOSS_PERCENTAGE_WARNING: float = 10.0          # > 10% de pertes déclarées

    # Dérives Temporelles (Séries Temporelles)
    STD_DEV_MULTIPLIER: float = 2.5                # Multiplicateur pour écart à la moyenne (Z-Score)


@dataclass(frozen=True)
class RuleWeightsConfig:
    """Poids attribués à chaque règle dans le calcul du score global d'incident."""
    COMMUNICATION_LOSS: float = 40.0        # Perte totale de télécommunication
    TOTAL_PLANT_SHUTDOWN: float = 50.0     # Production nulle malgré fort ensoleillement
    MAJOR_PR_DROP: float = 30.0            # Chute majeure du Performance Ratio
    MINOR_PR_DROP: float = 15.0            # Chute modérée du Performance Ratio
    INVERTER_FAILURE: float = 25.0         # Panne / Déconnexion d'onduleurs
    STRING_FAILURE: float = 15.0           # Défaillance au niveau chaîne/string
    WEATHER_ANOMALY: float = 10.0          # Anomalie corrélation météo/production
    DRIFT_DETECTION: float = 15.0          # Dérive progressive sur 7 jours


@dataclass(frozen=True)
class PriorityThresholdsConfig:
    """Seuils de score cumulé pour la qualification de priorité."""
    CRITICAL_SCORE: float = 75.0   # Score >= 75 -> CRITICAL
    HIGH_SCORE: float = 50.0       # Score >= 50 -> HIGH
    MEDIUM_SCORE: float = 25.0     # Score >= 25 -> MEDIUM
    LOW_SCORE: float = 10.0       # Score >= 10 -> LOW
                                   # En dessous de 10 -> INFO


@dataclass(frozen=True)
class DetectionConfig:
    """Configuration globale du moteur de détection et de décision."""
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    weights: RuleWeightsConfig = field(default_factory=RuleWeightsConfig)
    priority_thresholds: PriorityThresholdsConfig = field(default_factory=PriorityThresholdsConfig)
    
    # Paramètres d'explicabilité et de confiance
    MAX_TOTAL_SCORE: float = 100.0
    CONFIDENCE_BASE_PERCENT: float = 100.0


# Instance globale réutilisable
DETECTION_CONFIG = DetectionConfig()
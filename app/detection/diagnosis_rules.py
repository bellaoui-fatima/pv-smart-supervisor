"""
Module de la Base de Connaissances Experte.
Définit la matrice de règles traduisant une combinaison d'anomalies (codes de règles)
en un diagnostic humainement lisible, avec la cause racine et les actions à mener.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ExpertRule:
    """Structure d'une règle de diagnostic croisant plusieurs anomalies."""
    required_codes: List[str]          # Codes qui doivent absolument être déclenchés (ET logique)
    excluded_codes: List[str]          # Codes qui ne doivent PAS être déclenchés
    incident_type: str                 # Catégorie standardisée
    title: str                         # Résumé de l'incident
    root_cause: str                    # Cause racine probable
    recommended_action: str            # Action opérationnelle


# Base de connaissances expertes, triée par ordre de spécificité/criticité décroissante
EXPERT_KNOWLEDGE_BASE: List[ExpertRule] = [
    ExpertRule(
        required_codes=["R01_COMM_LOSS"],
        excluded_codes=[],
        incident_type="Communication Outage",
        title="Perte totale de télémétrie de la centrale",
        root_cause="Panne du datalogger (EnergySoft/Rawametrix) ou coupure réseau local.",
        recommended_action="Vérifier la connectivité 4G/Fibre du routeur de la centrale et pinger le datalogger."
    ),
    ExpertRule(
        required_codes=["R02_TOTAL_SHUTDOWN", "R05_INVERTER_FAILURE"],
        excluded_codes=["R01_COMM_LOSS"],
        incident_type="Major Outage",
        title="Arrêt complet suite à un défaut généralisé des onduleurs",
        root_cause="Coupure réseau Enedis (îlotage) ou déclenchement de la protection générale de découplage.",
        recommended_action="Appeler le gestionnaire de réseau (Enedis) pour vérifier la tension réseau. Contrôler le relais de découplage."
    ),
    ExpertRule(
        required_codes=["R07_WEATHER_ANOMALY", "R03_MAJOR_PR_DROP"],
        excluded_codes=["R05_INVERTER_FAILURE"],
        incident_type="Performance Degradation",
        title="Chute sévère de performance sous forte chaleur",
        root_cause="Surchauffe sévère des modules (Derating) ou encrassement majeur (Soiling).",
        recommended_action="Planifier un nettoyage des panneaux et vérifier la ventilation des locaux onduleurs."
    ),
    ExpertRule(
        required_codes=["R05_INVERTER_FAILURE"],
        excluded_codes=["R02_TOTAL_SHUTDOWN"],
        incident_type="Equipment Failure",
        title="Onduleur(s) déconnecté(s) ou en défaut",
        root_cause="Déclenchement interne d'un onduleur (surtension, surchauffe, ou défaut d'isolement).",
        recommended_action="Consulter le portail constructeur pour lire le code erreur exact. Prévoir une relance manuelle."
    ),
    ExpertRule(
        required_codes=["R08_DRIFT_DETECTION"],
        excluded_codes=["R02_TOTAL_SHUTDOWN", "R05_INVERTER_FAILURE"],
        incident_type="Progressive Drift",
        title="Dérive progressive de la production détectée",
        root_cause="Vieillissement accéléré, encrassement progressif, ou végétation créant de l'ombrage.",
        recommended_action="Analyser l'évolution du Performance Ratio sur 30 jours et inspecter visuellement la centrale (drone/visite)."
    )
]
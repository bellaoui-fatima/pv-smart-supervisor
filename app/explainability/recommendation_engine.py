from dataclasses import dataclass
from typing import List, Dict, Any
from .knowledge_base import DIAGNOSIS_DATABASE

@dataclass
class Recommendation:
    """Modèle de données représentant les actions recommandées."""
    actions: List[str]
    severity: str
    description: str

    def to_dict(self) -> dict:
        return {
            "actions": self.actions,
            "severity": self.severity,
            "description": self.description
        }


class RecommendationEngine:
    """
    Moteur chargé de transformer un diagnostic technique en un plan 
    d'action opérationnel pour les équipes de maintenance.
    """
    
    def __init__(self, knowledge_base: dict = None):
        # Injection de la base de connaissances (facilite les tests unitaires)
        self.kb = knowledge_base or DIAGNOSIS_DATABASE

    def generate_recommendation(self, diagnosis: str, context: Dict[str, Any] = None) -> Recommendation:
        """
        Génère une recommandation basée sur le diagnostic.
        
        :param diagnosis: La clé du diagnostic (ex: "offline_inverter")
        :param context: Dictionnaire pour les variables dynamiques (ex: {"equipment_id": "INV03"})
        """
        if context is None:
            context = {}

        # Si le diagnostic n'est pas dans la KB, on a un fallback générique
        default_entry = {
            "description": "Anomalie non reconnue nécessitant une investigation manuelle.",
            "severity": "UNKNOWN",
            "actions": [
                "Vérifier les logs bruts dans l'interface",
                "Contacter le support technique de niveau 2"
            ]
        }

        kb_entry = self.kb.get(diagnosis, default_entry)

        # Remplacement dynamique des variables dans les actions (templating)
        formatted_actions = []
        for action in kb_entry.get("actions", []):
            try:
                # Transforme "Contrôler {equipment_id}" en "Contrôler INV03"
                formatted_actions.append(action.format(**context))
            except KeyError:
                # Si la variable manque dans le context, on garde le texte brut
                formatted_actions.append(action)

        return Recommendation(
            actions=formatted_actions,
            severity=kb_entry.get("severity", "UNKNOWN"),
            description=kb_entry.get("description", "")
        )
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class Explanation:
    """Modèle de données représentant l'explication d'une décision."""
    triggered_rules: List[str]
    important_features: List[str]
    confidence: float
    reasoning: str
    evidence: Dict[str, Any]
    
    def to_dict(self) -> dict:
        return {
            "triggered_rules": self.triggered_rules,
            "important_features": self.important_features,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "evidence": self.evidence
        }


class ExplanationEngine:
    """
    Moteur chargé de transformer les résultats techniques du DecisionEngine
    en une explication lisible et compréhensible pour un opérateur.
    """
    
    def __init__(self):
        # Plus tard, on pourra injecter la KnowledgeBase ici 
        # pour externaliser les phrases de 'reasoning'
        pass

    def generate_explanation(
        self, 
        diagnosis: str, 
        feature_vector: dict,      # Les valeurs exactes au moment T
        evaluated_rules: list,     # Les règles qui ont "matché"
        score_result: float        # Le score de confiance (ex: 0.94)
    ) -> Explanation:
        
        # 1. Formatage des règles déclenchées (Checkmarks pour la lisibilité)
        triggered_rules = [f"✓ {rule_name}" for rule_name in evaluated_rules]
        
        # 2. Extraction des preuves (Evidence) et formatage métier
        evidence = self._extract_evidence(feature_vector)
        
        # 3. Déduction des features les plus importantes
        important_features = list(evidence.keys())
        
        # 4. Génération du raisonnement humain
        reasoning = self._generate_reasoning(diagnosis)

        return Explanation(
            triggered_rules=triggered_rules,
            important_features=important_features,
            confidence=score_result,
            reasoning=reasoning,
            evidence=evidence
        )

    def _extract_evidence(self, feature_vector: dict) -> Dict[str, Any]:
        """
        Formate les valeurs brutes en indicateurs lisibles avec leurs unités.
        """
        evidence = {}
        
        # Exemple de mapping avec formatage
        if "delta" in feature_vector:
            evidence["Delta"] = f"{feature_vector['delta']:.0f} %"
            
        if "pr" in feature_vector:
            # Performance Ratio
            evidence["PR"] = f"{feature_vector['pr']:.2f}"
            
        if "irradiation" in feature_vector:
            evidence["Irradiation"] = f"{feature_vector['irradiation']:.0f} W/m²"
            
        if "temperature" in feature_vector:
            evidence["Température"] = f"{feature_vector['temperature']:.1f}°C"
            
        return evidence

    def _generate_reasoning(self, diagnosis: str) -> str:
        """
        Associe un diagnostic technique à une phrase compréhensible.
        (Note : Cette logique pourra être déplacée dans la Knowledge Base plus tard).
        """
        reasoning_map = {
            "production_anomaly": "Production fortement inférieure à la production attendue alors que les conditions météorologiques sont normales.",
            "inverter_offline": "L'onduleur ne communique plus ou est à l'arrêt complet.",
            "communication_lost": "Perte de connexion avec le datalogger du site.",
            "underperformance_mild": "Légère baisse de performance détectée, potentiellement due à un encrassement ou un ombrage."
        }
        
        return reasoning_map.get(diagnosis, "Anomalie détectée par les règles d'évaluation.")
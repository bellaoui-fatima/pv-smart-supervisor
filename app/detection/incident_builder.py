"""
Module du constructeur d'Incidents (Incident Builder).
Fabrique (Factory) chargée d'assembler les résultats de tous les sous-moteurs
(Scoring, Priority, Diagnosis) en un objet Domaine Incident cohérent.
"""

from datetime import datetime
from typing import Dict, Any
from app.models.domain import Incident, ScoreResult, Diagnosis, Priority, IncidentStatus


class IncidentBuilder:
    """Assembleur final de l'objet Incident."""

    @staticmethod
    def build(
        plant_id: int, 
        features: Dict[str, Any], 
        score_result: ScoreResult,
        diagnosis: Diagnosis, 
        priority: Priority
    ) -> Incident:
        """
        Construit l'objet Incident prêt pour la persistance ou la notification.
        
        :param plant_id: ID de la centrale
        :param features: Le vecteur de features ayant déclenché l'analyse
        :param score_result: Le résultat du moteur de scoring
        :param diagnosis: Le diagnostic XAI expert
        :param priority: La priorité qualifiée
        :return: Objet Incident structuré
        """
        # Utiliser la date des features si elle existe, sinon l'heure actuelle
        measure_date = features.get("date")
        if not isinstance(measure_date, datetime):
            measure_date = datetime.utcnow()

        return Incident(
            plant_id=plant_id,
            created_at=measure_date,
            incident_type=diagnosis.incident_type,
            priority=priority,
            score_result=score_result,
            diagnosis=diagnosis,
            status=IncidentStatus.OPEN
        )
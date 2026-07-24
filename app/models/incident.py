"""
Module des modèles métier pour l'incident.
Définit la structure de données orientée objet pour représenter
un incident détecté par le moteur de diagnostic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Incident:
    """Modèle métier représentant un incident sur une centrale."""
    plant_id: int
    priority: str
    diagnosis: Optional[str] = None
    confidence: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: str = "New"
    notification_sent: bool = False
    ticket_id: Optional[str] = None
    alerts: List[any] = field(default_factory=list)
"""
Module des modèles métier pour l'alerte de notification.
Définit la structure de données standardisée transportée par l'ensemble
des canaux de notification (e-mail, Telegram, etc.).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AlertMessage:
    """Modèle métier représentant un message d'alerte universel."""
    title: str
    body: str
    priority: str
    plant: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ticket_id: Optional[str] = None
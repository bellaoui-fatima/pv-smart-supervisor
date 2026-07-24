"""
Module de base pour l'architecture des notifications.
Définit l'interface abstraite (classe de base) que tous les canaux
de notification doivent implémenter.
"""

from abc import ABC, abstractmethod
from app.models.alert import AlertMessage


class BaseNotifier(ABC):
    """Classe abstraite de base pour les notificateurs du système de supervision."""

    @abstractmethod
    def send(self, alert: AlertMessage) -> None:
        """
        Envoie un message d'alerte via le canal spécifique.

        Args:
            alert (AlertMessage): L'objet d'alerte standardisé à transmettre.
        """
        pass
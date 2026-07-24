"""
Module de notification par Telegram.
Implémente le notificateur Telegram en héritant de BaseNotifier
pour traiter le même objet AlertMessage.
"""

from typing import Optional
import requests

from app.config.settings import settings
from app.models.alert import AlertMessage
from app.notifications.base import BaseNotifier
from app.utils.logger import logger


class TelegramNotifier(BaseNotifier):
    """Notificateur pour l'envoi d'alertes via l'API Bot Telegram."""

    def __init__(self) -> None:
        """Initialise les paramètres de connexion au Bot Telegram."""
        self.token: Optional[str] = getattr(settings, "telegram_token", None)
        self.chat_id: Optional[str] = getattr(settings, "telegram_chat_id", None)
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage" if self.token else ""

    def send(self, alert: AlertMessage) -> None:
        """
        Envoie un message d'alerte sur un canal ou une discussion Telegram.

        Args:
            alert (AlertMessage): L'objet d'alerte unifié à transmettre.
        """
        if not self.token or not self.chat_id:
            logger.warning("Configuration Telegram incomplète (token ou chat_id manquant). Notification ignorée.")
            return

        text = (
            f"🚨 *{alert.title}*\n\n"
            f"🏭 *Centrale :* {alert.plant}\n"
            f"⚡ *Priorité :* {alert.priority}\n"
            f"🕒 *Date :* {alert.timestamp}\n"
            f"🎫 *Ticket :* {alert.ticket_id or 'N/A'}\n\n"
            f"{alert.body}"
        )

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            response = requests.post(self.base_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Alerte Telegram envoyée avec succès pour la centrale {alert.plant}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Échec de l'envoi de la notification Telegram : {e}")
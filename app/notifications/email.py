"""
Module de notification par e-mail via l'API Brevo.
Implémente le notificateur e-mail en héritant de BaseNotifier
et en acceptant l'objet universel AlertMessage.
"""

import os
from typing import Optional
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from app.config.settings import settings
from app.models.alert import AlertMessage
from app.notifications.base import BaseNotifier
from app.utils.logger import logger


class EmailNotifier(BaseNotifier):
    """Notificateur e-mail utilisant le service Brevo (Sendinblue)."""

    def __init__(self) -> None:
        """Initialise la configuration de l'API Brevo via les paramètres globaux."""
        self.configuration = sib_api_v3_sdk.Configuration()
        self.configuration.api_key["api-key"] = settings.brevo_api_key
        self.api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(self.configuration)
        )
        self.sender_email: Optional[str] = settings.sender_email
        self.receiver_email: Optional[str] = settings.receiver_email

    def send(self, alert: AlertMessage) -> None:
        """
        Envoie une alerte sous forme d'e-mail transactionnel via Brevo.

        Args:
            alert (AlertMessage): L'objet d'alerte unifié contenant les détails de l'incident.
        """
        if not self.sender_email or not self.receiver_email:
            logger.error("Configuration e-mail incomplète : expéditeur ou destinataire manquant.")
            return

        email_payload = sib_api_v3_sdk.SendSmtpEmail(
            sender={
                "name": "PV Monitoring System",
                "email": self.sender_email,
            },
            to=[
                {
                    "email": self.receiver_email,
                }
            ],
            subject=f"[{alert.priority.upper()}] {alert.title} - Centrale: {alert.plant}",
            text_content=(
                f"Centrale : {alert.plant}\n"
                f"Priorité : {alert.priority}\n"
                f"Date/Heure : {alert.timestamp}\n"
                f"Ticket ID : {alert.ticket_id or 'N/A'}\n\n"
                f"Message :\n{alert.body}"
            ),
        )

        try:
            self.api_instance.send_transac_email(email_payload)
            logger.info(f"E-mail d'alerte envoyé avec succès pour la centrale {alert.plant}.")
        except ApiException as e:
            logger.error(f"Erreur lors de l'envoi de l'e-mail via Brevo : {e}")
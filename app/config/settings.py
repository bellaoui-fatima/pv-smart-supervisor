"""
Module de configuration centralisée.
Ce module charge et valide toutes les variables d'environnement nécessaires
au fonctionnement de l'application.
"""

import os
from typing import Any
from dotenv import load_dotenv


class Settings:
    """
    Classe Singleton gérant la configuration de l'application.
    Charge les variables d'environnement et lève une erreur si une
    variable requise est manquante.
    """
    _instance = None

    def __new__(cls) -> "Settings":
        if cls._instance is None:
            cls._instance = super(Settings, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialise les attributs en chargeant le fichier .env."""
        load_dotenv()

        # Base de données
        self.database_url: str = self._get_env("DATABASE_URL", required=True)

        # API Rawametrix
        self.rawa_email: str = self._get_env("RAWA_EMAIL", required=True)
        self.rawa_password: str = self._get_env("RAWA_PASSWORD", required=True)

        # API Energysoft
        self.energysoft_user: str = self._get_env("ENERGYSOFT_USER", required=True)
        self.energysoft_password: str = self._get_env("ENERGYSOFT_PASSWORD", required=True)

        # Notifications
        self.telegram_token: str = self._get_env("TELEGRAM_TOKEN", required=True)
        self.telegram_chat_id: str = self._get_env("TELEGRAM_CHAT_ID", required=True)
        self.brevo_api_key: str = self._get_env("BREVO_API_KEY", required=True)
        self.sender_email: str = self._get_env("SENDER_EMAIL", required=True)
        self.receiver_email: str = self._get_env("RECEIVER_EMAIL", required=True)

        # Système
        self.log_level: str = self._get_env("LOG_LEVEL", default="INFO")

    def _get_env(self, key: str, required: bool = False, default: Any = None) -> Any:
        """
        Récupère une variable d'environnement et applique la validation.

        Args:
            key (str): Le nom de la variable d'environnement.
            required (bool): Si True, lève une ValueError si la variable est vide.
            default (Any): Valeur par défaut si la variable est absente.

        Returns:
            Any: La valeur de la variable d'environnement ou la valeur par défaut.

        Raises:
            ValueError: Si la variable est requise mais absente ou vide.
        """
        value = os.getenv(key)
        if required and not value:
            raise ValueError(
                f"Erreur de configuration : La variable '{key}' est manquante ou vide."
            )
        return value if value else default


# Instance globale à importer dans le reste du projet
settings = Settings()
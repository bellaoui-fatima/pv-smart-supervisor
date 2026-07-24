"""
Module de gestion de l'authentification et du cache des jetons JWT.
Gère l'obtention, le stockage en mémoire et le renouvellement automatique
du jeton d'accès avant son expiration.
"""

import time
from typing import Optional
import requests
from app.config.settings import settings
from app.utils.logger import logger


class TokenManager:
    """
    Gestionnaire d'authentification pour l'API Rawametrix.
    Implémente un cache en mémoire et un mécanisme de renouvellement automatique du JWT.
    """

    def __init__(self) -> None:
        self.base_url: str = "https://rawametrix.com/api/v1"
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        # Validité de 24h selon la documentation, renouvellement anticipé de 5 minutes (300s)
        self._token_lifetime: int = 86400
        self._safety_margin: int = 300

    def get_valid_token(self) -> str:
        """
        Récupère un jeton valide, en effectuant une authentification si le jeton
        est absent ou proche de l'expiration.

        Returns:
            str: Le jeton JWT valide.

        Raises:
            requests.exceptions.RequestException: Si l'authentification échoue.
        """
        current_time = time.time()
        
        # Vérifie si le token est absent ou va expirer sous peu
        if not self._token or current_time >= (self._token_expiry - self._safety_margin):
            logger.info("Jeton JWT absent ou expiré. Demande d'un nouveau jeton...")
            self._authenticate()

        return self._token  # type: ignore

    def _authenticate(self) -> None:
        """
        Effectue une requête POST vers l'endpoint de token pour obtenir un nouveau JWT.
        """
        url = f"{self.base_url}/token"
        payload = {
            "email": settings.rawa_email,
            "password": settings.rawa_password
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            # Le corps de la réponse contient directement le jeton JWT
            self._token = response.text.strip()
            self._token_expiry = time.time() + self._token_lifetime
            
            logger.info("Authentification réussie. Jeton JWT mis en cache pour 24 heures.")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Échec de l'authentification auprès de Rawametrix : {e}")
            raise
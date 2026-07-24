"""
Module collecteur pour l'API Rawametrix (REST).
Conforme aux exigences : AUCUN calcul, architecture propre, 
méthodes dédiées : login, get_plants, get_day_measures, get_month_measures, get_losses.
"""

import requests
import pandas as pd
from typing import Dict, Any, List, Optional
from app.config.settings import settings
from app.utils.logger import logger
from app.utils.http_utils import throttle_request


class RawametrixClient:
    """Client REST épuré pour interagir avec l'API Rawametrix sans aucune logique métier."""

    def __init__(self) -> None:
        self.base_url = getattr(settings, "RAWAMETRIX_API_URL", "https://rawametrix.com/").rstrip("/")
        self.email = getattr(settings, "RAWAMETRIX_USER", settings.rawa_email)
        self.password = getattr(settings, "RAWAMETRIX_PASSWORD", settings.rawa_password)
        self._token: Optional[str] = None
        self.session = requests.Session()

    def login(self) -> str:
        """
        Authentifie le client auprès de l'API Rawametrix via l'endpoint de jeton (/api/v1/token)
        et récupère le jeton JWT.

        Returns:
            str: Le jeton d'accès JWT.
        """
        auth_url = f"{self.base_url}/api/v1/token"
        payload = {
            "email": self.email,
            "password": self.password
        }
        
        logger.info("Authentification auprès de l'API Rawametrix...")
        try:
            response = self.session.post(auth_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            token = data.get("token") or data.get("access_token")
            if not token:
                raise ValueError("Le jeton d'accès est introuvable dans la réponse d'authentification.")
            
            self._token = token
            logger.info("Authentification Rawametrix réussie.")
            return self._token
        except Exception as e:
            logger.error(f"Échec de l'authentification Rawametrix : {e}")
            raise

    def _get_headers(self) -> Dict[str, str]:
        """
        Génère les en-têtes HTTP requis avec le jeton Bearer courant.
        """
        if not self._token:
            self.login()
            
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _handle_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Exécute une requête HTTP sécurisée vers l'API Rawametrix.
        """
        url = f"{self.base_url}/api/v1{endpoint}"
        headers = self._get_headers()

        throttle_request(delay_seconds=1.0)

        try:
            response = self.session.request(method=method, url=url, headers=headers, params=params, timeout=15)
            
            if response.status_code >= 500:
                logger.error(f"Erreur serveur ({response.status_code}) sur {url}. Réponse brute : {response.text}")
            elif response.status_code == 401:
                logger.warning("Jeton expiré (401), tentative de ré-authentification...")
                self.login()
                headers = self._get_headers()
                response = self.session.request(method=method, url=url, headers=headers, params=params, timeout=15)

            response.raise_for_status()
            
            if not response.content:
                return []
            return response.json()

        except Exception as err:
            logger.error(f"Erreur lors de l'appel à {url} : {err}")
            raise

    def get_plants(self) -> pd.DataFrame:
        """
        Récupère la liste de toutes les centrales photovoltaïques.

        Returns:
            pd.DataFrame: DataFrame contenant les informations brutes des centrales.
        """
        logger.info("Récupération de la liste des centrales depuis Rawametrix...")
        data = self._handle_request("GET", "/plants")
        
        if isinstance(data, dict):
            plants_list = data.get("data", data.get("plants", []))
        elif isinstance(data, list):
            plants_list = data
        else:
            plants_list = []

        return pd.DataFrame(plants_list)

    def get_day_measures(self, plant_id: Any) -> pd.DataFrame:
        """
        Récupère les mesures journalières brutes pour une centrale spécifique.

        Args:
            plant_id (Any): Identifiant unique de la centrale.

        Returns:
            pd.DataFrame: DataFrame brut des mesures journalières.
        """
        logger.info(f"Récupération des mesures journalières pour la centrale ID: {plant_id}")
        params = {
            "measures": "production,temperature,irradiation,budget_net_production,budget_real_irradiation,budget_t_amb",
            "limit": 1000
        }
        data = self._handle_request("GET", f"/plants/{plant_id}/day_measures", params=params)
        
        if isinstance(data, dict):
            measures_list = data.get("data", data.get("measures", []))
        elif isinstance(data, list):
            measures_list = data
        else:
            measures_list = []

        return pd.DataFrame(measures_list)

    def get_month_measures(self, plant_id: Any) -> pd.DataFrame:
        """
        Récupère les mesures mensuelles brutes pour une centrale spécifique.

        Args:
            plant_id (Any): Identifiant unique de la centrale.

        Returns:
            pd.DataFrame: DataFrame brut des mesures mensuelles.
        """
        logger.info(f"Récupération des mesures mensuelles pour la centrale ID: {plant_id}")
        data = self._handle_request("GET", f"/plants/{plant_id}/month_measures")
        
        if isinstance(data, dict):
            measures_list = data.get("data", data.get("measures", []))
        elif isinstance(data, list):
            measures_list = data
        else:
            measures_list = []

        return pd.DataFrame(measures_list)

    def get_losses(self, plant_id: Any) -> pd.DataFrame:
        """
        Récupère l'historique brut des pertes journalières d'une centrale.

        Args:
            plant_id (Any): Identifiant unique de la centrale.

        Returns:
            pd.DataFrame: DataFrame brut des pertes.
        """
        logger.info(f"Récupération des pertes pour la centrale ID: {plant_id}")
        params = {
            "measures": "loss_energy",
            "limit": 1000
        }
        data = self._handle_request("GET", f"/plants/{plant_id}/day_losses", params=params)
        
        if isinstance(data, dict):
            losses_list = data.get("data", data.get("losses", []))
        elif isinstance(data, list):
            losses_list = data
        else:
            losses_list = []

        return pd.DataFrame(losses_list)
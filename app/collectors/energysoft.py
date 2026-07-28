"""
Module du collecteur Energysoft (OData v4).
Interagit avec l'API Energysoft pour récupérer les sites, les équipements, 
les mesures et gérer les tickets, sans AUCUN calcul métier.
"""

import difflib
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException, Timeout

from app.config.settings import settings
from app.utils.logger import logger
from app.utils.http_utils import throttle_request


class EnergysoftClient:
    """Client pour la récupération des données via l'API OData v4 Energysoft."""

    def __init__(self) -> None:
        """Initialise le client Energysoft avec l'URL de base et l'authentification HTTP Basic."""
        self.base_url: str = getattr(settings, "ENERGYSOFT_API_URL", "https://energysoft.app/odata/v4").rstrip("/")
        
        user = getattr(settings, "ENERGYSOFT_USER", getattr(settings, "energysoft_user", ""))
        password = getattr(settings, "ENERGYSOFT_PASSWORD", getattr(settings, "energysoft_password", ""))
        
        self.auth: HTTPBasicAuth = HTTPBasicAuth(user, password)
        self.headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.session = requests.Session()
        
        # Cache interne pour éviter de requêter /Sites à chaque centrale
        self._sites_cache: Optional[List[Dict[str, Any]]] = None

    def _handle_request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        """
        Exécute une requête HTTP OData sécurisée avec gestion des erreurs et rate limiting.
        """
        url = f"{self.base_url}{endpoint}"
        throttle_request(delay_seconds=1.0)

        try:
            response = self.session.request(
                method=method, 
                url=url, 
                auth=self.auth, 
                headers=self.headers, 
                timeout=30, 
                **kwargs
            )
            
            if response.status_code >= 500:
                logger.error(f"Erreur serveur Energysoft ({response.status_code}) sur {url}.")
            elif response.status_code == 400:
                logger.error(f"Requête OData invalide (400) sur {url}.")
            elif response.status_code == 401:
                logger.error(f"Échec d'authentification (401) auprès d'Energysoft sur {url}.")
            elif response.status_code == 403:
                logger.error(f"Accès refusé (403) sur la ressource Energysoft {url}.")
            elif response.status_code == 404:
                logger.debug(f"Ressource introuvable (404) sur Energysoft {url}.")

            response.raise_for_status()
            return response

        except Timeout:
            logger.error(f"Délai d'attente dépassé (Timeout) lors de l'accès à Energysoft ({url}).")
            raise
        except RequestException as e:
            logger.error(f"Erreur réseau lors de l'appel à Energysoft ({url}) : {e}")
            raise

    def _get_all_sites_cached(self) -> List[Dict[str, Any]]:
        """
        Récupère et met en cache la liste globale des sites Energysoft.
        """
        if self._sites_cache is None:
            logger.info("Récupération initiale et mise en cache des sites Energysoft...")
            try:
                response = self._handle_request("GET", "/Sites")
                data = response.json()
                self._sites_cache = data.get("value", data if isinstance(data, list) else [])
            except Exception as e:
                logger.error(f"Impossible de mettre en cache les sites Energysoft : {e}")
                self._sites_cache = []
        return self._sites_cache

    def _resolve_site_id(self, rawa_id: Any, rawa_name: Optional[str] = None) -> Optional[Any]:
        """
        Trouve l'identifiant réel du site dans Energysoft via :
        1. Correspondance exacte (Nom ou Référence)
        2. Correspondance approximative (Fuzzy matching > 80%)
        """
        sites = self._get_all_sites_cached()
        if not sites:
            return None

        rawa_id_str = str(rawa_id).strip()
        rawa_name_norm = str(rawa_name).strip().lower() if rawa_name else ""

        # --- 1. Passe 1 : Correspondance exacte ---
        for site in sites:
            es_id = site.get("Id") or site.get("ID") or site.get("SiteId")
            es_name = str(site.get("Name", "")).strip().lower()
            es_ref = str(site.get("Reference", "")).strip()

            if (rawa_name_norm and rawa_name_norm == es_name) or rawa_id_str == es_ref:
                return es_id

        # --- 2. Passe 2 : Fuzzy Matching (Similarité) ---
        if rawa_name_norm:
            meilleur_match_id = None
            meilleur_score = 0.0
            meilleur_nom_es = ""

            for site in sites:
                es_name = str(site.get("Name", "")).strip().lower()
                
                # Calcule le ratio de similarité entre 0.0 et 1.0
                score = difflib.SequenceMatcher(None, rawa_name_norm, es_name).ratio()
                
                # Si le score est supérieur à 80% et meilleur que le précédent trouvé
                if score > 0.80 and score > meilleur_score:
                    meilleur_score = score
                    meilleur_match_id = site.get("Id") or site.get("ID") or site.get("SiteId")
                    meilleur_nom_es = site.get("Name", "")

            if meilleur_match_id:
                logger.info(
                    f"Mapping automatique réussi via similarité ({meilleur_score*100:.0f}%) : "
                    f"Rawa '{rawa_name}' -> ES '{meilleur_nom_es}' (ID: {meilleur_match_id})"
                )
                return meilleur_match_id

        return None

    def _get_odata_key(self, value: Any) -> str:
        """Convertit une valeur en clé OData littérale compatible avec les tests et l'API."""
        return f"'{str(value).strip()}'"

    def _record_matches_hints(self, record: Dict[str, Any], hints: List[str]) -> bool:
        """Vérifie si un enregistrement contient un des indices fournis dans ses champs clés."""
        if not record or not hints:
            return False

        def normalize(value: Any) -> str:
            text = str(value or "")
            return "".join(ch for ch in text.lower() if ch.isalnum())

        candidates: List[str] = []
        for key in ["ID", "Id", "Name", "Reference"]:
            if key in record:
                candidates.append(str(record[key]))

        site = record.get("Site") if isinstance(record.get("Site"), dict) else {}
        for key in ["Name", "Id", "Reference", "ID"]:
            if key in site:
                candidates.append(str(site[key]))

        normalized_candidates = [normalize(candidate) for candidate in candidates]
        normalized_hints = [normalize(hint) for hint in hints]

        return any(hint in candidate for hint in normalized_hints for candidate in normalized_candidates)

    def _format_odata_id(self, id_value: Any) -> str:
        """Formate correctement un identifiant pour une requête OData v4."""
        val_str = str(id_value).strip()
        if val_str.isdigit():
            return val_str
        return self._get_odata_key(id_value)

    def get_sites(self, site_id: Optional[str] = None) -> Union[pd.DataFrame, Dict[str, Any]]:
        """Récupère un site spécifique ou la liste complète des sites."""
        if site_id:
            odata_id = self._format_odata_id(site_id)
            endpoint = f"/Sites({odata_id})"
            try:
                response = self._handle_request("GET", endpoint)
                return response.json()
            except Exception:
                return {}

        return pd.DataFrame(self._get_all_sites_cached())

    def get_inverters(self, site_id: str, site_name: Optional[str] = None) -> pd.DataFrame:
        """Récupère la liste des onduleurs d'un site avec mapping automatique."""
        es_site_id = self._resolve_site_id(site_id, site_name)

        if not es_site_id:
            logger.warning(
                f"Onduleurs: Aucune correspondance Energysoft trouvée pour le site Rawa '{site_name}' (ID: {site_id})."
            )
            return pd.DataFrame()

        odata_id = self._format_odata_id(es_site_id)
        
        # Interrogation directe de la ressource spécifique du site
        endpoints_to_try = [
            f"/Sites({odata_id})/Inverters",
            f"/Inverters?$filter=SiteId eq {odata_id}"
        ]

        for endpoint in endpoints_to_try:
            try:
                response = self._handle_request("GET", endpoint)
                data = response.json()
                inverters_list = data.get("value", data if isinstance(data, list) else [])

                if isinstance(inverters_list, list) and len(inverters_list) > 0:
                    return pd.DataFrame(inverters_list)
            except Exception:
                continue

        logger.warning(f"Aucun onduleur trouvé pour le site Energysoft ID {es_site_id}.")
        return pd.DataFrame()

    def get_measurements(
        self,
        inverter_id: str,
        measure_type: str = "power",
        filter_date: Optional[str] = None,
        top: int = 1000
    ) -> pd.DataFrame:
        """Récupère les mesures brutes d'un onduleur."""
        odata_id = self._format_odata_id(inverter_id)
        
        filters = [f"InverterId eq {odata_id}", f"MeasureType eq '{measure_type}'"]
        if filter_date:
            filters.append(f"Date ge {filter_date}")

        query_params = {
            "$top": top,
            "$filter": " and ".join(filters)
        }

        endpoint = "/Measures"
        try:
            response = self._handle_request("GET", endpoint, params=query_params)
        except Exception:
            return pd.DataFrame()

        data = response.json()
        measures_list = data.get("value", data if isinstance(data, list) else [])

        return pd.DataFrame(measures_list)

    def get_status(self, site_id: str, site_name: Optional[str] = None) -> pd.DataFrame:
        """Récupère le statut opérationnel d'un site."""
        es_site_id = self._resolve_site_id(site_id, site_name)

        if not es_site_id:
            logger.warning(
                f"Statut: Aucune correspondance Energysoft trouvée pour le site Rawa '{site_name}' (ID: {site_id})."
            )
            return pd.DataFrame()

        odata_id = self._format_odata_id(es_site_id)
        
        # Interrogation directe de la ressource spécifique du site
        endpoints_to_try = [
            f"/Sites({odata_id})/Status",
            f"/Status?$filter=SiteId eq {odata_id}"
        ]

        for endpoint in endpoints_to_try:
            try:
                response = self._handle_request("GET", endpoint)
                data = response.json()
                status_list = data.get("value", data if isinstance(data, list) else [])

                if isinstance(status_list, list) and len(status_list) > 0:
                    return pd.DataFrame(status_list)
            except Exception:
                continue

        return pd.DataFrame()

    def create_service_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Crée une demande de service (ticket d'incident) dans Energysoft."""
        endpoint = "/ServiceRequests"
        response = self._handle_request("POST", endpoint, json=payload)
        logger.info("Demande de service (ticket) créée avec succès dans Energysoft.")
        return response.json()
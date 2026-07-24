from typing import List, Dict, Any
import pandas as pd
import numpy as np
from app.utils.logger import logger

class Preprocessor:
    """
    Responsabilité unique : Nettoyage, normalisation et typage des payloads JSON bruts.
    Prend du JSON en entrée, applique les transformations Pandas, et retourne
    des dictionnaires standardisés prêts pour la persistance ou le calcul.
    """

    @staticmethod
    def process_rawametrix_plants(raw_json: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Standardise la liste des centrales récupérées de RawaMetrix."""
        if not raw_json:
            return []

        logger.info(" Prétraitement des données statiques des centrales...")
        df = pd.DataFrame(raw_json)

        # Correspondance des colonnes (Renommer selon notre modèle de données)
        rename_mapping = {
            "id": "id",
            "name": "plant_name",
            "capacity": "capacity",
            "location": "location",
            "commissioning_date": "commissioning_date"
        }
        # On s'assure que toutes les colonnes attendues existent, même vides
        for col in rename_mapping.keys():
            if col not in df.columns:
                df[col] = None

        df = df[list(rename_mapping.keys())].rename(columns=rename_mapping)

        # Nettoyage et conversion des types
        df["capacity"] = pd.to_numeric(df["capacity"], errors="coerce").fillna(0.0)
        df["commissioning_date"] = pd.to_datetime(df["commissioning_date"], errors="coerce").dt.date

        # Remplacement des NaN par None pour la compatibilité SQL
        df = df.replace({np.nan: None})
        return df.to_dict(orient="records")

    @staticmethod
    def process_rawametrix_measures(raw_json: List[Dict[str, Any]], plant_id: str) -> List[Dict[str, Any]]:
        """Standardise et nettoie les mesures journalières de RawaMetrix."""
        if not raw_json:
            return []

        logger.info(f" Prétraitement des mesures journalières pour la centrale : {plant_id}")
        df = pd.DataFrame(raw_json)

        # Injection forcée de la clé étrangère plant_id
        df["plant_id"] = plant_id

        # Mappage des mesures d'API vers les colonnes de notre modèle
        mappings = {
            "date": "date",
            "plant_id": "plant_id",
            "production": "production",
            "temperature": "temperature",
            "irradiation": "irradiation",
            "budget_net_production": "budget_production",
            "budget_real_irradiation": "budget_irradiation",
            "budget_t_amb": "budget_temperature"
        }

        for col in mappings.keys():
            if col not in df.columns:
                df[col] = None

        df = df[list(mappings.keys())].rename(columns=mappings)

        # Conversion stricte des types de données
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        numeric_cols = ["production", "temperature", "irradiation", "budget_production", "budget_irradiation", "budget_temperature"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Initialisation par défaut des colonnes calculées (Feature engineering) à None
        df["expected_production"] = None
        df["delta"] = None

        # Suppression des lignes dont la date est invalide
        df = df.dropna(subset=["date"])

        df = df.replace({np.nan: None})
        return df.to_dict(orient="records")

    @staticmethod
    def process_rawametrix_losses(raw_json: List[Dict[str, Any]], plant_id: str) -> List[Dict[str, Any]]:
        """Standardise et nettoie les données de pertes de RawaMetrix."""
        if not raw_json:
            return []

        logger.info(f" Prétraitement des pertes journalières pour la centrale : {plant_id}")
        df = pd.DataFrame(raw_json)
        df["plant_id"] = plant_id

        mappings = {
            "plant_id": "plant_id",
            "date": "date",
            "loss_energy": "loss_energy",
            "loss_category": "loss_category",
            "loss_cause": "loss_cause",
            "loss_type": "loss_type"
        }

        for col in mappings.keys():
            if col not in df.columns:
                df[col] = None

        df = df[list(mappings.keys())].rename(columns=mappings)
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df["loss_energy"] = pd.to_numeric(df["loss_energy"], errors="coerce").fillna(0.0)

        df = df.dropna(subset=["date"])
        df = df.replace({np.nan: None})
        return df.to_dict(orient="records")

    @staticmethod
    def process_energysoft_inverters(raw_json: List[Dict[str, Any]], plant_id: str) -> List[Dict[str, Any]]:
        """Standardise la liste des onduleurs extraite d'Energysoft."""
        if not raw_json:
            return []

        logger.info(f" Prétraitement des équipements onduleurs pour le site : {plant_id}")
        df = pd.DataFrame(raw_json)
        df["plant_id"] = plant_id

        # Mappage des propriétés issues du flux OData Energysoft
        mappings = {
            "ID": "id",
            "plant_id": "plant_id",
            "Name": "name",
            "Status": "status",
            "Tag": "communication_status"  # Par exemple, utilisation du Tag pour le statut com si spécifié
        }

        for col in mappings.keys():
            if col not in df.columns:
                df[col] = None

        df = df[list(mappings.keys())].rename(columns=mappings)
        
        # Nettoyage des chaînes textuelles (Suppression des espaces inutiles)
        for col in ["id", "name", "status", "communication_status"]:
            df[col] = df[col].astype(str).str.strip()

        # Endpoint par défaut non fourni par l'API directe mais utile pour notre modèle
        df["endpoint"] = None

        df = df.replace({"nan": None, "None": None, np.nan: None})
        return df.to_dict(orient="records")
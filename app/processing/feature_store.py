"""
Module Feature Store.
Point d'accès unique pour sauvegarder, charger et mettre à jour les features
utilisées par la couche d'Intelligence Artificielle et le Dashboard.
"""

from typing import Optional
from datetime import datetime
import pandas as pd
from app.database.repository import DatabaseRepository
from app.utils.logger import logger


class FeatureStore:
    """
    Gestionnaire du Feature Store en appuyant la persistance sur la base relationnelle.
    """

    def __init__(self, repository: DatabaseRepository) -> None:
        """
        Args:
            repository (DatabaseRepository): Instance du repository de base de données.
        """
        self.repository = repository

    def save_features(self, plant_id: int, df_features: pd.DataFrame) -> None:
        """
        Persiste un DataFrame de features enrichies dans la base de données.

        Args:
            plant_id (int): Identifiant interne de la centrale.
            df_features (pd.DataFrame): DataFrame préparé par le FeatureEngineer.
        """
        if df_features is None or df_features.empty:
            logger.warning("FeatureStore.save_features: DataFrame fourni vide.")
            return

        logger.info(f"FeatureStore: Sauvegarde de {len(df_features)} lignes de features pour la centrale {plant_id}.")
        
        # Convertit le DataFrame en liste de dictionnaires pour le Repository
        records = df_features.to_dict(orient="records")
        self.repository.save_features(plant_id=plant_id, features_data=records)

    def load_features(
        self, 
        plant_id: int, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Restaure un DataFrame de features prêt à consommer pour les algorithmes du Milestone 3.

        Args:
            plant_id (int): Identifiant de la centrale.
            start_date (Optional[datetime]): Date de début de la fenêtre d'extraction.
            end_date (Optional[datetime]): Date de fin de la fenêtre d'extraction.

        Returns:
            pd.DataFrame: DataFrame pandas contenant l'ensemble des colonnes de features.
        """
        logger.info(f"FeatureStore: Chargement des features pour la centrale {plant_id}.")
        measures = self.repository.get_features_by_plant(plant_id, start_date, end_date)
        
        if not measures:
            logger.warning(f"FeatureStore: Aucune feature trouvée en base pour la centrale {plant_id}.")
            return pd.DataFrame()

        # Conversion des objets SQLAlchemy ORM en dictionnaires
        data = []
        for m in measures:
            data.append({
                "date": m.date,
                "production": m.production,
                "temperature": m.temperature,
                "irradiation": m.irradiation,
                "budget_production": m.budget_production,
                "budget_irradiation": m.budget_irradiation,
                "budget_temperature": m.budget_temperature,
                "expected_production": m.expected_production,
                "delta": m.delta,
                "performance_ratio": m.performance_ratio,
                "temperature_gap": m.temperature_gap,
                "irradiation_ratio": m.irradiation_ratio,
                "loss_percentage": m.loss_percentage,
                "offline_inverters": m.offline_inverters,
                "failed_strings": m.failed_strings,
                "communication_status": m.communication_status,
                "rolling_mean_7d": m.rolling_mean_7d,
                "rolling_std_7d": m.rolling_std_7d,
                "anomaly_score_rule": m.anomaly_score_rule
            })

        df = pd.DataFrame(data)
        logger.info(f"FeatureStore: {len(df)} enregistrements chargés.")
        return df

    def update_features(self, plant_id: int, df_updates: pd.DataFrame) -> None:
        """
        Met à jour ponctuellement certaines colonnes de features.

        Args:
            plant_id (int): Identifiant de la centrale.
            df_updates (pd.DataFrame): DataFrame contenant la colonne 'date' et les colonnes à modifier.
        """
        if df_updates is None or df_updates.empty or "date" not in df_updates.columns:
            logger.warning("FeatureStore.update_features: Données invalides fournies.")
            return

        for _, row in df_updates.iterrows():
            record_date = row["date"]
            updates = row.drop("date").to_dict()
            self.repository.update_features(plant_id, record_date, updates)
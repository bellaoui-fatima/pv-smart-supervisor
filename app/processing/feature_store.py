"""
Module Feature Store.
Point d'accès unique pour sauvegarder, charger et mettre à jour les features
utilisées par la couche d'Intelligence Artificielle, le Decision Engine et le Dashboard.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from app.database.repository import DatabaseRepository
from app.utils.logger import logger


class FeatureStore:
    """Gestionnaire du Feature Store appuyé sur la base de données relationnelle."""

    def __init__(self, repository: DatabaseRepository) -> None:
        self.repository = repository

    def save_features(self, plant_id: int, df_features: pd.DataFrame) -> None:
        """Persiste un DataFrame de features enrichies dans la base de données."""
        if df_features is None or df_features.empty:
            logger.warning("FeatureStore.save_features: DataFrame fourni vide.")
            return

        logger.info(f"FeatureStore: Sauvegarde de {len(df_features)} lignes de features pour la centrale {plant_id}.")
        records = df_features.to_dict(orient="records")
        self.repository.save_features(plant_id=plant_id, features_data=records)

    def load_features(
        self, 
        plant_id: int, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Restaure un DataFrame de features pour une centrale sur une plage temporelle."""
        logger.info(f"FeatureStore: Chargement des features pour la centrale {plant_id}.")
        measures = self.repository.get_features_by_plant(plant_id, start_date, end_date)
        
        if not measures:
            logger.warning(f"FeatureStore: Aucune feature trouvée en base pour la centrale {plant_id}.")
            return pd.DataFrame()

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

    def load_latest_features(self, plant_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère le dernier vecteur de features sous forme de dictionnaire/série
        pour évaluation immédiate par le Decision Engine.
        """
        measure = self.repository.get_latest_features(plant_id)
        if not measure:
            logger.warning(f"FeatureStore: Aucune mesure récente trouvée pour la centrale {plant_id}.")
            return None

        return {
            "date": measure.date,
            "production": measure.production,
            "temperature": measure.temperature,
            "irradiation": measure.irradiation,
            "expected_production": measure.expected_production,
            "delta": measure.delta,
            "performance_ratio": measure.performance_ratio,
            "temperature_gap": measure.temperature_gap,
            "irradiation_ratio": measure.irradiation_ratio,
            "loss_percentage": measure.loss_percentage,
            "offline_inverters": measure.offline_inverters,
            "failed_strings": measure.failed_strings,
            "communication_status": measure.communication_status,
            "rolling_mean_7d": measure.rolling_mean_7d,
            "rolling_std_7d": measure.rolling_std_7d,
            "anomaly_score_rule": measure.anomaly_score_rule
        }

    def load_last_7_days(self, plant_id: int) -> pd.DataFrame:
        """Extrait l'historique de features des 7 derniers jours."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        return self.load_features(plant_id, start_date=start_date, end_date=end_date)

    def load_last_30_days(self, plant_id: int) -> pd.DataFrame:
        """Extrait l'historique de features des 30 derniers jours."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        return self.load_features(plant_id, start_date=start_date, end_date=end_date)

    def update_features(self, plant_id: int, df_updates: pd.DataFrame) -> None:
        """Met à jour ponctuellement certaines colonnes de features."""
        if df_updates is None or df_updates.empty or "date" not in df_updates.columns:
            logger.warning("FeatureStore.update_features: Données invalides fournies.")
            return

        for _, row in df_updates.iterrows():
            record_date = row["date"]
            updates = row.drop("date").to_dict()
            self.repository.update_features(plant_id, record_date, updates)

    # =========================================================================
    # --- Nouvelles méthodes : Snapshot et Traçabilité (XAI) ---
    # =========================================================================

    def get_features_at_date(self, plant_id: int, target_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Récupère les features exactes pour une centrale à une date précise.
        Utile pour rejouer ou analyser le contexte précis d'un incident historique.
        """
        df = self.load_features(plant_id, start_date=target_date, end_date=target_date)
        if df.empty:
            logger.warning(f"FeatureStore: Aucune feature trouvée à la date {target_date} pour la centrale {plant_id}.")
            return None
        return df.iloc[0].to_dict()

    def get_last_features(self, plant_id: int) -> Optional[Dict[str, Any]]:
        """
        Alias standardisé de load_latest_features.
        Garantit que le Decision Engine peut piocher les dernières features connues.
        """
        return self.load_latest_features(plant_id)

    def get_feature_snapshot(self, plant_id: int, target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Génère un 'snapshot' JSON-serializable des features, figeant les valeurs exactes
        ayant conduit à une décision d'incident (XAI).
        
        Args:
            plant_id (int): L'ID de la centrale.
            target_date (Optional[datetime]): La date ciblée. Si None, prend les dernières features.
            
        Returns:
            Dict[str, Any]: Dictionnaire des features nettoyées pour l'insertion en base (JSON).
        """
        if target_date:
            features = self.get_features_at_date(plant_id, target_date)
        else:
            features = self.get_last_features(plant_id)
            
        if not features:
            logger.warning(f"FeatureStore.get_feature_snapshot: Impossible de créer un snapshot pour la centrale {plant_id}.")
            return {}
            
        # Nettoyage et typage pour garantir la compatibilité avec la colonne JSON de SQLAlchemy
        snapshot = {}
        for key, value in features.items():
            if pd.isna(value):  # Remplace les NaN (pandas) par None (null en JSON)
                snapshot[key] = None
            elif isinstance(value, (datetime, pd.Timestamp)):
                snapshot[key] = value.isoformat()
            else:
                snapshot[key] = value
                
        return snapshot
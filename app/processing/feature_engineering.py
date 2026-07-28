"""
Module de Feature Engineering.
Responsable de l'agrégation, du calcul des métriques métier, météo, équipements,
temporelles et de la préparation du DataFrame final pour le Feature Store et l'IA.
"""

from typing import List, Dict, Optional, Union
import pandas as pd
import numpy as np
from app.processing.strings_analysis import StringAnalysisResult
from app.utils.logger import logger


class FeatureEngineer:
    """
    Classe centrale de calcul et d'enrichissement des features pour l'IA et le monitoring.
    """

    def __init__(self, anomaly_threshold_delta: float = -0.15) -> None:
        """
        Args:
            anomaly_threshold_delta (float): Seuil de dérive de delta pour considérer un jour comme anormal.
        """
        self.anomaly_threshold_delta = anomaly_threshold_delta

    def create_features(
        self,
        df_measures: pd.DataFrame,
        inverters_data: Optional[Union[List[dict], pd.DataFrame]] = None,
        losses_data: Optional[Union[List[dict], pd.DataFrame]] = None,
        string_analysis: Optional[StringAnalysisResult] = None
    ) -> pd.DataFrame:
        """
        Génère l'ensemble des features pour un DataFrame de mesures d'une centrale.

        Args:
            df_measures (pd.DataFrame): DataFrame nettoyé avec mesures et calculs de base.
            inverters_data (Optional): Données de statut des onduleurs.
            losses_data (Optional): Données de pertes d'énergie.
            string_analysis (Optional[StringAnalysisResult]): Résultats de l'analyseur de strings.

        Returns:
            pd.DataFrame: DataFrame enrichi avec l'intégralité des features.
        """
        if df_measures is None or df_measures.empty:
            logger.warning("FeatureEngineer: DataFrame de mesures vide.")
            return pd.DataFrame()

        df = df_measures.copy()
        
        # S'assurer que le DataFrame est trié chronologiquement pour les calculs temporels
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

        logger.info(f"Début du Feature Engineering sur {len(df)} enregistrements.")

        # 1. Features Météo
        df = self._add_weather_features(df)

        # 2. Features Pertes
        df = self._add_loss_features(df, losses_data)

        # 3. Features Onduleurs
        df = self._add_inverter_features(df, inverters_data)

        # 4. Features Strings
        df = self._add_string_features(df, string_analysis)

        # 5. Features Temporelles (Moyennes & Écarts-types glissants)
        df = self._add_temporal_features(df)

        # 6. Features Historiques
        df = self._add_historical_features(df)

        # 7. Features de Qualité de Donnée
        df = self._add_quality_features(df)

        logger.info("Feature Engineering terminé avec succès.")
        return df

    def _add_weather_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcule les écarts et ratios météorologiques."""
        if "temperature" in df.columns and "budget_temperature" in df.columns:
            df["temperature_gap"] = df["temperature"] - df["budget_temperature"]
        else:
            df["temperature_gap"] = 0.0

        if "irradiation" in df.columns and "budget_irradiation" in df.columns:
            safe_budget_irr = df["budget_irradiation"].replace(0.0, np.nan)
            df["irradiation_ratio"] = df["irradiation"] / safe_budget_irr
        else:
            df["irradiation_ratio"] = 1.0

        return df

    def _add_loss_features(self, df: pd.DataFrame, losses_data: Optional[Union[List[dict], pd.DataFrame]]) -> pd.DataFrame:
        """Enrichit avec les métriques de pertes énergétiques."""
        df["loss_energy"] = 0.0
        df["loss_percentage"] = 0.0
        df["loss_category"] = "None"

        if losses_data is None:
            return df

        df_losses = pd.DataFrame(losses_data) if isinstance(losses_data, list) else losses_data
        if df_losses.empty or "date" not in df_losses.columns:
            return df

        df_losses["date"] = pd.to_datetime(df_losses["date"])

        # Fusion sur la date pour corréler les pertes déclarées
        merged = pd.merge(df, df_losses[["date", "loss_energy", "loss_category"]], on="date", how="left", suffixes=("", "_loss"))
        
        if "loss_energy_loss" in merged.columns:
            df["loss_energy"] = merged["loss_energy_loss"].fillna(0.0)
            df["loss_category"] = merged["loss_category_loss"].fillna("None")

        if "expected_production" in df.columns:
            safe_expected = df["expected_production"].replace(0.0, np.nan)
            df["loss_percentage"] = (df["loss_energy"] / safe_expected) * 100.0

        return df

    def _add_inverter_features(self, df: pd.DataFrame, inverters_data: Optional[Union[List[dict], pd.DataFrame]]) -> pd.DataFrame:
        """Calcule l'état de santé et de communication du parc d'onduleurs."""
        offline_count = 0
        total_inverters = 1
        comm_failures = 0

        if inverters_data is not None:
            df_inv = pd.DataFrame(inverters_data) if isinstance(inverters_data, list) else inverters_data
            if not df_inv.empty:
                total_inverters = max(len(df_inv), 1)
                if "status" in df_inv.columns:
                    offline_count = int((df_inv["status"].str.upper() != "OK").sum())
                if "communication" in df_inv.columns:
                    comm_failures = int((df_inv["communication"].str.upper() != "OK").sum())

        df["offline_inverters"] = offline_count
        df["offline_ratio"] = round(offline_count / total_inverters, 3)
        df["communication_failures"] = comm_failures
        df["communication_status"] = (comm_failures == 0)

        return df

    def _add_string_features(self, df: pd.DataFrame, string_analysis: Optional[StringAnalysisResult]) -> pd.DataFrame:
        """Intègre les métriques issues de la recherche de chaînes défaillantes."""
        if string_analysis is None:
            df["failed_strings"] = 0
            df["failed_ratio"] = 0.0
            df["weakest_string_ratio"] = 1.0
            return df

        total_strings = len(string_analysis.connected_strings) + len(string_analysis.disconnected_strings)
        total_strings = max(total_strings, 1)

        failed_count = len(string_analysis.failed_strings)
        df["failed_strings"] = failed_count
        df["failed_ratio"] = round(failed_count / total_strings, 3)

        weakest_ratio = 1.0
        if string_analysis.weakest_string and string_analysis.ratios:
            weakest_ratio = string_analysis.ratios.get(string_analysis.weakest_string, 1.0)

        df["weakest_string_ratio"] = weakest_ratio
        return df

    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Génère les fenêtres glissantes (Rolling Window) indispensables pour les modèles temporels."""
        if "production" in df.columns:
            df["rolling_mean_7d"] = df["production"].rolling(window=7, min_periods=1).mean()
            df["rolling_std_7d"] = df["production"].rolling(window=7, min_periods=1).std().fillna(0.0)
        else:
            df["rolling_mean_7d"] = 0.0
            df["rolling_std_7d"] = 0.0

        if "delta" in df.columns:
            df["delta_rolling_mean"] = df["delta"].rolling(window=7, min_periods=1).mean()
            df["delta_rolling_std"] = df["delta"].rolling(window=7, min_periods=1).std().fillna(0.0)
        else:
            df["delta_rolling_mean"] = 0.0
            df["delta_rolling_std"] = 0.0

        return df

    def _add_historical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Génère des métriques de dérive historique et de récurrence d'anomalies."""
        if "delta" in df.columns:
            df["previous_day_delta"] = df["delta"].shift(1).fillna(0.0)
            
            # Détection simple d'anomalie sur le delta
            is_anomaly = df["delta"] < self.anomaly_threshold_delta
            
            # Compteur de jours d'anomalies consécutives
            consecutive = []
            count = 0
            for anomaly in is_anomaly:
                count = count + 1 if anomaly else 0
                consecutive.append(count)
            df["consecutive_anomaly_days"] = consecutive

            # Jours écoulés depuis la dernière anomalie
            days_since = []
            last_idx = -1
            for idx, anomaly in enumerate(is_anomaly):
                if anomaly:
                    last_idx = idx
                    days_since.append(0)
                else:
                    days_since.append(idx - last_idx if last_idx != -1 else 999)
            df["days_since_last_anomaly"] = days_since
        else:
            df["previous_day_delta"] = 0.0
            df["consecutive_anomaly_days"] = 0
            df["days_since_last_anomaly"] = 999

        return df

    def _add_quality_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Évalue la complétude des données entrantes."""
        core_columns = ["production", "temperature", "irradiation"]
        existing_cols = [c for c in core_columns if c in df.columns]

        if existing_cols:
            missing_count = df[existing_cols].isnull().sum(axis=1) + (df[existing_cols] == 0).sum(axis=1)
            df["missing_measurements"] = missing_count
            df["missing_percentage"] = (missing_count / len(existing_cols)) * 100.0
        else:
            df["missing_measurements"] = 0
            df["missing_percentage"] = 0.0

        return df
"""
Module de Preprocessing des données.
Responsable de la validation, du nettoyage et de l'harmonisation des DataFrames 
bruts issus des API (Rawametrix, Energysoft).
Ne contient AUCUNE règle d'intelligence métier ni de calcul de features.
"""

import pandas as pd
import numpy as np
from typing import List
from app.utils.logger import logger


class DataPreprocessor:
    """
    Classe dédiée au nettoyage et à la préparation des DataFrames.
    Assure l'intégrité des données avant leur passage dans la couche de Feature Engineering.
    """

    def __init__(self) -> None:
        # Colonnes numériques attendues pour les mesures journalières
        self.numeric_measures: List[str] = [
            "production", "temperature", "irradiation",
            "budget_production", "budget_irradiation", "budget_temperature"
        ]

    def process_daily_measures(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Nettoie et harmonise un DataFrame contenant des mesures journalières.
        
        Args:
            df (pd.DataFrame): DataFrame brut issu des API.
            
        Returns:
            pd.DataFrame: DataFrame propre, validé et prêt pour le calcul.
        """
        if df is None or df.empty:
            logger.warning("Preprocessing: Le DataFrame des mesures est vide.")
            return pd.DataFrame()

        # On travaille sur une copie pour éviter les SettingWithCopyWarning
        clean_df = df.copy()

        logger.info(f"Début du preprocessing pour {len(clean_df)} mesures brutes.")

        clean_df = self._harmonize_types(clean_df)
        clean_df = self._remove_duplicates(clean_df, subset=["plant_id", "date"])
        clean_df = self._handle_missing_values(clean_df)
        clean_df = self._validate_physics(clean_df)
        clean_df = self._prevent_zero_division(clean_df)

        logger.info(f"Preprocessing terminé. {len(clean_df)} lignes valides conservées.")
        return clean_df

    def _harmonize_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convertit les colonnes dans les types de données appropriés."""
        # 1. Dates
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            # Suppression des lignes où la date est invalide (NaT)
            df = df.dropna(subset=["date"])

        # 2. Normalisation des noms de colonnes issus des API externes
        column_aliases = {
            "budget_net_production": "budget_production",
            "budget_real_irradiation": "budget_irradiation",
            "budget_t_amb": "budget_temperature",
        }
        for source_col, target_col in column_aliases.items():
            if source_col in df.columns and target_col not in df.columns:
                df[target_col] = df[source_col]

        # 3. Numériques (float)
        for col in self.numeric_measures:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 3. Entiers & Booléens (le cas échéant pour les onduleurs/ID)
        if "plant_id" in df.columns:
            df["plant_id"] = pd.to_numeric(df["plant_id"], errors="coerce").fillna(-1).astype(int)

        return df

    def _remove_duplicates(self, df: pd.DataFrame, subset: List[str]) -> pd.DataFrame:
        """Supprime les doublons basés sur un sous-ensemble de colonnes."""
        available_subset = [col for col in subset if col in df.columns]
        if available_subset:
            initial_len = len(df)
            df = df.drop_duplicates(subset=available_subset, keep="last")
            if len(df) < initial_len:
                logger.debug(f"Preprocessing: {initial_len - len(df)} doublons supprimés.")
        return df

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gère les NaN (Not a Number) sur les colonnes obligatoires."""
        for col in self.numeric_measures:
            if col in df.columns:
                # Les valeurs NaN sur des mesures critiques sont remplacées par 0 
                # (à affiner selon les consignes métier si besoin d'interpolation)
                df[col] = df[col].fillna(0.0)
        return df

    def _validate_physics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Valide l'intégrité physique des données (ex: pas de valeurs négatives impossibles).
        """
        # La production et l'irradiation ne peuvent pas être négatives
        for col in ["production", "irradiation", "budget_production", "budget_irradiation"]:
            if col in df.columns:
                df[col] = df[col].clip(lower=0.0)
        
        return df

    def _prevent_zero_division(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Protège les futures opérations mathématiques (Feature Engineering) 
        en traitant les zéros dans les dénominateurs potentiels.
        """
        # Dans ProdExpected = (ProdBudget / IrrBudget) * ...
        # IrrBudget se retrouve au dénominateur. On remplace 0 par NaN pour générer 
        # un calcul "vide" plutôt qu'une erreur fatale (ZeroDivisionError).
        if "budget_irradiation" in df.columns:
            df["budget_irradiation"] = df["budget_irradiation"].replace(0.0, np.nan)

        # Idem si la production attendue devait servir de diviseur pour un ratio
        if "expected_production" in df.columns:
            df["expected_production"] = df["expected_production"].replace(0.0, np.nan)

        return df
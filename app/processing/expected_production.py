"""
Module de calcul de la production attendue (Expected Production).
Responsable de l'application de la formule physique et de la génération
des indicateurs de performance de base (Delta, Performance Ratio).
Ne contient aucun accès aux API, ni écriture en base de données.
"""

import pandas as pd
import numpy as np
from app.utils.logger import logger

# Constante métier centralisée
BETA_TEMPERATURE_COEFFICIENT = 0.004


class ExpectedProductionCalculator:
    """
    Classe dédiée au calcul de la production théorique et de ses métriques dérivées.
    Applique les formules physiques sur un DataFrame nettoyé.
    """

    def __init__(self, beta: float = BETA_TEMPERATURE_COEFFICIENT) -> None:
        """
        Initialise le calculateur avec le coefficient de perte de température.
        
        Args:
            beta (float): Coefficient de variation de performance lié à la température.
                          Par défaut 0.004 (soit 0.4% / °C).
        """
        self.beta = beta

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applique les calculs métiers sur le DataFrame.
        
        Args:
            df (pd.DataFrame): DataFrame nettoyé (issu du preprocessing).
            
        Returns:
            pd.DataFrame: DataFrame enrichi avec 'expected_production', 'delta' et 'performance_ratio'.
        """
        if df is None or df.empty:
            logger.warning("ExpectedProductionCalculator: Le DataFrame est vide, aucun calcul effectué.")
            return pd.DataFrame()

        # Travail sur une copie pour respecter l'immuabilité
        enriched_df = df.copy()

        logger.info("Début des calculs : Expected Production, Delta et Performance Ratio.")

        enriched_df = self._calculate_expected_production(enriched_df)
        enriched_df = self._calculate_delta(enriched_df)
        enriched_df = self._calculate_performance_ratio(enriched_df)

        logger.info("Calculs métiers terminés avec succès.")
        return enriched_df

    def _calculate_expected_production(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule la production théorique attendue selon la formule :
        ProdExpected = (ProdBudget / IrrBudget) * IrrReal * (1 - Beta * (T_reel - T_budget))
        """
        # Le preprocessing a déjà remplacé les IrrBudget = 0 par des NaN pour éviter la division par zéro
        base_ratio = df['budget_production'] / df['budget_irradiation']
        
        # Facteur de correction de température
        temp_factor = 1 - (self.beta * (df['temperature'] - df['budget_temperature']))
        
        # Calcul de la formule complète
        df['expected_production'] = base_ratio * df['irradiation'] * temp_factor
        
        # Sécurité physique : la production attendue ne peut pas être négative
        df['expected_production'] = df['expected_production'].clip(lower=0.0)
        
        return df

    def _calculate_delta(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule la différence absolue entre la production réelle et celle attendue (en kWh).
        """
        if 'expected_production' in df.columns:
            df['delta'] = df['production'] - df['expected_production']
        return df

    def _calculate_performance_ratio(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule le ratio de performance (Performance Ratio - PR).
        Formule : Production réelle / Production attendue.
        """
        if 'expected_production' in df.columns:
            # Sécurité mathématique : éviter la division par zéro si la production attendue est nulle
            safe_expected = df['expected_production'].replace(0.0, np.nan)
            df['performance_ratio'] = df['production'] / safe_expected
            
        return df
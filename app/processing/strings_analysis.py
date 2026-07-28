"""
Module d'analyse des chaînes de panneaux photovoltaïques (Strings).
Dédié au calcul de l'état de connexion, à la détection des chaînes défaillantes 
et à la comparaison des rendements relatifs par onduleur.
Ne contient aucun code d'affichage (Plotly) ni d'I/O (fichiers/API).
"""

import re
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from app.utils.logger import logger


@dataclass
class StringAnalysisResult:
    """
    Structure de données contenant les résultats synthétiques de l'analyse des strings.
    """
    connected_strings: List[str] = field(default_factory=list)
    disconnected_strings: List[str] = field(default_factory=list)
    failed_strings: List[str] = field(default_factory=list)
    active_strings_count: int = 0
    weakest_string: Optional[str] = None
    weakest_inverter: Optional[str] = None
    average_ratio: float = 0.0
    ratios: Dict[str, float] = field(default_factory=dict)


class StringAnalyzer:
    """
    Classe de traitement analytique sur les courants DC des chaînes (strings).
    """

    def __init__(
        self, 
        current_threshold: float = 0.1, 
        connection_ratio_threshold: float = 0.5,
        failure_ratio_threshold: float = 0.85
    ) -> None:
        """
        Args:
            current_threshold (float): Seuil de courant minimal (en A) pour considérer un string actif.
            connection_ratio_threshold (float): Pourcentage minimal de jours actifs pour être jugé 'connecté'.
            failure_ratio_threshold (float): Ratio sous lequel une chaîne est considérée en sous-performance/défaillante.
        """
        self.current_threshold = current_threshold
        self.connection_ratio_threshold = connection_ratio_threshold
        self.failure_ratio_threshold = failure_ratio_threshold

    def analyze(self, df: pd.DataFrame, irradiance_col: str = "irr") -> StringAnalysisResult:
        """
        Exécute l'analyse complète sur un DataFrame de mesures haute fréquence ou journalières.

        Args:
            df (pd.DataFrame): DataFrame contenant les colonnes 'I_DC' et l'irradiation.
            irradiance_col (str): Nom de la colonne d'irradiation.

        Returns:
            StringAnalysisResult: Dataclass structurée des résultats de l'analyse.
        """
        if df is None or df.empty:
            logger.warning("StringAnalyzer: DataFrame d'entrée vide.")
            return StringAnalysisResult()

        logger.info("Début de l'analyse détaillée des strings...")

        # Identification des colonnes de courant DC
        string_cols = [c for c in df.columns if "I_DC" in c]
        if not string_cols:
            logger.warning("StringAnalyzer: Aucune colonne de type 'I_DC' n'a été trouvée.")
            return StringAnalysisResult()

        # Nettoyage préalable des types
        df_work = df.copy()
        df_work[string_cols] = df_work[string_cols].apply(pd.to_numeric, errors="coerce")

        # 1. Analyse de la connexion et activité
        connected, disconnected = self._check_connections(df_work, string_cols)
        
        # Nombre moyen de strings actifs par échantillon/jour
        active_strings_series = (df_work[string_cols] > self.current_threshold).sum(axis=1)
        avg_active_count = int(round(active_strings_series.mean())) if not active_strings_series.empty else 0

        if not connected:
            logger.warning("StringAnalyzer: Aucun string connecté détecté.")
            return StringAnalysisResult(
                disconnected_strings=disconnected,
                failed_strings=disconnected,
                active_strings_count=avg_active_count
            )

        # 2. Calcul du ratio de performance par rapport à la moyenne globale
        df_active = df_work[connected].copy()
        daily_mean_global = df_active.mean(axis=1).replace(0, np.nan)
        ratio_df = df_active.divide(daily_mean_global, axis=0)

        ratios: Dict[str, float] = {}
        failed_strings: List[str] = list(disconnected)  # Les désactivés sont d'office considérés hors-service

        for col in connected:
            ratio_mean = float(ratio_df[col].mean())
            if np.isnan(ratio_mean):
                ratio_mean = 0.0
            ratios[col] = round(ratio_mean, 3)

            # Identification des sous-performances
            if ratio_mean < self.failure_ratio_threshold:
                failed_strings.append(col)

        # 3. Identification des éléments les plus faibles
        weakest_string = min(ratios, key=ratios.get) if ratios else None
        average_ratio = float(np.mean(list(ratios.values()))) if ratios else 0.0

        # 4. Identification de l'onduleur le plus faible
        weakest_inverter = self._identify_weakest_inverter(connected, ratios)

        logger.info(f"Analyse terminée: {len(connected)} connectés, {len(failed_strings)} défaillants.")

        return StringAnalysisResult(
            connected_strings=connected,
            disconnected_strings=disconnected,
            failed_strings=failed_strings,
            active_strings_count=avg_active_count,
            weakest_string=weakest_string,
            weakest_inverter=weakest_inverter,
            average_ratio=round(average_ratio, 3),
            ratios=ratios
        )

    def _check_connections(self, df: pd.DataFrame, string_cols: List[str]) -> tuple[List[str], List[str]]:
        """Sépare les strings connectés des déconnectés selon leur activité historique."""
        connected = [
            c for c in string_cols 
            if (df[c] > self.current_threshold).mean() > self.connection_ratio_threshold
        ]
        disconnected = [c for c in string_cols if c not in connected]
        return connected, disconnected

    def _identify_weakest_inverter(self, connected_strings: List[str], ratios: Dict[str, float]) -> Optional[str]:
        """Agrège les ratios par onduleur pour identifier l'onduleur le moins performant."""
        inverter_ratios: Dict[str, List[float]] = {}

        for col in connected_strings:
            # Extrait le nom de l'onduleur (ex: 'INV 1' depuis 'INV 1_DC1_1')
            match = re.search(r'(INV\s*\d+)', col, re.IGNORECASE)
            inv_name = match.group(1).upper() if match else "INV_UNKNOWN"

            if inv_name not in inverter_ratios:
                inverter_ratios[inv_name] = []
            if col in ratios:
                inverter_ratios[inv_name].append(ratios[col])

        # Calcul du ratio moyen par onduleur
        inv_means = {
            inv: np.mean(val_list) 
            for inv, val_list in inverter_ratios.items() if val_list
        }

        if not inv_means:
            return None

        return min(inv_means, key=inv_means.get)
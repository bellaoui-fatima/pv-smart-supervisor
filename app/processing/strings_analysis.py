import os
import re
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from app.utils.logger import logger

class StringAnalyzer:
    """
    Responsabilité unique : Analyse statistique avancée des courants des strings DC
    et détection des déséquilibres ou déconnexions par onduleur.
    Adapté pour traiter n'importe quelle centrale de manière dynamique.
    """

    THRESHOLD: float = 0.1
    RATIO_LOW: float = 0.85
    RATIO_HIGH: float = 1.15

    @classmethod
    def analyze_plant_strings(
        cls, 
        df_raw: pd.DataFrame, 
        plant_id: str, 
        output_plots_dir: str = "output/plots"
    ) -> Dict[str, Any]:
        """
        Exécute l'analyse complète des strings pour une centrale donnée.
        
        Args:
            df_raw (pd.DataFrame): Données brutes de la centrale contenant les courants et l'irradiation.
            plant_id (str): Identifiant unique de la centrale.
            output_plots_dir (str): Répertoire cible pour la sauvegarde des rapports HTML Plotly.
            
        Returns:
            Dict[str, Any]: Synthèse des anomalies détectées et métriques clés.
        """
        if df_raw.empty:
            logger.warning(f" Aucun enregistrement fourni pour l'analyse des strings de la centrale {plant_id}.")
            return {}

        logger.info(f" Lancement de l'analyse des strings DC pour la centrale : {plant_id}")
        
        # Copie de travail pour éviter les effets de bord (SettingWithCopyWarning)
        df = df_raw.copy()
        
        # 1. Standardisation de l'axe temporel
        time_col = 'Timestamp' if 'Timestamp' in df.columns else ('date' if 'date' in df.columns else None)
        if not time_col:
            raise KeyError("La source de données doit contenir une colonne 'Timestamp' ou 'date'.")
        
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.sort_values(time_col).reset_index(drop=True)

        # 2. Identification dynamique des colonnes de strings (I_DC) et d'irradiation
        string_cols = [c for c in df.columns if 'I_DC' in c]
        irr_col = 'irr' if 'irr' in df.columns else ('irradiation' if 'irradiation' in df.columns else None)

        if not string_cols:
            logger.warning(f" Aucune colonne de type 'I_DC' détectée pour la centrale {plant_id}. Abandon.")
            return {}
        if not irr_col:
            logger.warning(f" Colonne d'irradiation absente ou mal nommée pour {plant_id}. Calculs normalisés dégradés.")

        # Typage numérique strict
        df[string_cols] = df[string_cols].apply(pd.to_numeric, errors='coerce')
        if irr_col:
            df[irr_col] = pd.to_numeric(df[irr_col], errors='coerce')

        # 3. Analyse de l'état de connexion des strings
        # Un string est considéré connecté s'il produit (I > THRESHOLD) sur plus de 50% de la période
        connected_strings = [c for c in string_cols if (df[c] > cls.THRESHOLD).mean() > 0.5]
        disconnected_strings = [c for c in string_cols if c not in connected_strings]

        # Calcul du nombre de strings actifs à chaque pas de temps
        active_per_timestamp = (df[string_cols] > cls.THRESHOLD).sum(axis=1)

        # 4. Extraction dynamique de la liste des onduleurs présents
        inverters = sorted(set(cls._extract_inverter_id(c) for c in string_cols if cls._extract_inverter_id(c)))

        # 5. Calcul des moyennes quotidiennes normalisées par onduleur
        # Formule : $$mean\_inv(j) = \frac{1}{N} \sum_{i=1}^{N} \frac{I_i(j)}{irr(j)}$$
        inv_daily_mean = {}
        if irr_col:
            irr_safe = df[irr_col].replace(0, np.nan) # Protection division par zéro
            for inv in inverters:
                cols_inv = [c for c in connected_strings if f'INV {inv} ' in c or f'INV{inv}_' in c or c.startswith(f'INV_{inv}')]
                n = len(cols_inv)
                if n > 0:
                    inv_daily_mean[inv] = df[cols_inv].divide(irr_safe, axis=0).sum(axis=1) / n

        # 6. Comparaison des courants de chaque string par rapport à la moyenne globale
        df_active = df[connected_strings].copy()
        df_active.index = df[time_col]
        daily_mean_global = df_active.mean(axis=1)
        
        # Sécurité anti-division par zéro si la moyenne globale est nulle (nuit)
        safe_global_mean = daily_mean_global.replace(0, np.nan)
        ratio_df = df_active.divide(safe_global_mean, axis=0)

        string_alerts = []
        for col in connected_strings:
            ratio_mean = ratio_df[col].mean()
            if pd.isna(ratio_mean):
                continue
                
            status = "OK"
            if ratio_mean < cls.RATIO_LOW:
                status = "FAIBLE"
            elif ratio_mean > cls.RATIO_HIGH:
                status = "ELEVE"
                
            if status != "OK":
                string_alerts.append({
                    "string_name": col,
                    "short_name": cls._short_name(col),
                    "ratio": round(ratio_mean, 3),
                    "status": status
                })

        # 7. Génération des rapports graphiques Plotly (HTML)
        os.makedirs(output_plots_dir, exist_ok=True)
        cls._generate_plots(
            df=df,
            time_col=time_col,
            plant_id=plant_id,
            string_cols=string_cols,
            connected_strings=connected_strings,
            active_per_timestamp=active_per_timestamp,
            inverters=inverters,
            inv_daily_mean=inv_daily_mean,
            daily_mean_global=daily_mean_global,
            ratio_df=ratio_df,
            output_dir=output_plots_dir
        )

        # 8. Retour des indicateurs pour alimenter la brique diagnostic/incidents
        return {
            "plant_id": plant_id,
            "total_strings_count": len(string_cols),
            "connected_strings_count": len(connected_strings),
            "disconnected_strings_count": len(disconnected_strings),
            "disconnected_strings_list": disconnected_strings,
            "anomalous_strings": string_alerts
        }

    @staticmethod
    def _extract_inverter_id(col_name: str) -> str:
        """Extrait l'identifiant numérique ou textuel de l'onduleur depuis le nom de colonne."""
        match = re.search(r'INV\s*[-_]?\s*(\d+)', col_name, re.IGNORECASE)
        return match.group(1) if match else ""

    @staticmethod
    def _short_name(col: str) -> str:
        """Génère un libellé court et lisible pour les graphiques Plotly."""
        m = re.search(r'INV\s*(\d+).*I_DC(\d+_\d+|\d+)', col, re.IGNORECASE)
        return f"INV{m.group(1)}_DC{m.group(2)}" if m else col

    @classmethod
    def _generate_plots(
        cls, df: pd.DataFrame, time_col: str, plant_id: str, string_cols: List[str],
        connected_strings: List[str], active_per_timestamp: pd.Series, inverters: List[str],
        inv_daily_mean: Dict[str, pd.Series], daily_mean_global: pd.Series, ratio_df: pd.DataFrame,
        output_dir: str
    ) -> None:
        """Centralise la génération et l'écriture des fichiers HTML interactifs."""
        COLORS = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf']

        # --- Graphique 1: Strings actifs par jour ---
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=df[time_col], y=active_per_timestamp.values, name='Strings actifs', marker_color='steelblue'))
        fig1.add_hline(y=len(connected_strings), line_dash='dash', line_color='green', annotation_text=f'Connectés ({len(connected_strings)})')
        fig1.update_layout(title=f"Centrale {plant_id} - Nombre de strings actifs (I > {cls.THRESHOLD} A)", yaxis_title="Nb strings", xaxis_title="Date")
        fig1.write_html(os.path.join(output_dir, f'{plant_id}_strings_actifs.html'))

        # --- Graphique 2: Moyenne quotidienne normalisée par onduleur ---
        if inv_daily_mean:
            fig2 = make_subplots(rows=len(inverters), cols=1, shared_xaxes=True, subplot_titles=[f"INV {inv} – Moyenne normalisée" for inv in inverters])
            for i, inv in enumerate(inverters, 1):
                if inv in inv_daily_mean:
                    fig2.add_trace(go.Scatter(x=df[time_col], y=inv_daily_mean[inv], mode='lines', name=f'INV {inv}'), row=i, col=1)
            fig2.update_layout(title=f"Centrale {plant_id} - Moyenne quotidienne normalisée (I / irr)", height=250 * len(inverters))
            fig2.write_html(os.path.join(output_dir, f'{plant_id}_moyenne_onduleurs.html'))

        # --- Graphique 3 & 4: Profils et Ratios individuels par Onduleur ---
        for inv in inverters:
            cols_inv = [c for c in connected_strings if f'INV {inv} ' in c or f'INV{inv}_' in c or c.startswith(f'INV_{inv}')]
            if not cols_inv:
                continue

            # Profils de courants
            fig_p = go.Figure()
            for j, col in enumerate(cols_inv):
                fig_p.add_trace(go.Scatter(x=df[time_col], y=df[col], mode='lines', name=cls._short_name(col), line=dict(color=COLORS[j % len(COLORS)], width=1.5)))
            fig_p.add_trace(go.Scatter(x=df[time_col], y=daily_mean_global.values, mode='lines', name='Moyenne globale', line=dict(color='black', width=2, dash='dash')))
            fig_p.update_layout(title=f"Centrale {plant_id} - Courants strings Onduleur {inv}", yaxis_title="Courant DC (A)", xaxis_title="Date")
            fig_p.write_html(os.path.join(output_dir, f'{plant_id}_profil_INV{inv}.html'))

            # Ratios d'écarts
            fig_r = go.Figure()
            for j, col in enumerate(cols_inv):
                if col in ratio_df.columns:
                    fig_r.add_trace(go.Scatter(x=df[time_col], y=ratio_df[col], mode='lines', name=cls._short_name(col), line=dict(color=COLORS[j % len(COLORS)], width=1.5)))
            fig_r.add_hline(y=1.0, line_dash='dash', line_color='black', annotation_text='Référence')
            fig_r.add_hline(y=cls.RATIO_LOW, line_dash='dot', line_color='red', annotation_text=f'-{int((1-cls.RATIO_LOW)*100)}%')
            fig_r.add_hline(y=cls.RATIO_HIGH, line_dash='dot', line_color='orange', annotation_text=f'+{int((cls.RATIO_HIGH-1)*100)}%')
            fig_r.update_layout(title=f"Centrale {plant_id} - Ratios d'écart Onduleur {inv}", yaxis_title="Ratio", xaxis_title="Date")
            fig_r.write_html(os.path.join(output_dir, f'{plant_id}_ratio_INV{inv}.html'))
            
        logger.info(f" Fichiers HTML d'analyse visuelle générés avec succès dans '{output_dir}'.")
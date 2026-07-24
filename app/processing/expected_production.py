from typing import List, Dict, Any
import pandas as pd
import numpy as np
from app.utils.logger import logger

class ExpectedProductionCalculator:
    """
    Responsabilité unique : Calculer la production attendue (théorique) et 
    le delta de performance à partir des mesures nettoyées.
    """
    
    # Coefficient de dégradation thermique par défaut (0.4% par degré Celsius)
    BETA: float = 0.004

    @classmethod
    def compute_expected_production(cls, cleaned_measures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calcule la production attendue et le delta pour un ensemble de mesures.
        
        Formule mathématique appliquée :
        $$ProdExpected = \\frac{ProdBudget}{IrradiationBudget} \\times IrradiationReal \\times (1 - \\beta \\times (T_{reel} - T_{budget}))$$
        
        Delta de performance :
        $$Delta = \\frac{ProdReelle}{ProdExpected} - 1$$
        """
        if not cleaned_measures:
            return []

        logger.info(f" Lancement du calcul de productible attendu sur {len(cleaned_measures)} enregistrement(s)...")
        
        # Chargement dans un DataFrame pour bénéficier de la vectorisation de Pandas/NumPy
        df = pd.DataFrame(cleaned_measures)

        # Liste des colonnes requises pour le calcul (noms normalisés issus du Preprocessor)
        required_cols = [
            "production", "temperature", "irradiation", 
            "budget_production", "budget_irradiation", "budget_temperature"
        ]

        # Sécurité : s'assurer que toutes les colonnes numériques nécessaires sont exploitables
        for col in required_cols:
            if col not in df.columns:
                df[col] = np.nan
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # --- Étape 1 : Calcul de la Production Attendue (Expected Production) ---
        # Sécurité anti division par zéro si l'irradiation budgétée est nulle ou absente
        safe_irradiation_budget = np.where(
            (df["budget_irradiation"].isna()) | (df["budget_irradiation"] == 0),
            np.nan,
            df["budget_irradiation"]
        )

        # Application stricte de la formule PV
        df["expected_production"] = (
            (df["budget_production"] / safe_irradiation_budget) * 
            df["irradiation"] * 
            (1 - cls.BETA * (df["temperature"] - df["budget_temperature"]))
        )

        # En cas d'irradiation réelle nulle, la production attendue est mathématiquement de 0
        df.loc[df["irradiation"] == 0, "expected_production"] = 0.0

        # --- Étape 2 : Calcul du Delta de Performance ---
        # Sécurité anti division par zéro si la production attendue calculée est nulle ou négative
        safe_expected_prod = np.where(
            (df["expected_production"].isna()) | (df["expected_production"] <= 0),
            np.nan,
            df["expected_production"]
        )

        df["delta"] = (df["production"] / safe_expected_prod) - 1.0

        # --- Étape 3 : Nettoyage final avant conversion ---
        # Remplacement des infinis (générés par des divisions limites) et des NaN par None pour SQLAlchemy
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.replace({np.nan: None})

        return df.to_dict(orient="records")
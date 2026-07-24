"""
Module utilitaire pour la validation des données entrantes.
Vérifie la cohérence des structures de données avant leur traitement ou persistance.
"""

from typing import Any, Dict


def validate_inverter_measure(measure: Dict[str, Any]) -> bool:
    """
    Valide qu'un dictionnaire de mesure d'onduleur contient les clés essentielles.

    Args:
        measure (Dict[str, Any]): Dictionnaire représentant une mesure.

    Returns:
        bool: True si la mesure est valide, False sinon.
    """
    if not isinstance(measure, dict):
        return False
    
    required_keys = ["Value"]
    return all(key in measure for key in required_keys)


def validate_plant_payload(plant_data: Dict[str, Any]) -> bool:
    """
    Valide les données de base d'une centrale photovoltaïque.

    Args:
        plant_data (Dict[str, Any]): Données de la centrale.

    Returns:
        bool: True si les identifiants clés sont présents.
    """
    if not isinstance(plant_data, dict):
        return False
        
    return bool(plant_data.get("name")) and (bool(plant_data.get("rawametrix_id")) or bool(plant_data.get("ID")))
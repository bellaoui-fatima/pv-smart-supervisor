"""
Module utilitaire pour la gestion et le formatage des dates.
Centralise les fonctions de conversion et de normalisation temporelle
(timestamps, formats OData, ISO, etc.).
"""

from datetime import datetime, timezone


def format_iso_to_readable(date_str: str) -> str:
    """
    Convertit une chaîne de date au format ISO (ex: 2026-07-20T12:00:00Z)
    en un format lisible (YYYY-MM-DD HH:MM:SS).

    Args:
        date_str (str): Chaîne de date brute au format ISO.

    Returns:
        str: Date formatée ou la chaîne d'origine en cas d'échec.
    """
    if not date_str:
        return "N/A"
    
    try:
        cleaned = date_str.replace("T", " ").replace("Z", "")
        # Tronque les microsecondes si présentes
        if "." in cleaned:
            cleaned = cleaned.split(".")[0]
        return cleaned
    except Exception:
        return date_str


def get_current_utc_date_str() -> str:
    """
    Récupère la date UTC courante au format chaîne YYYY-MM-DD.

    Returns:
        str: La date du jour au format YYYY-MM-DD.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
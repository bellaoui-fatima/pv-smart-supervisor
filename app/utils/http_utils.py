"""
Module utilitaire pour les opérations HTTP transverses.
Gère les retries, les délais anti-congestion (rate limiting)
et l'encodage des requêtes.
"""

import time
from typing import Callable, Any
from app.utils.logger import logger


def throttle_request(delay_seconds: float = 2.0) -> None:
    """
    Applique une pause pour respecter les limites de taux (rate limiting) des APIs.

    Args:
        delay_seconds (float): Temps de pause en secondes.
    """
    time.sleep(delay_seconds)


def retry_on_exception(func: Callable[..., Any], retries: int = 3, delay: float = 2.0) -> Callable[..., Any]:
    """
    Décorateur ou fonction utilitaire pour réitérer une action en cas d'échec réseau.

    Args:
        func (Callable): Fonction à exécuter.
        retries (int): Nombre maximal de tentatives.
        delay (float): Délai initial entre les essais.

    Returns:
        Callable: Résultat de la fonction exécutée.
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        attempt = 0
        while attempt < retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                attempt += 1
                logger.warning(f"Échec de l'appel ({attempt}/{retries}) : {e}. Nouvelle tentative dans {delay}s...")
                time.sleep(delay)
                if attempt == retries:
                    logger.error("Nombre maximal de tentatives atteint. Abandon.")
                    raise
    return wrapper
"""
Module de gestion des logs.
Configure l'enregistrement des événements de l'application dans la console
et dans un fichier de log dédié, en remplaçant l'usage de 'print'.
"""

import logging
import os
import sys
from app.config.settings import settings


def _setup_logger() -> logging.Logger:
    """
    Configure et retourne le logger principal de l'application.
    Crée le dossier 'logs' s'il n'existe pas et initialise les sorties
    vers la console et le fichier 'application.log'.
    
    Returns:
        logging.Logger: L'instance du logger configurée.
    """
    logger = logging.getLogger("pv_supervision")
    
    # Éviter de dupliquer les handlers si la fonction est appelée plusieurs fois
    if logger.hasHandlers():
        return logger

    # Récupération et validation du niveau de log depuis la configuration
    log_level_str = settings.log_level.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(log_level)

    # Format standardisé pour tous les logs
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Sortie Console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Sortie Fichier (logs/application.log)
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    file_path = os.path.join(log_dir, "application.log")
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# Instance globale à importer dans tous les autres modules avec :
# from app.utils.logger import logger
logger = _setup_logger()
"""
Module de gestion de la base de données.
Configure le moteur SQLAlchemy, la fabrique de sessions et la base déclarative
pour l'ensemble des modèles ORM.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config.settings import settings

# Création du moteur SQLAlchemy avec pool_pre_ping pour la robustesse de la connexion
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True
)

# Configuration de la fabrique de sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True
)

# Classe de base pour la définition des modèles ORM
Base = declarative_base()


def get_db_session() -> Generator[Session, None, None]:
    """
    Fournit une session de base de données via un générateur (pattern context manager).
    Garantit la fermeture systématique de la session après utilisation.

    Yields:
        Session: Une session active SQLAlchemy.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
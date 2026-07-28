"""
Module des modèles SQLAlchemy ORM.
Définit l'ensemble des tables relationnelles du projet (Plant, Inverter,
DailyMeasure, Loss, Incident, Alert) et leurs liaisons.
"""

from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import relationship
from app.database.database import Base


class Plant(Base):
    """Modèle représentant une centrale photovoltaïque."""
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rawametrix_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    capacity = Column(Float, nullable=True)
    commissioning_date = Column(DateTime, nullable=True)

    # Relations
    inverters = relationship("Inverter", back_populates="plant", cascade="all, delete-orphan")
    daily_measures = relationship("DailyMeasure", back_populates="plant", cascade="all, delete-orphan")
    losses = relationship("Loss", back_populates="plant", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="plant", cascade="all, delete-orphan")


class Inverter(Base):
    """Modèle représentant un onduleur rattaché à une centrale."""
    __tablename__ = "inverters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    energysoft_id = Column(String(100), unique=True, nullable=False, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=True)
    communication = Column(String(50), nullable=True)
    last_update = Column(DateTime, nullable=True)

    # Relation
    plant = relationship("Plant", back_populates="inverters")


class DailyMeasure(Base):
    """
    Modèle représentant les mesures journalières agrégées d'une centrale, 
    enrichies par la couche de Feature Engineering pour l'IA.
    """
    __tablename__ = "daily_measures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    
    # --- Données Brutes (Raw Data issues de l'API) ---
    production = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    irradiation = Column(Float, nullable=True)
    budget_production = Column(Float, nullable=True)
    budget_irradiation = Column(Float, nullable=True)
    budget_temperature = Column(Float, nullable=True)
    
    # --- Features de Production ---
    expected_production = Column(Float, nullable=True, comment="Production théorique attendue (kWh)")
    delta = Column(Float, nullable=True, comment="Différence entre production réelle et attendue (kWh)")
    performance_ratio = Column(Float, nullable=True, comment="Ratio de performance (Prod réelle / Prod attendue)")

    # --- Features Météo ---
    temperature_gap = Column(Float, nullable=True, comment="Écart de température par rapport à la référence")
    irradiation_ratio = Column(Float, nullable=True, comment="Ratio d'irradiation (Réelle / Budget)")

    # --- Features Pertes ---
    loss_percentage = Column(Float, nullable=True, comment="Pourcentage de pertes déclarées")

    # --- Features Équipements (Strings & Inverters) ---
    offline_inverters = Column(Integer, nullable=True, comment="Nombre d'onduleurs hors ligne")
    failed_strings = Column(Integer, nullable=True, comment="Nombre de chaînes (strings) défaillantes")
    communication_status = Column(Boolean, nullable=True, comment="État global de la communication de la centrale")

    # --- Features Temporelles ---
    rolling_mean_7d = Column(Float, nullable=True, comment="Moyenne glissante de la production sur 7 jours")
    rolling_std_7d = Column(Float, nullable=True, comment="Écart-type glissant de la production sur 7 jours")
    
    # --- Feature de Qualité / Métier ---
    anomaly_score_rule = Column(Float, nullable=True, comment="Score d'anomalie calculé via règles expertes")

    # Relation
    plant = relationship("Plant", back_populates="daily_measures")


class Loss(Base):
    """Modèle représentant les pertes énergétiques journalières d'une centrale."""
    __tablename__ = "losses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    loss_energy = Column(Float, nullable=True)
    loss_category = Column(String(100), nullable=True)
    loss_cause = Column(String(100), nullable=True)
    loss_type = Column(String(100), nullable=True)

    # Relation
    plant = relationship("Plant", back_populates="losses")


class Incident(Base):
    """Modèle représentant un incident détecté sur une centrale."""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    priority = Column(String(50), nullable=False)
    diagnosis = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(String(50), nullable=False, default="New")
    notification_sent = Column(Boolean, nullable=False, default=False)
    ticket_id = Column(String(100), nullable=True)

    # Relations
    plant = relationship("Plant", back_populates="incidents")
    alerts = relationship("Alert", back_populates="incident", cascade="all, delete-orphan")


class Alert(Base):
    """Modèle représentant l'historique des notifications émises pour un incident."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    telegram = Column(Boolean, nullable=False, default=False)
    email = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relation
    incident = relationship("Incident", back_populates="alerts")
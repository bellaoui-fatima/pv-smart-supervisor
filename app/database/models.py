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
    """Modèle représentant les mesures journalières agrégées d'une centrale."""
    __tablename__ = "daily_measures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    production = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    irradiation = Column(Float, nullable=True)
    budget_production = Column(Float, nullable=True)
    budget_irradiation = Column(Float, nullable=True)
    budget_temperature = Column(Float, nullable=True)
    expected_production = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)

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
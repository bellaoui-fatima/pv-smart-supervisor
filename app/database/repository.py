"""
Module du repository de base de données.
Centralise toutes les opérations de persistance et de récupération des données
pour isoler la logique métier des appels SQL directs (pattern Repository).
"""

from typing import List, Optional, Type, Dict, Any
from datetime import datetime, date
import pandas as pd
from sqlalchemy.orm import Session
from app.database.models import Plant, Inverter, DailyMeasure, Loss, Incident, Alert
from app.utils.logger import logger


class DatabaseRepository:
    """Classe gérant les interactions avec la base de données via SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _coerce_datetime(value) -> Optional[datetime]:
        """Convertit une valeur temporelle en objet Python datetime compatible SQLAlchemy."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, datetime.min.time())
        if hasattr(value, "to_pydatetime"):
            try:
                return value.to_pydatetime()
            except Exception:
                pass
        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return None
            for fmt in (
                "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f"
            ):
                try:
                    return datetime.strptime(raw_value, fmt)
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            except ValueError:
                try:
                    return datetime.combine(date.fromisoformat(raw_value), datetime.min.time())
                except ValueError:
                    logger.warning(f"Valeur de date non interprétable : {value}")
                    return None
        return value

    def save_features(self, plant_id: int, features_data: List[dict]) -> None:
        """
        Enregistre ou met à jour les features et mesures agrégées pour une centrale.
        """
        feature_keys = [
            "production", "temperature", "irradiation", "budget_production", 
            "budget_irradiation", "budget_temperature", "expected_production", 
            "delta", "performance_ratio", "temperature_gap", "irradiation_ratio", 
            "loss_percentage", "offline_inverters", "failed_strings", 
            "communication_status", "rolling_mean_7d", "rolling_std_7d", 
            "anomaly_score_rule"
        ]

        for data in features_data:
            measure_date = self._coerce_datetime(data.get("date"))
            if not measure_date:
                continue

            existing = self.session.query(DailyMeasure).filter_by(
                plant_id=plant_id, date=measure_date
            ).first()

            if existing:
                for key in feature_keys:
                    if key in data and data[key] is not None:
                        # Conversion NaN pandas -> None pour SQL
                        val = data[key]
                        if isinstance(val, float) and pd.isna(val):
                            val = None
                        setattr(existing, key, val)
            else:
                new_measure = DailyMeasure(plant_id=plant_id, date=measure_date)
                for key in feature_keys:
                    if key in data and data[key] is not None:
                        val = data[key]
                        if isinstance(val, float) and pd.isna(val):
                            val = None
                        setattr(new_measure, key, val)
                self.session.add(new_measure)

        self.session.commit()
        logger.info(f"Features enregistrées avec succès pour la centrale ID {plant_id}.")

    def get_latest_features(self, plant_id: int) -> Optional[DailyMeasure]:
        """Récupère la ligne de features la plus récente pour une centrale donnée."""
        return (
            self.session.query(DailyMeasure)
            .filter_by(plant_id=plant_id)
            .order_by(DailyMeasure.date.desc())
            .first()
        )

    def get_features_by_plant(
        self, 
        plant_id: int, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> List[DailyMeasure]:
        """Récupère l'historique des features pour une centrale sur une plage temporelle."""
        query = self.session.query(DailyMeasure).filter(DailyMeasure.plant_id == plant_id)
        
        if start_date:
            query = query.filter(DailyMeasure.date >= start_date)
        if end_date:
            query = query.filter(DailyMeasure.date <= end_date)

        return query.order_by(DailyMeasure.date.asc()).all()

    def update_features(self, plant_id: int, measure_date: datetime, feature_dict: Dict[str, Any]) -> None:
        """Met à jour un sous-ensemble spécifique de features pour un jour donné."""
        target_date = self._coerce_datetime(measure_date)
        existing = self.session.query(DailyMeasure).filter_by(
            plant_id=plant_id, date=target_date
        ).first()

        if existing:
            for key, val in feature_dict.items():
                if hasattr(existing, key):
                    if isinstance(val, float) and pd.isna(val):
                        val = None
                    setattr(existing, key, val)
            self.session.commit()
            logger.info(f"Features mises à jour pour la centrale {plant_id} au {target_date}.")
        else:
            logger.warning(f"Impossible de mettre à jour : aucune mesure trouvée au {target_date}.")

    # --- Méthodes existantes conservées ---
    def save_plants(self, plants_data: List[dict]) -> None:
        for data in plants_data:
            raw_id = data.get("rawametrix_id") or data.get("id") or data.get("plant_id")
            if raw_id is None:
                continue
            rawa_id = str(raw_id)
            name = data.get("name") or data.get("plant_name") or f"Plant {rawa_id}"
            existing = self.session.query(Plant).filter_by(rawametrix_id=rawa_id).first()
            if existing:
                existing.name = name or existing.name
            else:
                new_plant = Plant(
                    rawametrix_id=rawa_id,
                    name=name,
                    location=data.get("location"),
                    capacity=data.get("capacity"),
                    commissioning_date=self._coerce_datetime(data.get("commissioning_date"))
                )
                self.session.add(new_plant)
        self.session.commit()

    def save_inverters(self, plant_id: int, inverters_data: List[dict]) -> None:
        for data in inverters_data:
            if not data:
                continue
            raw_es_id = data.get("energysoft_id") or data.get("ID") or data.get("id")
            if raw_es_id is None:
                continue
            es_id = str(raw_es_id)
            existing = self.session.query(Inverter).filter_by(energysoft_id=es_id).first()
            if existing:
                existing.status = data.get("status", existing.status)
                existing.communication = data.get("communication", existing.communication)
            else:
                new_inverter = Inverter(
                    energysoft_id=es_id,
                    plant_id=plant_id,
                    name=data.get("name", f"Inverter {es_id}"),
                    status=data.get("status"),
                    communication=data.get("communication")
                )
                self.session.add(new_inverter)
        self.session.commit()

    def save_losses(self, plant_id: int, losses_data: List[dict]) -> None:
        for data in losses_data:
            loss_date = self._coerce_datetime(data.get("date"))
            loss_type = data.get("loss_type")
            existing = self.session.query(Loss).filter_by(
                plant_id=plant_id, date=loss_date, loss_type=loss_type
            ).first()
            if not existing:
                new_loss = Loss(
                    plant_id=plant_id,
                    date=loss_date,
                    loss_energy=data.get("loss_energy"),
                    loss_category=data.get("loss_category"),
                    loss_cause=data.get("loss_cause"),
                    loss_type=loss_type
                )
                self.session.add(new_loss)
        self.session.commit()

    def save_incident(self, incident_data: dict) -> Incident:
        new_incident = Incident(
            plant_id=incident_data.get("plant_id"),
            timestamp=self._coerce_datetime(incident_data.get("timestamp", datetime.utcnow())),
            priority=incident_data.get("priority"),
            diagnosis=incident_data.get("diagnosis"),
            confidence=incident_data.get("confidence"),
            status=incident_data.get("status", "New"),
            notification_sent=incident_data.get("notification_sent", False),
            ticket_id=incident_data.get("ticket_id")
        )
        self.session.add(new_incident)
        self.session.commit()
        self.session.refresh(new_incident)
        return new_incident

    def get_last_measure(self, plant_id: int) -> Optional[DailyMeasure]:
        return self.session.query(DailyMeasure).filter_by(plant_id=plant_id).order_by(DailyMeasure.date.desc()).first()

    def get_active_incidents(self) -> List[Incident]:
        return self.session.query(Incident).filter(Incident.status != "Resolved").all()
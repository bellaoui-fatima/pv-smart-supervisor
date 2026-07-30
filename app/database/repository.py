"""
Module du repository de base de données.
Centralise toutes les opérations de persistance et de récupération des données
pour isoler la logique métier des appels SQL directs (pattern Repository).
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date
import json
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

    # =========================================================================
    # --- Gestion des Features et Mesures ---
    # =========================================================================

    def save_features(self, plant_id: int, features_data: List[dict]) -> None:
        """Enregistre ou met à jour les features et mesures agrégées pour une centrale."""
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

    # =========================================================================
    # --- Gestion des Entités de Référence (Plants, Inverters, Losses) ---
    # =========================================================================

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

    # =========================================================================
    # --- Gestion Explicable des Incidents (Milestone 3.5 & XAI) ---
    # =========================================================================

    def save_incident_report(self, report_data: Union[dict, Any]) -> Incident:
        """
        Enregistre un rapport d'incident complet et expliqué en base de données.
        Accepte un dictionnaire, un objet IncidentDomain ou une instance d'IncidentReport.
        """
        if hasattr(report_data, "to_repository_dict"):
            data = report_data.to_repository_dict()
        elif hasattr(report_data, "to_dict"):
            data = report_data.to_dict()
        elif isinstance(report_data, dict):
            data = report_data
        else:
            raise ValueError("save_incident_report: format de données non supporté.")

        created_at = self._coerce_datetime(
            data.get("created_at") or data.get("date") or datetime.utcnow()
        )

        new_incident = Incident(
            plant_id=data.get("plant_id", 1),
            created_at=created_at,
            incident_type=data.get("incident_type", "Anomaly"),
            priority=data.get("priority", "MEDIUM"),
            confidence=data.get("confidence", 0.0),
            rule_score=data.get("rule_score"),
            ai_score=data.get("ai_score"),
            
            # Champs XAI / Explicabilité
            diagnosis=data.get("diagnosis"),
            explanation=data.get("explanation"),
            recommendation=data.get("recommendation"),
            triggered_rules=data.get("triggered_rules"),
            evidence=data.get("evidence"),
            feature_snapshot=data.get("feature_snapshot"),
            decision_trace=data.get("decision_trace"),
            
            # Suivi
            status=data.get("status", "OPEN"),
            notification_sent=data.get("notification_sent", False),
            ticket_id=data.get("ticket_id")
        )

        self.session.add(new_incident)
        self.session.commit()
        self.session.refresh(new_incident)
        
        logger.info(
            f"Rapport d'Incident #{new_incident.id} enregistré pour la centrale {new_incident.plant_id} "
            f"[Priorité: {new_incident.priority} | Diagnostic: {new_incident.diagnosis}]."
        )
        return new_incident

    def get_incident_report(self, incident_id: int) -> Optional[Incident]:
        """Récupère un rapport d'incident complet par son identifiant unique."""
        return self.session.query(Incident).filter_by(id=incident_id).first()

    def update_incident_status(
        self, 
        incident_id: int, 
        status: str, 
        notes: Optional[str] = None
    ) -> Optional[Incident]:
        """
        Met à jour le statut d'un incident (ex: OPEN, IN_PROGRESS, RESOLVED, CLOSED).
        Ajuste automatiquement la date de résolution si l'incident est clos.
        """
        incident = self.session.query(Incident).filter_by(id=incident_id).first()
        if not incident:
            logger.warning(f"update_incident_status: Incident #{incident_id} introuvable.")
            return None

        clean_status = status.upper()
        incident.status = clean_status

        if clean_status in ["RESOLVED", "CLOSED"]:
            incident.resolved_at = datetime.utcnow()

        if notes:
            # Traitement sécurisé selon que recommendation est un tableau JSON ou du texte
            if isinstance(incident.recommendation, list):
                updated_reco = list(incident.recommendation)
                updated_reco.append(f"Note d'intervention : {notes}")
                incident.recommendation = updated_reco
            elif incident.recommended_action:
                incident.recommended_action += f" | Note : {notes}"
            else:
                incident.recommended_action = f"Note : {notes}"

        self.session.commit()
        self.session.refresh(incident)
        logger.info(f"Incident #{incident_id} mis à jour vers le statut [{incident.status}].")
        return incident

    def list_open_incidents(self, plant_id: Optional[int] = None) -> List[Incident]:
        """Récupère tous les incidents en cours non résolus (OPEN, IN_PROGRESS, New)."""
        query = self.session.query(Incident).filter(
            Incident.status.in_(["OPEN", "IN_PROGRESS", "New"])
        )
        if plant_id is not None:
            query = query.filter(Incident.plant_id == plant_id)

        return query.order_by(Incident.created_at.desc()).all()

    def list_closed_incidents(self, plant_id: Optional[int] = None) -> List[Incident]:
        """Récupère tous les incidents archivés/résolus (RESOLVED, CLOSED)."""
        query = self.session.query(Incident).filter(
            Incident.status.in_(["RESOLVED", "CLOSED"])
        )
        if plant_id is not None:
            query = query.filter(Incident.plant_id == plant_id)

        return query.order_by(Incident.created_at.desc()).all()

    # --- Alias de rétrocompatibilité (évite de casser l'existant) ---

    def save_incident(self, incident_data: dict) -> Incident:
        """Redirige vers save_incident_report pour compatibilité ascendante."""
        return self.save_incident_report(incident_data)

    def update_incident(self, incident_id: int, update_data: dict) -> Optional[Incident]:
        """Met à jour un dictionnaire d'attributs arbitraires sur un incident."""
        incident = self.session.query(Incident).filter_by(id=incident_id).first()
        if not incident:
            logger.warning(f"update_incident: Incident #{incident_id} introuvable.")
            return None

        for key, val in update_data.items():
            if hasattr(incident, key):
                if key in ["created_at", "resolved_at"]:
                    val = self._coerce_datetime(val)
                setattr(incident, key, val)

        self.session.commit()
        self.session.refresh(incident)
        logger.info(f"Incident #{incident_id} mis à jour avec succès.")
        return incident

    def get_open_incidents(self, plant_id: Optional[int] = None) -> List[Incident]:
        """Alias pour list_open_incidents."""
        return self.list_open_incidents(plant_id=plant_id)

    def close_incident(self, incident_id: int, resolution_notes: Optional[str] = None) -> Optional[Incident]:
        """Alias spécialisé pour update_incident_status vers RESOLVED."""
        return self.update_incident_status(incident_id, status="RESOLVED", notes=resolution_notes)

    def get_incidents_by_plant(self, plant_id: int, status: Optional[str] = None) -> List[Incident]:
        """Récupère l'historique des incidents d'une centrale, optionnellement filtré par statut."""
        query = self.session.query(Incident).filter(Incident.plant_id == plant_id)
        if status:
            query = query.filter(Incident.status == status.upper())
        return query.order_by(Incident.created_at.desc()).all()
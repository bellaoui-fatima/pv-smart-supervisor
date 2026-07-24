"""
Module du repository de base de données.
Centralise toutes les opérations de persistance et de récupération des données
pour isoler la logique métier des appels SQL directs (pattern Repository).
"""

from typing import List, Optional, Type
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.database.models import Plant, Inverter, DailyMeasure, Loss, Incident, Alert
from app.utils.logger import logger


class DatabaseRepository:
    """Classe gérant les interactions avec la base de données via SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        """
        Initialise le repository avec une session active.

        Args:
            session (Session): Session SQLAlchemy active.
        """
        self.session = session

    @staticmethod
    def _coerce_datetime(value):
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
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S.%f",
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

    def save_plants(self, plants_data: List[dict]) -> None:
        """
        Enregistre ou met à jour une liste de centrales.

        Args:
            plants_data (List[dict]): Liste des dictionnaires contenant les données des centrales.
        """
        for data in plants_data:
            raw_id = data.get("rawametrix_id") or data.get("id") or data.get("plant_id")
            if raw_id is None:
                logger.warning("Centrale ignorée : identifiant Rawametrix absent.")
                continue

            rawa_id = str(raw_id)
            name = data.get("name") or data.get("plant_name") or f"Plant {rawa_id}"
            location = data.get("location")
            capacity = data.get("capacity")
            commissioning_date = self._coerce_datetime(data.get("commissioning_date"))

            existing = self.session.query(Plant).filter_by(rawametrix_id=rawa_id).first()
            
            if existing:
                existing.name = name or existing.name
                existing.location = location or existing.location
                existing.capacity = capacity if capacity is not None else existing.capacity
                existing.commissioning_date = commissioning_date or existing.commissioning_date
            else:
                new_plant = Plant(
                    rawametrix_id=rawa_id,
                    name=name,
                    location=location,
                    capacity=capacity,
                    commissioning_date=commissioning_date
                )
                self.session.add(new_plant)
        
        self.session.commit()
        logger.info(f"{len(plants_data)} centrales traitées et sauvegardées.")

    def save_measures(self, plant_id: int, measures_data: List[dict]) -> None:
        """
        Enregistre les mesures journalières pour une centrale.

        Args:
            plant_id (int): Identifiant interne de la centrale.
            measures_data (List[dict]): Liste des mesures journalières.
        """
        for data in measures_data:
            measure_date = self._coerce_datetime(data.get("date"))
            existing = self.session.query(DailyMeasure).filter_by(
                plant_id=plant_id, date=measure_date
            ).first()

            if existing:
                existing.production = data.get("production", existing.production)
                existing.temperature = data.get("temperature", existing.temperature)
                existing.irradiation = data.get("irradiation", existing.irradiation)
                existing.budget_production = data.get("budget_production", existing.budget_production)
                existing.budget_irradiation = data.get("budget_irradiation", existing.budget_irradiation)
                existing.budget_temperature = data.get("budget_temperature", existing.budget_temperature)
            else:
                new_measure = DailyMeasure(
                    plant_id=plant_id,
                    date=measure_date,
                    production=data.get("production"),
                    temperature=data.get("temperature"),
                    irradiation=data.get("irradiation"),
                    budget_production=data.get("budget_production"),
                    budget_irradiation=data.get("budget_irradiation"),
                    budget_temperature=data.get("budget_temperature")
                )
                self.session.add(new_measure)

        self.session.commit()
        logger.info(f"Mesures journalières sauvegardées pour la centrale ID {plant_id}.")

    def save_losses(self, plant_id: int, losses_data: List[dict]) -> None:
        """
        Enregistre les pertes énergétiques pour une centrale.

        Args:
            plant_id (int): Identifiant interne de la centrale.
            losses_data (List[dict]): Liste des données de pertes.
        """
        for data in losses_data:
            loss_date = self._coerce_datetime(data.get("date"))
            loss_type = data.get("loss_type")
            
            existing = self.session.query(Loss).filter_by(
                plant_id=plant_id, date=loss_date, loss_type=loss_type
            ).first()

            if existing:
                existing.loss_energy = data.get("loss_energy", existing.loss_energy)
                existing.loss_category = data.get("loss_category", existing.loss_category)
                existing.loss_cause = data.get("loss_cause", existing.loss_cause)
            else:
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
        logger.info(f"Pertes sauvegardées pour la centrale ID {plant_id}.")

    def save_inverters(self, plant_id: int, inverters_data: List[dict]) -> None:
        """
        Enregistre ou met à jour la liste des onduleurs d'une centrale.

        Args:
            plant_id (int): Identifiant interne de la centrale.
            inverters_data (List[dict]): Liste des données des onduleurs.
        """
        for data in inverters_data:
            if not data:
                continue

            raw_es_id = data.get("energysoft_id") or data.get("ID") or data.get("id")
            if raw_es_id is None:
                continue

            es_id = str(raw_es_id)
            existing = self.session.query(Inverter).filter_by(energysoft_id=es_id).first()
            last_update = self._coerce_datetime(data.get("last_update"))

            name = data.get("name") or data.get("Name") or data.get("serial_number") or data.get("SerialNumber")
            status = data.get("status") or data.get("Status")
            communication = data.get("communication") or data.get("Communication")

            if existing:
                existing.name = name or existing.name
                existing.status = status or existing.status
                existing.communication = communication or existing.communication
                existing.last_update = last_update if last_update is not None else existing.last_update
            else:
                if not name:
                    name = f"Inverter {es_id}"

                new_inverter = Inverter(
                    energysoft_id=es_id,
                    plant_id=plant_id,
                    name=name,
                    status=status,
                    communication=communication,
                    last_update=last_update
                )
                self.session.add(new_inverter)

        self.session.commit()
        logger.info(f"Onduleurs sauvegardés pour la centrale ID {plant_id}.")

    def save_incident(self, incident_data: dict) -> Incident:
        """
        Enregistre un nouvel incident dans la base de données.

        Args:
            incident_data (dict): Dictionnaire contenant les attributs de l'incident.

        Returns:
            Incident: L'objet Incident créé ou mis à jour.
        """
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
        logger.info(f"Incident enregistré pour la centrale ID {new_incident.plant_id}.")
        return new_incident

    def get_last_measure(self, plant_id: int) -> Optional[DailyMeasure]:
        """
        Récupère la mesure journalière la plus récente pour une centrale.

        Args:
            plant_id (int): Identifiant interne de la centrale.

        Returns:
            Optional[DailyMeasure]: La dernière mesure trouvée ou None.
        """
        return (
            self.session.query(DailyMeasure)
            .filter_by(plant_id=plant_id)
            .order_by(DailyMeasure.date.desc())
            .first()
        )

    def get_active_incidents(self) -> List[Incident]:
        """
        Récupère la liste de tous les incidents dont le statut n'est pas résolu.

        Returns:
            List[Incident]: Liste des incidents actifs.
        """
        return (
            self.session.query(Incident)
            .filter(Incident.status != "Resolved")
            .all()
        )
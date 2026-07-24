"""
Module des modèles métier pour la centrale.
Définit la structure de données orientée objet pour représenter
une centrale photovoltaïque et ses onduleurs associés.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Inverter:
    """Modèle métier représentant un onduleur."""
    energysoft_id: str
    name: str
    status: Optional[str] = None
    communication: Optional[str] = None
    last_update: Optional[datetime] = None


@dataclass
class Plant:
    """Modèle métier représentant une centrale photovoltaïque."""
    rawametrix_id: str
    name: str
    location: Optional[str] = None
    capacity: Optional[float] = None
    commissioning_date: Optional[datetime] = None
    inverters: List[Inverter] = field(default_factory=list)
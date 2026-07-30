"""
Module des Objets Métier (Domain Dataclasses & Enums).
Définit les structures de données fortement typées pour le Moteur de Décision,
le Rules Engine, la qualification des diagnostics et le suivi des incidents.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class Priority(str, Enum):
    """Niveaux de priorité attribués à un incident."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"

class IncidentStatus(str, Enum):
    """Statuts du cycle de vie d'un incident."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


@dataclass
class RuleEvaluation:
    """Résultat de l'évaluation d'une règle d'expertise individuelle."""
    rule_code: str
    rule_name: str
    is_triggered: bool
    score: float
    weight: float
    description: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le résultat de la règle en dictionnaire (pour sérialisation JSON/XAI)."""
        return {
            "rule_code": self.rule_code,
            "rule_name": self.rule_name,
            "is_triggered": self.is_triggered,
            "score": self.score,
            "weight": self.weight,
            "description": self.description,
            "details": self.details
        }


@dataclass
class ScoreResult:
    """Résultat global de l'évaluation par le moteur de règles."""
    total_score: float
    max_score: float
    confidence_score: float  # Pourcentage (0.0 à 100.0%)
    triggered_rules: List[RuleEvaluation] = field(default_factory=list)
    evaluated_rules: List[RuleEvaluation] = field(default_factory=list)

    @property
    def has_anomalies(self) -> bool:
        """Indique si au moins une règle s'est déclenchée."""
        return len(self.triggered_rules) > 0

    def get_triggered_codes(self) -> List[str]:
        """Retourne la liste des codes de règles déclenchées."""
        return [r.rule_code for r in self.triggered_rules]


@dataclass
class Diagnosis:
    """Synthèse explicable (XAI) de l'incident élaborée par le Moteur de Décision."""
    title: str
    incident_type: str
    root_cause: str
    recommended_action: str
    affected_components: List[str] = field(default_factory=list)
    summary_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "incident_type": self.incident_type,
            "root_cause": self.root_cause,
            "recommended_action": self.recommended_action,
            "affected_components": self.affected_components,
            "summary_text": self.summary_text
        }


@dataclass
class Incident:
    """Objet Domaine représentant un incident qualifié, expliqué et prêt pour persistance."""
    plant_id: int
    created_at: datetime
    priority: Priority
    diagnosis: str
    
    # Scores
    confidence: float
    rule_score: Optional[float] = None
    ai_score: Optional[float] = None  # Prêt pour le Milestone 4
    incident_type: Optional[str] = None
    
    # Explicabilité (XAI)
    explanation: str = ""
    recommendation: List[str] = field(default_factory=list)
    triggered_rules: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    feature_snapshot: Dict[str, Any] = field(default_factory=dict)
    decision_trace: Dict[str, Any] = field(default_factory=dict)
    
    # Tracking
    status: IncidentStatus = IncidentStatus.OPEN
    id: Optional[int] = None
    notification_sent: bool = False
    ticket_id: Optional[str] = None
    resolved_at: Optional[datetime] = None

    def to_repository_dict(self) -> Dict[str, Any]:
        """Convertit l'objet domaine vers la structure attendue par DatabaseRepository.save_incident."""
        return {
            "plant_id": self.plant_id,
            "created_at": self.created_at,
            "incident_type": self.incident_type or "Anomaly",
            "rule_score": self.rule_score,
            "ai_score": self.ai_score,
            "confidence": self.confidence,
            "priority": self.priority.value if isinstance(self.priority, Priority) else self.priority,
            
            # Données XAI transformées en JSON/Textes
            "diagnosis": self.diagnosis,
            "explanation": self.explanation,
            "recommendation": self.recommendation,  # Automatiquement géré par SQLAlchemy JSON
            "triggered_rules": self.triggered_rules, # Automatiquement géré par SQLAlchemy JSON
            "evidence": self.evidence,               # Automatiquement géré par SQLAlchemy JSON
            "feature_snapshot": self.feature_snapshot,
            "decision_trace": self.decision_trace,
            
            # Suivi
            "status": self.status.value if isinstance(self.status, IncidentStatus) else self.status,
            "notification_sent": self.notification_sent,
            "ticket_id": self.ticket_id,
            "resolved_at": self.resolved_at
        }
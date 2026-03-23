"""
Core data models for MetricFlow.

Defines the main entities: Metric, Alert, Pipeline, and supporting types.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Literal
from enum import Enum
import uuid


class MetricType(str, Enum):
    """Types of metrics supported."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status values."""
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Metric:
    """
    Represents a single metric data point.
    
    Attributes:
        name: Metric name (e.g., "requests.count", "response_time.p95")
        value: Metric value
        type: Type of metric (counter, gauge, histogram, summary)
        timestamp: Time when metric was recorded
        tags: Optional tags/labels for filtering
        source: Source of the metric (e.g., "api", "worker", "database")
        unit: Optional unit of measurement
    """
    name: str
    value: float
    type: MetricType = MetricType.GAUGE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    source: str = "unknown"
    unit: Optional[str] = None
    
    def __post_init__(self):
        """Validate metric after initialization."""
        if not self.name:
            raise ValueError("Metric name cannot be empty")
        if self.value is None:
            raise ValueError("Metric value cannot be None")
    
    @property
    def id(self) -> str:
        """Generate unique metric ID."""
        return f"{self.name}:{self.timestamp.isoformat()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "source": self.source,
            "unit": self.unit,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Metric":
        """Create metric from dictionary."""
        return cls(
            name=data["name"],
            value=float(data["value"]),
            type=MetricType(data.get("type", "gauge")),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
            tags=data.get("tags", {}),
            source=data.get("source", "unknown"),
            unit=data.get("unit"),
        )


@dataclass
class AggregatedMetric:
    """
    Represents an aggregated metric over a time window.
    
    Contains statistical summaries (min, max, avg, percentiles).
    """
    name: str
    count: int
    sum: float
    min: float
    max: float
    avg: float
    p50: float
    p90: float
    p95: float
    p99: float
    window_start: datetime
    window_end: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    source: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "count": self.count,
            "sum": self.sum,
            "min": self.min,
            "max": self.max,
            "avg": self.avg,
            "p50": self.p50,
            "p90": self.p90,
            "p95": self.p95,
            "p99": self.p99,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "tags": self.tags,
            "source": self.source,
        }


@dataclass
class AlertRule:
    """
    Defines an alert rule configuration.
    
    Conditions are checked against metrics to determine if an alert should fire.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    metric_name: str = ""
    condition: str = ">"
    threshold: float = 0.0
    severity: AlertSeverity = AlertSeverity.WARNING
    enabled: bool = True
    cooldown_minutes: int = 5
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def evaluate(self, value: float) -> bool:
        """
        Evaluate if the rule should trigger.
        
        Args:
            value: Current metric value
            
        Returns:
            True if alert should trigger
        """
        if not self.enabled:
            return False
        
        if self.condition == ">":
            return value > self.threshold
        elif self.condition == ">=":
            return value >= self.threshold
        elif self.condition == "<":
            return value < self.threshold
        elif self.condition == "<=":
            return value <= self.threshold
        elif self.condition == "==":
            return value == self.threshold
        elif self.condition == "!=":
            return value != self.threshold
        
        return False


@dataclass
class Alert:
    """
    Represents an active alert.
    
    Generated when an AlertRule condition is met.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = ""
    rule_name: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    severity: AlertSeverity = AlertSeverity.WARNING
    status: AlertStatus = AlertStatus.PENDING
    message: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    fired_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "status": self.status.value,
            "message": self.message,
            "tags": self.tags,
            "fired_at": self.fired_at.isoformat() if self.fired_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class Pipeline:
    """
    Represents an ETL pipeline for processing metrics.
    
    Defines a sequence of transformations and destinations.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    enabled: bool = True
    source_type: str = ""
    source_config: Dict[str, Any] = field(default_factory=dict)
    transforms: List[Dict[str, Any]] = field(default_factory=list)
    destinations: List[Dict[str, Any]] = field(default_factory=list)
    schedule: Optional[str] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: PipelineStatus = PipelineStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "source_type": self.source_type,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Dashboard:
    """
    Represents a dashboard configuration.
    
    Contains widget layouts and visualization settings.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    widgets: List[Dict[str, Any]] = field(default_factory=list)
    refresh_interval: int = 30
    time_range: str = "1h"
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "widgets": self.widgets,
            "refresh_interval": self.refresh_interval,
            "time_range": self.time_range,
            "created_at": self.created_at.isoformat(),
        }
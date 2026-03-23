"""
Services module for MetricFlow.

Contains business logic for metrics collection, aggregation, and alerting.
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
import asyncio
import time

from src.models import (
    Metric, MetricType, Alert, AlertRule, AlertSeverity, 
    AlertStatus, AggregatedMetric, Pipeline, PipelineStatus
)
from src.core.logging import get_logger
from src.core.config import get_settings


logger = get_logger(__name__)


@dataclass
class MetricBuffer:
    """In-memory buffer for storing metrics before flushing."""
    metrics: List[Metric] = field(default_factory=list)
    max_size: int = 10000
    
    def add(self, metric: Metric) -> None:
        """Add metric to buffer."""
        self.metrics.append(metric)
        if len(self.metrics) > self.max_size:
            self.metrics.pop(0)
    
    def flush(self) -> List[Metric]:
        """Flush and return all metrics."""
        metrics = self.metrics.copy()
        self.metrics.clear()
        return metrics
    
    def size(self) -> int:
        """Get current buffer size."""
        return len(self.metrics)


class MetricsCollector:
    """
    Collects and buffers metrics from various sources.
    
    Thread-safe implementation with support for multiple metric types.
    """
    
    def __init__(self, buffer_size: int = 10000):
        """
        Initialize metrics collector.
        
        Args:
            buffer_size: Maximum number of metrics to buffer
        """
        self._buffer = MetricBuffer(max_size=buffer_size)
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._subscribers: List[Callable[[List[Metric]], None]] = []
    
    async def record(self, metric: Metric) -> None:
        """
        Record a single metric.
        
        Args:
            metric: Metric to record
        """
        async with self._lock:
            if metric.type == MetricType.COUNTER:
                self._counters[metric.name] += metric.value
            elif metric.type == MetricType.GAUGE:
                self._gauges[metric.name] = metric.value
            elif metric.type == MetricType.HISTOGRAM:
                self._histograms[metric.name].append(metric.value)
            
            self._buffer.add(metric)
    
    async def increment(self, name: str, value: float = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        await self.record(Metric(
            name=name,
            value=value,
            type=MetricType.COUNTER,
            tags=tags or {},
            source="collector"
        ))
    
    async def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        await self.record(Metric(
            name=name,
            value=value,
            type=MetricType.GAUGE,
            tags=tags or {},
            source="collector"
        ))
    
    async def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram metric."""
        await self.record(Metric(
            name=name,
            value=value,
            type=MetricType.HISTOGRAM,
            tags=tags or {},
            source="collector"
        ))
    
    async def flush(self) -> List[Metric]:
        """
        Flush buffered metrics.
        
        Returns:
            List of buffered metrics
        """
        async with self._lock:
            return self._buffer.flush()
    
    def get_current_values(self) -> Dict[str, Any]:
        """Get current values for all metrics."""
        values = {}
        
        for name, value in self._counters.items():
            values[name] = {"type": "counter", "value": value}
        
        for name, value in self._gauges.items():
            values[name] = {"type": "gauge", "value": value}
        
        for name, values_list in self._histograms.items():
            if values_list:
                values[name] = {
                    "type": "histogram",
                    "count": len(values_list),
                    "sum": sum(values_list),
                    "avg": sum(values_list) / len(values_list)
                }
        
        return values
    
    def subscribe(self, callback: Callable[[List[Metric]], None]) -> None:
        """Subscribe to metric events."""
        self._subscribers.append(callback)
    
    async def notify_subscribers(self, metrics: List[Metric]) -> None:
        """Notify subscribers of new metrics."""
        for callback in self._subscribers:
            try:
                callback(metrics)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")


class MetricsAggregator:
    """
    Aggregates metrics over time windows.
    
    Computes statistical summaries including min, max, avg, and percentiles.
    """
    
    def __init__(self, window_seconds: int = 60):
        """
        Initialize metrics aggregator.
        
        Args:
            window_seconds: Aggregation window size in seconds
        """
        self.window_seconds = window_seconds
        self._windows: Dict[str, List[Metric]] = defaultdict(list)
    
    def add(self, metric: Metric) -> None:
        """Add metric to appropriate window."""
        window_key = self._get_window_key(metric.timestamp)
        self._windows[metric.name].append(metric)
    
    def aggregate(self, name: str) -> Optional[AggregatedMetric]:
        """
        Aggregate metrics for a given name.
        
        Args:
            name: Metric name to aggregate
            
        Returns:
            Aggregated metric or None if no data
        """
        metrics = self._windows.get(name, [])
        if not metrics:
            return None
        
        values = [m.value for m in metrics]
        sorted_values = sorted(values)
        
        window_start = metrics[0].timestamp
        window_end = metrics[-1].timestamp
        
        return AggregatedMetric(
            name=name,
            count=len(values),
            sum=sum(values),
            min=min(values),
            max=max(values),
            avg=sum(values) / len(values),
            p50=self._percentile(sorted_values, 50),
            p90=self._percentile(sorted_values, 90),
            p95=self._percentile(sorted_values, 95),
            p99=self._percentile(sorted_values, 99),
            window_start=window_start,
            window_end=window_end,
            tags=metrics[0].tags,
            source=metrics[0].source
        )
    
    def aggregate_all(self) -> List[AggregatedMetric]:
        """Aggregate all metrics."""
        results = []
        for name in self._windows.keys():
            agg = self.aggregate(name)
            if agg:
                results.append(agg)
        return results
    
    def clear(self, name: Optional[str] = None) -> None:
        """Clear aggregated data."""
        if name:
            self._windows.pop(name, None)
        else:
            self._windows.clear()
    
    @staticmethod
    def _get_window_key(timestamp: datetime) -> str:
        """Get window key for timestamp."""
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def _percentile(sorted_values: List[float], p: float) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = f + 1 if f < len(sorted_values) - 1 else f
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])


class AlertManager:
    """
    Manages alert rules and handles alert lifecycle.
    
    Evaluates rules against metrics and generates alerts.
    """
    
    def __init__(self):
        """Initialize alert manager."""
        self._rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._cooldowns: Dict[str, datetime] = {}
    
    def add_rule(self, rule: AlertRule) -> None:
        """Add or update an alert rule."""
        self._rules[rule.id] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False
    
    def get_rules(self) -> List[AlertRule]:
        """Get all alert rules."""
        return list(self._rules.values())
    
    def evaluate(self, metric: Metric) -> List[Alert]:
        """
        Evaluate all rules against a metric.
        
        Args:
            metric: Metric to evaluate
            
        Returns:
            List of triggered alerts
        """
        triggered = []
        
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            if rule.metric_name != metric.name:
                continue
            
            if not rule.evaluate(metric.value):
                continue
            
            # Check cooldown
            if rule.id in self._cooldowns:
                cooldown_end = self._cooldowns[rule.id] + timedelta(minutes=rule.cooldown_minutes)
                if datetime.utcnow() < cooldown_end:
                    continue
            
            # Create alert
            alert = Alert(
                rule_id=rule.id,
                rule_name=rule.name,
                metric_name=metric.name,
                metric_value=metric.value,
                threshold=rule.threshold,
                severity=rule.severity,
                status=AlertStatus.FIRING,
                message=f"{rule.name}: {metric.name} = {metric.value} ({rule.condition} {rule.threshold})",
                tags=metric.tags,
                fired_at=datetime.utcnow()
            )
            
            triggered.append(alert)
            self._active_alerts[alert.id] = alert
            self._cooldowns[rule.id] = datetime.utcnow()
            
            logger.warning(f"Alert triggered: {alert.message}")
        
        return triggered
    
    def acknowledge(self, alert_id: str, user: str) -> bool:
        """Acknowledge an alert."""
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = user
            return True
        return False
    
    def resolve(self, alert_id: str) -> bool:
        """Resolve an alert."""
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            return True
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return [a for a in self._active_alerts.values() if a.status == AlertStatus.FIRING]


class PipelineExecutor:
    """
    Executes pipelines for processing metrics.
    
    Handles source fetching, transformations, and destination output.
    """
    
    def __init__(self):
        """Initialize pipeline executor."""
        self._pipelines: Dict[str, Pipeline] = {}
        self._running: Dict[str, bool] = {}
    
    def register(self, pipeline: Pipeline) -> None:
        """Register a pipeline."""
        self._pipelines[pipeline.id] = pipeline
        logger.info(f"Registered pipeline: {pipeline.name}")
    
    async def execute(self, pipeline_id: str) -> bool:
        """
        Execute a pipeline.
        
        Args:
            pipeline_id: ID of pipeline to execute
            
        Returns:
            True if execution succeeded
        """
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            return False
        
        try:
            pipeline.status = PipelineStatus.RUNNING
            pipeline.last_run = datetime.utcnow()
            
            logger.info(f"Executing pipeline: {pipeline.name}")
            
            # Execute pipeline steps
            for step in pipeline.transforms:
                await self._execute_transform(step)
            
            pipeline.status = PipelineStatus.COMPLETED
            logger.info(f"Pipeline completed: {pipeline.name}")
            return True
            
        except Exception as e:
            pipeline.status = PipelineStatus.FAILED
            logger.error(f"Pipeline failed: {pipeline.name} - {e}")
            return False
    
    async def _execute_transform(self, transform: Dict[str, Any]) -> None:
        """Execute a single transform step."""
        transform_type = transform.get("type", "")
        
        if transform_type == "filter":
            # Filter metrics based on conditions
            pass
        elif transform_type == "map":
            # Map/transform metric values
            pass
        elif transform_type == "aggregate":
            # Aggregate metrics
            pass
        
        await asyncio.sleep(0.1)  # Simulate processing
    
    def cancel(self, pipeline_id: str) -> bool:
        """Cancel a running pipeline."""
        if pipeline_id in self._running:
            self._running[pipeline_id] = False
            return True
        return False
"""
Unit tests for MetricFlow core components.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from src.models import Metric, MetricType, AlertRule, AlertSeverity, AlertStatus
from src.services.metrics import MetricsCollector, MetricsAggregator, AlertManager
from src.core.config import Settings, DatabaseConfig, AlertConfig


class TestMetric:
    """Tests for Metric model."""
    
    def test_create_metric(self):
        """Test creating a basic metric."""
        metric = Metric(name="test.metric", value=100.0)
        assert metric.name == "test.metric"
        assert metric.value == 100.0
        assert metric.type == MetricType.GAUGE
    
    def test_metric_to_dict(self):
        """Test metric serialization."""
        metric = Metric(
            name="test.metric",
            value=100.0,
            type=MetricType.COUNTER,
            tags={"env": "prod"}
        )
        data = metric.to_dict()
        
        assert data["name"] == "test.metric"
        assert data["value"] == 100.0
        assert data["type"] == "counter"
        assert data["tags"]["env"] == "prod"
    
    def test_metric_validation(self):
        """Test metric validation."""
        with pytest.raises(ValueError):
            Metric(name="", value=100.0)


class TestAlertRule:
    """Tests for AlertRule model."""
    
    def test_create_rule(self):
        """Test creating an alert rule."""
        rule = AlertRule(
            name="High Error Rate",
            metric_name="errors.count",
            condition=">",
            threshold=10.0,
            severity=AlertSeverity.ERROR
        )
        
        assert rule.name == "High Error Rate"
        assert rule.metric_name == "errors.count"
        assert rule.threshold == 10.0
    
    def test_rule_evaluation(self):
        """Test rule condition evaluation."""
        rule = AlertRule(
            metric_name="response_time",
            condition=">",
            threshold=500.0,
            enabled=True
        )
        
        assert rule.evaluate(600.0) is True
        assert rule.evaluate(400.0) is False
    
    def test_rule_disabled(self):
        """Test disabled rule evaluation."""
        rule = AlertRule(
            metric_name="response_time",
            condition=">",
            threshold=500.0,
            enabled=False
        )
        
        assert rule.evaluate(600.0) is False


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    @pytest.mark.asyncio
    async def test_record_metric(self):
        """Test recording a metric."""
        collector = MetricsCollector()
        
        metric = Metric(name="test.counter", value=1.0, type=MetricType.COUNTER)
        await collector.record(metric)
        
        values = collector.get_current_values()
        assert "test.counter" in values
    
    @pytest.mark.asyncio
    async def test_counter_increment(self):
        """Test counter increment."""
        collector = MetricsCollector()
        
        await collector.increment("requests.count", 5)
        await collector.increment("requests.count", 3)
        
        values = collector.get_current_values()
        assert values["requests.count"]["value"] == 8.0
    
    @pytest.mark.asyncio
    async def test_flush(self):
        """Test buffer flush."""
        collector = MetricsCollector()
        
        await collector.gauge("temp", 25.0)
        await collector.gauge("temp", 26.0)
        
        flushed = await collector.flush()
        assert len(flushed) == 2


class TestMetricsAggregator:
    """Tests for MetricsAggregator."""
    
    def test_aggregate_counter(self):
        """Test aggregating counter metrics."""
        aggregator = MetricsAggregator()
        
        # Add multiple metrics
        for i in range(10):
            aggregator.add(Metric(
                name="response.time",
                value=float(100 + i * 10),
                tags={"endpoint": "/api"}
            ))
        
        result = aggregator.aggregate("response.time")
        
        assert result is not None
        assert result.count == 10
        assert result.min == 100.0
        assert result.max == 190.0
        assert result.avg > 100
    
    def test_percentile_calculation(self):
        """Test percentile calculations."""
        aggregator = MetricsAggregator()
        
        # Add metrics with known values
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        for v in values:
            aggregator.add(Metric(name="test", value=float(v)))
        
        result = aggregator.aggregate("test")
        
        assert result is not None
        assert result.p50 == 50.0
        assert result.p90 == 90.0
        assert result.p95 == 95.0


class TestAlertManager:
    """Tests for AlertManager."""
    
    def test_add_rule(self):
        """Test adding alert rule."""
        manager = AlertManager()
        
        rule = AlertRule(
            name="High Latency",
            metric_name="latency",
            condition=">",
            threshold=1000.0
        )
        
        manager.add_rule(rule)
        
        rules = manager.get_rules()
        assert len(rules) == 1
        assert rules[0].name == "High Latency"
    
    def test_evaluate_triggers_alert(self):
        """Test alert evaluation."""
        manager = AlertManager()
        
        rule = AlertRule(
            name="High Error Rate",
            metric_name="errors",
            condition=">",
            threshold=5.0,
            severity=AlertSeverity.ERROR
        )
        manager.add_rule(rule)
        
        # Create metric that triggers alert
        metric = Metric(name="errors", value=10.0)
        alerts = manager.evaluate(metric)
        
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.ERROR
    
    def test_evaluate_no_trigger(self):
        """Test alert that doesn't trigger."""
        manager = AlertManager()
        
        rule = AlertRule(
            name="Low Error Rate",
            metric_name="errors",
            condition=">",
            threshold=5.0
        )
        manager.add_rule(rule)
        
        # Create metric below threshold
        metric = Metric(name="errors", value=2.0)
        alerts = manager.evaluate(metric)
        
        assert len(alerts) == 0
    
    def test_cooldown(self):
        """Test alert cooldown period."""
        manager = AlertManager()
        
        rule = AlertRule(
            name="Test Alert",
            metric_name="test",
            condition=">",
            threshold=1.0,
            cooldown_minutes=10
        )
        manager.add_rule(rule)
        
        # First alert should fire
        metric = Metric(name="test", value=10.0)
        alerts = manager.evaluate(metric)
        assert len(alerts) == 1
        
        # Second alert in cooldown should not fire
        alerts = manager.evaluate(metric)
        assert len(alerts) == 0


class TestSettings:
    """Tests for Settings configuration."""
    
    def test_default_values(self):
        """Test default settings values."""
        settings = Settings()
        
        assert settings.app_name == "MetricFlow"
        assert settings.port == 8000
        assert settings.debug is False
    
    def test_database_url(self):
        """Test database URL generation."""
        db = DatabaseConfig(
            host="localhost",
            port=5432,
            user="admin",
            password="secret",
            name="metrics"
        )
        
        assert db.url == "postgresql://admin:secret@localhost:5432/metrics"
    
    def test_validation_errors(self):
        """Test settings validation."""
        settings = Settings(
            secret_key="change-me-in-production",
            debug=True,
            environment="production",
            port=0
        )
        
        errors = settings.validate()
        
        assert "DEBUG cannot be enabled in production" in errors
        assert "PORT must be between 1 and 65535" in errors
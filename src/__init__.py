"""
MetricFlow - Real-time Metrics Aggregation and Alerting System

A production-ready Python system for collecting, aggregating, and alerting
on real-time metrics with support for multiple data sources and alerting channels.
"""

__version__ = "1.0.0"
__author__ = "Logesh Kannan"
__license__ = "MIT"

from src.core.config import Settings
from src.core.logging import get_logger
from src.models import Metric, Alert, Pipeline

__all__ = [
    "Settings",
    "get_logger",
    "Metric",
    "Alert",
    "Pipeline",
]
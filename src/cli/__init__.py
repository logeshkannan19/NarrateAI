"""
Command-line interface for MetricFlow.

Provides CLI commands for managing metrics, alerts, and pipelines.
"""

import sys
import asyncio
import argparse
from typing import Optional, List
from datetime import datetime, timedelta

from src.core.config import get_settings, load_env_file
from src.core.logging import setup_logging, get_logger, LogContext
from src.models import Metric, MetricType, AlertRule, AlertSeverity, Pipeline
from src.services.metrics import MetricsCollector, MetricsAggregator, AlertManager


logger = get_logger(__name__)


class CLI:
    """Main CLI application."""
    
    def __init__(self):
        self.settings = get_settings()
        self.collector = MetricsCollector()
        self.aggregator = MetricsAggregator()
        self.alert_manager = AlertManager()
    
    async def run(self, args: argparse.Namespace) -> int:
        """Run CLI command."""
        if hasattr(args, 'func'):
            return await args.func(self, args)
        return 0


async def cmd_metrics_record(cli: CLI, args: argparse.Namespace) -> int:
    """Record a metric."""
    metric = Metric(
        name=args.name,
        value=float(args.value),
        type=MetricType(args.type),
        tags=parse_tags(args.tags),
        source="cli"
    )
    await cli.collector.record(metric)
    print(f"✓ Recorded: {metric.name} = {metric.value} ({metric.type.value})")
    return 0


async def cmd_metrics_list(cli: CLI, args: argparse.Namespace) -> int:
    """List current metrics."""
    values = cli.collector.get_current_values()
    if not values:
        print("No metrics recorded yet.")
        return 0
    
    print(f"{'Name':<40} {'Type':<12} {'Value':<15}")
    print("-" * 67)
    for name, data in values.items():
        print(f"{name:<40} {data['type']:<12} {data['value']}")
    return 0


async def cmd_metrics_flush(cli: CLI, args: argparse.Namespace) -> int:
    """Flush and aggregate metrics."""
    metrics = await cli.collector.flush()
    print(f"Flushed {len(metrics)} metrics")
    
    for m in metrics:
        cli.aggregator.add(m)
    
    aggregated = cli.aggregator.aggregate_all()
    print(f"\nAggregated {len(aggregated)} metrics:")
    for agg in aggregated:
        print(f"  {agg.name}: count={agg.count}, avg={agg.avg:.2f}, p95={agg.p95:.2f}")
    return 0


async def cmd_alerts_list(cli: CLI, args: argparse.Namespace) -> int:
    """List alert rules."""
    rules = cli.alert_manager.get_rules()
    if not rules:
        print("No alert rules configured.")
        return 0
    
    print(f"{'Name':<30} {'Metric':<20} {'Condition':<10} {'Severity':<10}")
    print("-" * 70)
    for rule in rules:
        status = "✓" if rule.enabled else "✗"
        print(f"{status} {rule.name:<28} {rule.metric_name:<20} {rule.condition}{rule.threshold:<8} {rule.severity.value}")
    return 0


async def cmd_alerts_add(cli: CLI, args: argparse.Namespace) -> int:
    """Add an alert rule."""
    rule = AlertRule(
        name=args.name,
        description=args.description or "",
        metric_name=args.metric,
        condition=args.condition,
        threshold=float(args.threshold),
        severity=AlertSeverity(args.severity),
        enabled=True
    )
    cli.alert_manager.add_rule(rule)
    print(f"✓ Added alert rule: {rule.name}")
    return 0


async def cmd_alerts_active(cli: CLI, args: argparse.Namespace) -> int:
    """List active alerts."""
    alerts = cli.alert_manager.get_active_alerts()
    if not alerts:
        print("No active alerts.")
        return 0
    
    print(f"{'ID':<38} {'Severity':<10} {'Message':<40}")
    print("-" * 88)
    for alert in alerts:
        msg = alert.message[:37] + "..." if len(alert.message) > 40 else alert.message
        print(f"{alert.id:<38} {alert.severity.value:<10} {msg}")
    return 0


async def cmd_status(cli: CLI, args: argparse.Namespace) -> int:
    """Show system status."""
    settings = cli.settings
    print(f"MetricFlow Status")
    print(f"{'='*50}")
    print(f"Environment:   {settings.environment}")
    print(f"Debug Mode:    {settings.debug}")
    print(f"Log Level:    {settings.log_level}")
    print(f"Port:          {settings.host}:{settings.port}")
    print(f"Database:      {settings.database.host}:{settings.database.port}")
    print(f"Redis:         {settings.redis.host}:{settings.redis.port}")
    print()
    print(f"Metrics:")
    values = cli.collector.get_current_values()
    print(f"  - Recorded:   {len(values)} unique metrics")
    print(f"  - Buffered:   {cli.collector._buffer.size()}")
    print()
    print(f"Alerts:")
    print(f"  - Rules:      {len(cli.alert_manager.get_rules())}")
    print(f"  - Active:     {len(cli.alert_manager.get_active_alerts())}")
    return 0


def parse_tags(tag_string: Optional[str]) -> dict:
    """Parse tag string into dictionary."""
    if not tag_string:
        return {}
    tags = {}
    for pair in tag_string.split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            tags[key.strip()] = value.strip()
    return tags


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="metricflow",
        description="MetricFlow - Real-time Metrics Aggregation and Alerting"
    )
    
    # Global options
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Metrics commands
    metrics_parser = subparsers.add_parser("metrics", help="Metrics commands")
    metrics_sub = metrics_parser.add_subparsers(dest="subcommand")
    
    record_parser = metrics_sub.add_parser("record", help="Record a metric")
    record_parser.add_argument("name", help="Metric name")
    record_parser.add_argument("value", help="Metric value")
    record_parser.add_argument("--type", choices=["counter", "gauge", "histogram"], default="gauge")
    record_parser.add_argument("--tags", help="Tags (key=value,key=value)")
    record_parser.set_defaults(func=cmd_metrics_record)
    
    list_parser = metrics_sub.add_parser("list", help="List current metrics")
    list_parser.set_defaults(func=cmd_metrics_list)
    
    flush_parser = metrics_sub.add_parser("flush", help="Flush and aggregate metrics")
    flush_parser.set_defaults(func=cmd_metrics_flush)
    
    # Alert commands
    alerts_parser = subparsers.add_parser("alerts", help="Alert commands")
    alerts_sub = alerts_parser.add_subparsers(dest="subcommand")
    
    rules_parser = alerts_sub.add_parser("list", help="List alert rules")
    rules_parser.set_defaults(func=cmd_alerts_list)
    
    add_parser = alerts_sub.add_parser("add", help="Add alert rule")
    add_parser.add_argument("name", help="Rule name")
    add_parser.add_argument("metric", help="Metric name to monitor")
    add_parser.add_argument("condition", choices=[">", ">=", "<", "<=", "==", "!="])
    add_parser.add_argument("threshold", help="Threshold value")
    add_parser.add_argument("--severity", choices=["info", "warning", "error", "critical"], default="warning")
    add_parser.add_argument("--description", help="Rule description")
    add_parser.set_defaults(func=cmd_alerts_add)
    
    active_parser = alerts_sub.add_parser("active", help="List active alerts")
    active_parser.set_defaults(func=cmd_alerts_active)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.set_defaults(func=cmd_status)
    
    return parser


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level, debug=args.debug)
    
    # Load environment
    load_env_file()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Create CLI and run
    cli = CLI()
    return asyncio.run(cli.run(args))


if __name__ == "__main__":
    sys.exit(main())
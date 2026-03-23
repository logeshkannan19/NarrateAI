# NarrateAI

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/status-stable-green" alt="Status">
</p>

**Real-time Metrics Aggregation and Alerting System**

A production-ready Python system for collecting, aggregating, and alerting on real-time metrics. Built for scale with support for multiple data sources, intelligent aggregation, and flexible alerting.

---

## ✨ Features

### Core Capabilities
- **Multi-type Metrics** — Support for counters, gauges, histograms, and summaries
- **Real-time Collection** — Async-first architecture with sub-second latency
- **Smart Aggregation** — Automatic computation of min, max, avg, and percentiles (p50, p90, p95, p99)
- **Flexible Alerting** — Rule-based alerts with severity levels, cooldowns, and multi-channel delivery

### Alert Channels
- Email notifications via SMTP
- Slack webhook integration
- Custom webhook endpoints
- Rate limiting to prevent alert storms

### Developer Experience
- **CLI First** — Intuitive command-line interface for all operations
- **Type Hints** — Full type annotations for better IDE support
- **Well Documented** — Comprehensive docstrings and examples
- **Tested** — Unit and integration test suite

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MetricFlow                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│  │   CLI       │   │   API       │   │  Library    │       │
│  │   Client    │   │   Server    │   │   Import    │       │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘       │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            ▼                                  │
│  ┌───────────────────────────────────────────────────────┐   │
│  │              MetricsCollector (In-Memory)             │   │
│  │  • Buffer management    • Type handling               │   │
│  └─────────────────────────┬───────────────────────────┘   │
│                            │                                 │
│         ┌──────────────────┼──────────────────┐             │
│         ▼                  ▼                  ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Aggregator   │  │Alert Manager │  │  Pipeline    │       │
│  │              │  │              │  │  Executor    │       │
│  │ • Windowing  │  │ • Rules      │  │              │       │
│  │ • Stats     │  │ • Cooldowns  │  │ • ETL        │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
MetricFlow/
├── src/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # Application entry point
│   ├── cli/
│   │   └── __init__.py      # CLI interface
│   ├── core/
│   │   ├── config.py        # Configuration management
│   │   └── logging.py       # Logging setup
│   ├── models/
│   │   └── __init__.py      # Data models (Metric, Alert, Pipeline)
│   ├── services/
│   │   └── metrics.py       # Business logic
│   └── utils/
│       ├── __init__.py
│       └── helpers.py       # Utility functions
├── tests/
│   └── unit/
│       └── test_core.py     # Unit tests
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
└── README.md               # This file
```

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/logeshkannan19/MetricFlow.git
cd MetricFlow

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
# (Optional) Adjust settings in .env
```

### CLI Usage

```bash
# Record a simple metric
metricflow metrics record requests.count 100 --type counter

# List current metrics
metricflow metrics list

# Add an alert rule
metricflow alerts add "High Response Time" response_time.p95 > 1000 --severity warning

# List alert rules
metricflow alerts list

# Check system status
metricflow status
```

### Programmatic Usage

```python
from src.services.metrics import MetricsCollector, AlertManager
from src.models import Metric, MetricType

async def main():
    collector = MetricsCollector()
    
    # Record metrics
    await collector.gauge("temperature", 23.5)
    await collector.increment("requests.count", 1)
    await collector.histogram("response_time", 145.2)
    
    # Get current values
    values = collector.get_current_values()
    print(values)

asyncio.run(main())
```

---

## 📊 Example: Alert Rule

```python
from src.models import AlertRule, AlertSeverity

# Create an alert rule
rule = AlertRule(
    name="High Error Rate",
    description="Alert when error rate exceeds 5%",
    metric_name="errors.rate",
    condition=">",
    threshold=5.0,
    severity=AlertSeverity.ERROR,
    cooldown_minutes=15
)

# Add to manager
alert_manager = AlertManager()
alert_manager.add_rule(rule)

# Evaluate against metric
from src.models import Metric
metric = Metric(name="errors.rate", value=7.5)
alerts = alert_manager.evaluate(metric)

# Alerts now triggered!
print(f"Triggered {len(alerts)} alerts")
```

---

## 🔧 Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | MetricFlow | Application name |
| `PORT` | 8000 | Server port |
| `LOG_LEVEL` | INFO | Logging level |
| `FLUSH_INTERVAL` | 10 | Metrics flush interval (seconds) |
| `BUFFER_SIZE` | 10000 | Max buffered metrics |
| `RETENTION_DAYS` | 30 | Data retention period |

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit/ -v

# Run with coverage
pytest --cov=src tests/
```

---

## 📈 Roadmap

- [ ] PostgreSQL persistence layer
- [ ] Redis caching
- [ ] REST API server
- [ ] WebSocket real-time updates
- [ ] Dashboard UI
- [ ] Prometheus export
- [ ] Grafana integration

---

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Logesh Kannan**
- GitHub: [@logeshkannan19](https://github.com/logeshkannan19)

---

<p align="center">Built with ❤️ for developers who care about observability</p>

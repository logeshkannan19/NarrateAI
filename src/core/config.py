"""
Configuration management for MetricFlow.

Handles environment variables, settings validation, and configuration loading.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from functools import lru_cache
import logging


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    host: str = "localhost"
    port: int = 5432
    name: str = "metricflow"
    user: str = "postgres"
    password: str = ""
    pool_size: int = 10
    timeout: int = 30

    @property
    def url(self) -> str:
        """Generate database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """Generate async database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class RedisConfig:
    """Redis connection configuration."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    max_connections: int = 50

    @property
    def url(self) -> str:
        """Generate Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class AlertConfig:
    """Alert delivery configuration."""
    email_enabled: bool = True
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_from: str = ""
    email_to: List[str] = field(default_factory=list)
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    slack_channel: str = "#alerts"
    webhook_enabled: bool = False
    webhook_urls: List[str] = field(default_factory=list)
    rate_limit: int = 100
    rate_window: int = 3600


@dataclass
class MetricsConfig:
    """Metrics collection configuration."""
    flush_interval: int = 10
    buffer_size: int = 10000
    retention_days: int = 30
    aggregation_interval: int = 60
    percentiles: List[int] = field(default_factory=lambda: [50, 90, 95, 99])


@dataclass
class Settings:
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden via environment variables or .env file.
    """
    # Application
    app_name: str = "MetricFlow"
    debug: bool = False
    environment: str = "development"
    log_level: str = "INFO"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Database
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    # Redis
    redis: RedisConfig = field(default_factory=RedisConfig)
    
    # Alerts
    alerts: AlertConfig = field(default_factory=AlertConfig)
    
    # Metrics
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    
    # Security
    secret_key: str = "change-me-in-production"
    api_token: str = ""
    allowed_hosts: List[str] = field(default_factory=lambda: ["*"])
    
    # Feature flags
    enable_aggregation: bool = True
    enable_persistence: bool = True
    enable_alerts: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from environment variables."""
        return cls(
            app_name=os.getenv("APP_NAME", "MetricFlow"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            environment=os.getenv("ENVIRONMENT", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            workers=int(os.getenv("WORKERS", "4")),
            secret_key=os.getenv("SECRET_KEY", "change-me-in-production"),
            api_token=os.getenv("API_TOKEN", ""),
            allowed_hosts=os.getenv("ALLOWED_HOSTS", "*").split(","),
            database=DatabaseConfig(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                name=os.getenv("DB_NAME", "metricflow"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", ""),
            ),
            redis=RedisConfig(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                db=int(os.getenv("REDIS_DB", "0")),
                password=os.getenv("REDIS_PASSWORD"),
            ),
            alerts=AlertConfig(
                email_enabled=os.getenv("EMAIL_ENABLED", "true").lower() == "true",
                email_smtp_host=os.getenv("SMTP_HOST", ""),
                email_smtp_port=int(os.getenv("SMTP_PORT", "587")),
                email_from=os.getenv("EMAIL_FROM", ""),
                email_to=os.getenv("EMAIL_TO", "").split(","),
                slack_enabled=os.getenv("SLACK_ENABLED", "false").lower() == "true",
                slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL", ""),
                slack_channel=os.getenv("SLACK_CHANNEL", "#alerts"),
            ),
            metrics=MetricsConfig(
                flush_interval=int(os.getenv("FLUSH_INTERVAL", "10")),
                buffer_size=int(os.getenv("BUFFER_SIZE", "10000")),
                retention_days=int(os.getenv("RETENTION_DAYS", "30")),
            ),
            enable_aggregation=os.getenv("ENABLE_AGGREGATION", "true").lower() == "true",
            enable_persistence=os.getenv("ENABLE_PERSISTENCE", "true").lower() == "true",
            enable_alerts=os.getenv("ENABLE_ALERTS", "true").lower() == "true",
        )

    def validate(self) -> List[str]:
        """Validate settings and return list of validation errors."""
        errors = []
        
        if not self.secret_key or self.secret_key == "change-me-in-production":
            errors.append("SECRET_KEY must be set in production")
        
        if self.debug and self.environment == "production":
            errors.append("DEBUG cannot be enabled in production")
        
        if self.port < 1 or self.port > 65535:
            errors.append("PORT must be between 1 and 65535")
        
        if self.metrics.retention_days < 1:
            errors.append("RETENTION_DAYS must be at least 1")
        
        return errors


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Application settings singleton
    """
    return Settings.from_env()


def load_env_file(env_path: Optional[Path] = None) -> None:
    """
    Load environment variables from .env file.
    
    Args:
        env_path: Path to .env file. Defaults to project root.
    """
    if env_path is None:
        env_path = Path.cwd() / ".env"
    
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key, value)
"""
Main entry point for MetricFlow application.

Provides both CLI and API server functionality.
"""

import sys
import asyncio
import signal
from typing import Optional

from src.core.config import get_settings, load_env_file
from src.core.logging import setup_logging, get_logger
from src.services.metrics import MetricsCollector, MetricsAggregator, AlertManager
from src.cli import main as cli_main


logger = get_logger(__name__)


class MetricFlowApp:
    """
    Main application class.
    
    Manages lifecycle and coordinates all components.
    """
    
    def __init__(self):
        """Initialize application."""
        self.settings = get_settings()
        self.collector = MetricsCollector()
        self.aggregator = MetricsAggregator()
        self.alert_manager = AlertManager()
        self._running = False
    
    async def start(self) -> None:
        """Start the application."""
        logger.info(f"Starting {self.settings.app_name}")
        
        self._running = True
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._flush_loop()),
            asyncio.create_task(self._aggregate_loop()),
        ]
        
        logger.info(f"{self.settings.app_name} started on {self.settings.host}:{self.settings.port}")
        
        # Wait for interruption
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Application cancelled")
    
    async def stop(self) -> None:
        """Stop the application."""
        logger.info(f"Stopping {self.settings.app_name}")
        self._running = False
    
    async def _flush_loop(self) -> None:
        """Periodic flush of metrics buffer."""
        interval = self.settings.metrics.flush_interval
        
        while self._running:
            await asyncio.sleep(interval)
            
            metrics = await self.collector.flush()
            for metric in metrics:
                self.aggregator.add(metric)
                
                # Check alerts
                alerts = self.alert_manager.evaluate(metric)
                for alert in alerts:
                    logger.warning(f"Alert: {alert.message}")
    
    async def _aggregate_loop(self) -> None:
        """Periodic aggregation of metrics."""
        interval = self.settings.metrics.aggregation_interval
        
        while self._running:
            await asyncio.sleep(interval)
            
            aggregated = self.aggregator.aggregate_all()
            
            if aggregated:
                logger.debug(f"Aggregated {len(aggregated)} metrics")


def run_server() -> int:
    """Run the API server."""
    # Setup
    load_env_file()
    settings = get_settings()
    setup_logging(level=settings.log_level, debug=settings.debug)
    
    # Validate settings
    errors = settings.validate()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        return 1
    
    logger.info(f"Starting {settings.app_name} server...")
    
    # Create and start app
    app = MetricFlowApp()
    
    # Handle signals
    loop = asyncio.get_event_loop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(app.stop()))
    
    try:
        loop.run_until_complete(app.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(app.stop())
    
    return 0


def main() -> int:
    """Main entry point."""
    # Check if called with arguments
    if len(sys.argv) > 1:
        return cli_main()
    return run_server()


if __name__ == "__main__":
    sys.exit(main())
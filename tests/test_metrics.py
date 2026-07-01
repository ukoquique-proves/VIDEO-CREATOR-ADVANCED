"""
Tests for structured logging and performance metrics.
"""

import pytest
import json
import logging
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.metrics import (
    MetricsCollector, GenerationMetrics, StepMetrics, ProviderMetrics,
    StructuredLogger
)
from src.json_logging import JSONFormatter, setup_json_logging


class TestProviderMetrics:
    """Test provider-level metrics."""
    
    def test_provider_metrics_initialization(self):
        """Provider metrics should initialize with zeros."""
        metrics = ProviderMetrics(name="test_provider")
        
        assert metrics.name == "test_provider"
        assert metrics.attempts == 0
        assert metrics.successes == 0
        assert metrics.failures == 0
        assert metrics.total_time_ms == 0.0
        assert metrics.success_rate == 0.0
    
    def test_provider_success_rate(self):
        """Success rate should calculate correctly."""
        metrics = ProviderMetrics(name="test")
        metrics.attempts = 10
        metrics.successes = 7
        metrics.failures = 3
        
        assert metrics.success_rate == 70.0
    
    def test_provider_average_time(self):
        """Average time should be total_time / attempts."""
        metrics = ProviderMetrics(name="test")
        metrics.attempts = 5
        metrics.total_time_ms = 1000.0  # 1000ms total
        
        assert metrics.avg_time_ms == 200.0  # 200ms average


class TestStepMetrics:
    """Test pipeline step metrics."""
    
    def test_step_metrics_initialization(self):
        """Step metrics should initialize with pending status."""
        step = StepMetrics(name="image_generation")
        
        assert step.name == "image_generation"
        assert step.status == "pending"
        assert step.duration_ms == 0.0
    
    def test_step_duration_calculation(self):
        """Duration should calculate from start and end times."""
        step = StepMetrics(name="test")
        step.start_time = 100.0
        step.end_time = 100.5  # 0.5 seconds
        
        assert step.duration_ms == 500.0  # 500 milliseconds
    
    def test_step_to_dict(self):
        """Step should convert to dict with all fields."""
        step = StepMetrics(
            name="tts_audio",
            status="success",
            start_time=100.0,
            end_time=110.0,
            metadata={"language": "es"}
        )
        
        step_dict = step.to_dict()
        
        assert step_dict["name"] == "tts_audio"
        assert step_dict["status"] == "success"
        assert step_dict["duration_ms"] == pytest.approx(10000.0, rel=1.0)
        assert step_dict["metadata"]["language"] == "es"


class TestGenerationMetrics:
    """Test overall generation metrics."""
    
    def test_generation_metrics_initialization(self):
        """Generation metrics should initialize with request ID and timestamp."""
        metrics = GenerationMetrics(request_id="abc123", start_time=time.time())
        
        assert metrics.request_id == "abc123"
        assert metrics.start_time > 0
        assert metrics.success is False
        assert len(metrics.steps) == 0
    
    def test_total_failovers(self):
        """Total failovers should count multi-attempt providers."""
        metrics = GenerationMetrics(request_id="test", start_time=time.time())
        
        # Provider with 3 attempts = 2 failovers
        metrics.providers["provider1"] = ProviderMetrics(name="provider1", attempts=3)
        # Provider with 1 attempt = 0 failovers
        metrics.providers["provider2"] = ProviderMetrics(name="provider2", attempts=1)
        
        assert metrics.total_failovers == 2
    
    def test_image_provider_success_rate(self):
        """Success rate should be calculated across all providers."""
        metrics = GenerationMetrics(request_id="test", start_time=time.time())
        
        metrics.providers["p1"] = ProviderMetrics(
            name="p1", attempts=10, successes=7, failures=3
        )
        metrics.providers["p2"] = ProviderMetrics(
            name="p2", attempts=5, successes=3, failures=2
        )
        
        # (7+3) / (10+5) = 10/15 = 66.67%
        assert metrics.image_provider_success_rate == pytest.approx(66.67, rel=0.1)
    
    def test_metrics_to_dict(self):
        """Metrics should convert to dict for JSON logging."""
        metrics = GenerationMetrics(
            request_id="req123",
            start_time=time.time(),
            config_name="test_config",
            language="es",
            success=True
        )
        metrics.end_time = metrics.start_time + 10.0
        
        metrics_dict = metrics.to_dict()
        
        assert metrics_dict["request_id"] == "req123"
        assert metrics_dict["config_name"] == "test_config"
        assert metrics_dict["language"] == "es"
        assert metrics_dict["success"] is True
        assert "timestamp" in metrics_dict
        assert "total_duration_ms" in metrics_dict


class TestMetricsCollector:
    """Test metrics collection during generation."""
    
    def test_collector_initialization(self):
        """Collector should initialize with unique request ID."""
        collector = MetricsCollector(
            config_name="test",
            language="en",
            tts_backend="edge-tts"
        )
        
        assert collector.metrics.request_id is not None
        assert len(collector.metrics.request_id) > 0
        assert collector.metrics.config_name == "test"
        assert collector.metrics.language == "en"
        assert collector.metrics.tts_backend == "edge-tts"
    
    def test_start_and_end_step(self):
        """Collector should track step start and end."""
        collector = MetricsCollector()
        
        step = collector.start_step("image_generation", metadata={"prompt": "test"})
        assert step.status == "running"
        assert step.start_time is not None
        
        time.sleep(0.01)  # 10ms
        collector.end_step(step, status="success")
        
        assert step.status == "success"
        assert step.end_time is not None
        assert step.duration_ms >= 10.0
        assert step.metadata["prompt"] == "test"
    
    def test_track_provider_attempt(self):
        """Collector should track provider attempts with success/failure."""
        collector = MetricsCollector()
        
        # Track success
        collector.track_provider_attempt("provider1", success=True, duration_ms=100.0)
        
        # Track failure
        collector.track_provider_attempt(
            "provider1",
            success=False,
            duration_ms=50.0,
            error="Rate limited"
        )
        
        metrics = collector.metrics.providers["provider1"]
        assert metrics.attempts == 2
        assert metrics.successes == 1
        assert metrics.failures == 1
        assert metrics.total_time_ms == 150.0
        assert metrics.last_error == "Rate limited"
    
    def test_finish_generation(self):
        """Collector should mark generation as complete."""
        collector = MetricsCollector()
        
        collector.finish(success=True, output_path="/path/to/video.mp4")
        
        assert collector.metrics.success is True
        assert collector.metrics.output_path == "/path/to/video.mp4"
        assert collector.metrics.end_time is not None
        assert collector.metrics.total_duration_ms > 0
    
    def test_get_summary(self):
        """Collector should provide summary of key metrics."""
        collector = MetricsCollector()
        
        # Add some steps
        step1 = collector.start_step("step1")
        time.sleep(0.01)
        collector.end_step(step1, status="success")
        
        step2 = collector.start_step("step2")
        collector.end_step(step2, status="failed", error="Test error")
        
        collector.finish(success=False, error="Pipeline failed")
        
        summary = collector.get_summary()
        
        assert summary["success"] is False
        assert summary["steps_completed"] == 1
        assert summary["steps_failed"] == 1
        assert summary["request_id"] == collector.metrics.request_id
    
    def test_log_json_to_file(self, tmp_path):
        """Collector should write metrics to JSON file."""
        collector = MetricsCollector(config_name="test")
        
        # Simulate a complete generation
        step = collector.start_step("image_generation")
        collector.end_step(step, status="success")
        collector.track_provider_attempt("provider1", success=True, duration_ms=1000.0)
        collector.finish(success=True, output_path="/video.mp4")
        
        # Write to file
        log_file = tmp_path / "metrics.json"
        json_str = collector.log_json(log_file)
        
        assert log_file.exists()
        
        # Parse JSON
        metrics_data = json.loads(json_str)
        assert metrics_data["request_id"] == collector.metrics.request_id
        assert metrics_data["config_name"] == "test"
        assert metrics_data["success"] is True


class TestStructuredLogger:
    """Test structured logging with request IDs."""
    
    def test_structured_logger_set_request_id(self):
        """Logger should set and use request ID."""
        logger = StructuredLogger("test_logger")
        
        logger.set_request_id("req123")
        assert logger.request_id == "req123"
    
    def test_structured_logger_formats_with_request_id(self, caplog):
        """Logger should include request ID in messages."""
        logger = StructuredLogger("test_logger")
        logger.set_request_id("req456")
        
        with caplog.at_level(logging.INFO):
            logger.info("Test message")
        
        # Should contain request ID in log
        assert any("req456" in record.message for record in caplog.records)


class TestJSONFormatter:
    """Test JSON log formatting."""
    
    def test_json_formatter_formats_record(self):
        """Formatter should convert log record to JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        json_str = formatter.format(record)
        
        # Parse JSON
        log_data = json.loads(json_str)
        assert log_data["message"] == "Test message"
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test"
    
    def test_json_formatter_includes_extra_fields(self):
        """Formatter should include extra fields in JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None
        )
        # Add extra fields
        record.request_id = "req123"
        record.duration_ms = 100.5
        
        json_str = formatter.format(record)
        
        log_data = json.loads(json_str)
        assert log_data["request_id"] == "req123"
        assert log_data["duration_ms"] == 100.5
    
    def test_json_formatter_handles_exceptions(self):
        """Formatter should include exception info in JSON."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info()
            )
        
        json_str = formatter.format(record)
        
        log_data = json.loads(json_str)
        assert "exception" in log_data
        assert log_data["exception"]["type"] == "ValueError"
        assert "Test exception" in log_data["exception"]["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

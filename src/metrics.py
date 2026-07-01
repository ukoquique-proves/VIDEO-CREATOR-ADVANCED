"""
Performance Metrics Collection & Tracking

Collects structured performance metrics throughout the video generation pipeline:
- Step-level timing (TTS, image generation, assembly, etc.)
- Provider performance (success rates, failover frequency)
- Overall generation metrics
- Request tracing with unique request IDs
"""

import time
import json
import logging
import uuid
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProviderMetrics:
    """Metrics for a single provider."""
    name: str
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    total_time_ms: float = 0.0
    last_error: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.attempts == 0:
            return 0.0
        return (self.successes / self.attempts) * 100
    
    @property
    def avg_time_ms(self) -> float:
        """Calculate average time per attempt."""
        if self.attempts == 0:
            return 0.0
        return self.total_time_ms / self.attempts


@dataclass
class StepMetrics:
    """Metrics for a single pipeline step."""
    name: str  # e.g., "image_generation", "tts_audio", "assembly"
    status: str = "pending"  # "pending", "running", "success", "failed"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class GenerationMetrics:
    """Overall metrics for a video generation run."""
    request_id: str
    start_time: float
    config_name: Optional[str] = None
    language: Optional[str] = None
    tts_backend: Optional[str] = None
    image_engine: Optional[str] = None
    
    # Collection data
    steps: List[StepMetrics] = field(default_factory=list)
    providers: Dict[str, ProviderMetrics] = field(default_factory=dict)
    
    # Results
    end_time: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    output_path: Optional[str] = None
    
    @property
    def total_duration_ms(self) -> float:
        """Total generation time in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000
    
    @property
    def total_failovers(self) -> int:
        """Total number of failovers across all providers."""
        return sum(
            max(0, p.attempts - 1) for p in self.providers.values()
        )
    
    @property
    def image_provider_attempts(self) -> int:
        """Total image provider attempts."""
        return sum(p.attempts for p in self.providers.values())
    
    @property
    def image_provider_success_rate(self) -> float:
        """Overall image provider success rate."""
        if self.image_provider_attempts == 0:
            return 0.0
        successes = sum(p.successes for p in self.providers.values())
        return (successes / self.image_provider_attempts) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON logging."""
        return {
            "request_id": self.request_id,
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat(),
            "config_name": self.config_name,
            "language": self.language,
            "tts_backend": self.tts_backend,
            "image_engine": self.image_engine,
            "success": self.success,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "error": self.error,
            "output_path": self.output_path,
            "steps": [s.to_dict() for s in self.steps],
            "providers": {
                name: {
                    "attempts": m.attempts,
                    "successes": m.successes,
                    "failures": m.failures,
                    "success_rate": round(m.success_rate, 2),
                    "total_time_ms": round(m.total_time_ms, 2),
                    "avg_time_ms": round(m.avg_time_ms, 2),
                    "last_error": m.last_error,
                }
                for name, m in self.providers.items()
            },
            "summary": {
                "image_provider_attempts": self.image_provider_attempts,
                "image_provider_success_rate": round(self.image_provider_success_rate, 2),
                "total_failovers": self.total_failovers,
            }
        }


class MetricsCollector:
    """Collects and manages metrics for a video generation run."""
    
    def __init__(self, config_name: Optional[str] = None, language: Optional[str] = None,
                 tts_backend: Optional[str] = None, image_engine: Optional[str] = None):
        """Initialize metrics collector for a generation run."""
        self.metrics = GenerationMetrics(
            request_id=str(uuid.uuid4())[:8],  # Short ID for readability
            start_time=time.time(),
            config_name=config_name,
            language=language,
            tts_backend=tts_backend,
            image_engine=image_engine,
        )
    
    def start_step(self, step_name: str, metadata: Optional[Dict[str, Any]] = None) -> StepMetrics:
        """Mark the start of a pipeline step."""
        step = StepMetrics(
            name=step_name,
            status="running",
            start_time=time.time(),
            metadata=metadata or {}
        )
        self.metrics.steps.append(step)
        logger.debug(f"[{self.metrics.request_id}] Starting step: {step_name}")
        return step
    
    def end_step(self, step: StepMetrics, status: str = "success", error: Optional[str] = None):
        """Mark the end of a pipeline step."""
        step.status = status
        step.end_time = time.time()
        step.error = error
        
        duration_ms = step.duration_ms
        logger.debug(
            f"[{self.metrics.request_id}] Completed step {step.name}: {status} ({duration_ms:.1f}ms)",
            extra={"duration_ms": duration_ms, "status": status}
        )
    
    def track_provider_attempt(self, provider_name: str, success: bool, 
                               duration_ms: float = 0.0, error: Optional[str] = None):
        """Track a single provider attempt."""
        if provider_name not in self.metrics.providers:
            self.metrics.providers[provider_name] = ProviderMetrics(name=provider_name)
        
        provider = self.metrics.providers[provider_name]
        provider.attempts += 1
        provider.total_time_ms += duration_ms
        
        if success:
            provider.successes += 1
            logger.debug(
                f"[{self.metrics.request_id}] Provider {provider_name}: SUCCESS ({duration_ms:.1f}ms)"
            )
        else:
            provider.failures += 1
            provider.last_error = error
            logger.debug(
                f"[{self.metrics.request_id}] Provider {provider_name}: FAILED ({duration_ms:.1f}ms) - {error}"
            )
    
    def finish(self, success: bool, error: Optional[str] = None, output_path: Optional[str] = None):
        """Mark generation as complete."""
        self.metrics.end_time = time.time()
        self.metrics.success = success
        self.metrics.error = error
        self.metrics.output_path = output_path
        
        logger.info(
            f"[{self.metrics.request_id}] Generation {'COMPLETED' if success else 'FAILED'}: "
            f"{self.metrics.total_duration_ms:.1f}ms",
            extra=self.metrics.to_dict()
        )
    
    def get_metrics(self) -> GenerationMetrics:
        """Get the collected metrics."""
        return self.metrics
    
    def log_json(self, filepath: Optional[Path] = None) -> str:
        """Log metrics as JSON and optionally write to file."""
        metrics_dict = self.metrics.to_dict()
        metrics_json = json.dumps(metrics_dict, indent=2)
        
        if filepath:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(metrics_json)
            logger.info(f"Metrics written to {filepath}")
        
        return metrics_json
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of key metrics."""
        return {
            "request_id": self.metrics.request_id,
            "success": self.metrics.success,
            "total_time_sec": round(self.metrics.total_duration_ms / 1000, 2),
            "image_provider_success_rate": round(self.metrics.image_provider_success_rate, 1),
            "total_failovers": self.metrics.total_failovers,
            "steps_completed": len([s for s in self.metrics.steps if s.status == "success"]),
            "steps_failed": len([s for s in self.metrics.steps if s.status == "failed"]),
        }


class StructuredLogger:
    """Wrapper for structured JSON logging with request IDs."""
    
    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self.request_id: Optional[str] = None
    
    def set_request_id(self, request_id: str):
        """Set request ID for all subsequent logs."""
        self.request_id = request_id
    
    def info(self, message: str, **extra):
        """Log info with structured data."""
        full_message = f"[{self.request_id}] {message}" if self.request_id else message
        self.logger.info(full_message, extra=extra)
    
    def debug(self, message: str, **extra):
        """Log debug with structured data."""
        full_message = f"[{self.request_id}] {message}" if self.request_id else message
        self.logger.debug(full_message, extra=extra)
    
    def warning(self, message: str, **extra):
        """Log warning with structured data."""
        full_message = f"[{self.request_id}] {message}" if self.request_id else message
        self.logger.warning(full_message, extra=extra)
    
    def error(self, message: str, **extra):
        """Log error with structured data."""
        full_message = f"[{self.request_id}] {message}" if self.request_id else message
        self.logger.error(full_message, extra=extra)

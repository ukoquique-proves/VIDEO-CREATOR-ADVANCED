# Structured Logging & Performance Metrics

## Overview

This feature adds comprehensive structured logging and performance metrics throughout the video generation pipeline. It provides:

- **Structured JSON logging** with request IDs, timestamps, and contextual data
- **Step-level timing** for each pipeline stage (TTS, image generation, subtitles, assembly)
- **Provider performance metrics** (success rates, failover counts, execution times)
- **Request tracing** with unique IDs for tracking a single generation across the entire system
- **Observability hooks** for monitoring, debugging, and performance optimization

## Architecture

### Components

#### 1. **Metrics Collection** (`src/metrics.py`)

Four core dataclasses track metrics at different levels:

- **`ProviderMetrics`**: Per-provider statistics
  - `attempts`, `successes`, `failures`
  - `success_rate`, `avg_time_ms`
  - `last_error` for debugging

- **`StepMetrics`**: Per-pipeline-step timing
  - `name` (e.g., "image_generation", "tts_audio")
  - `status` (pending, running, success, failed)
  - `duration_ms`, `error`, `metadata`

- **`GenerationMetrics`**: Overall generation run
  - Request ID, start/end times
  - Aggregated statistics (total failovers, success rates)
  - Complete step and provider history

- **`MetricsCollector`**: API for collecting metrics during generation
  - `start_step()` / `end_step()` for tracking pipeline steps
  - `track_provider_attempt()` for provider-level tracking
  - `finish()` to mark generation complete
  - `log_json()` to export metrics as JSON

#### 2. **Structured Logging** (`src/json_logging.py`)

- **`JSONFormatter`**: Custom logging formatter that outputs JSON
  - Preserves all standard logging fields
  - Includes extra fields passed via `extra={}` parameter
  - Captures exception tracebacks with full context
  - Compatible with standard Python logging module

- **`setup_json_logging()`**: Configure app-wide JSON logging
  - Console handler for real-time JSON output
  - Optional file handler for JSON log persistence
  - Configurable log level

#### 3. **Provider Manager Integration**

`src/image_providers/manager.py` now:
- Accepts optional `MetricsCollector` during initialization
- Times each provider attempt
- Tracks successes, failures, and errors
- Reports provider-specific performance metrics

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Video Generation Request                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─ Create MetricsCollector(request_id="abc123")
                   │
                   ├─ TTS Step
                   │  ├─ start_step("tts_audio")
                   │  ├─ Run TTS adapter
                   │  └─ end_step(..., status="success")
                   │
                   ├─ Image Generation Step
                   │  ├─ start_step("image_generation")
                   │  ├─ Provider attempt 1: track_provider_attempt("provider1", success=true)
                   │  └─ end_step(..., status="success")
                   │
                   ├─ Subtitle Generation Step
                   │  ├─ start_step("subtitles")
                   │  ├─ Generate subtitles
                   │  └─ end_step(..., status="success")
                   │
                   ├─ Assembly Step
                   │  ├─ start_step("assembly")
                   │  ├─ Assemble final video
                   │  └─ end_step(..., status="success")
                   │
                   ├─ finish(success=true, output_path="/video.mp4")
                   │
                   └─ Export metrics as JSON
                      {
                        "request_id": "abc123",
                        "timestamp": "2026-06-28T...",
                        "success": true,
                        "total_duration_ms": 45200.5,
                        "steps": [...],
                        "providers": {...},
                        "summary": {...}
                      }
```

## Usage

### Basic Example

```python
from src.metrics import MetricsCollector
from src.orchestrator import VideoOrchestrator

# Create metrics collector
metrics = MetricsCollector(
    config_name="my_video",
    language="en",
    tts_backend="edge-tts",
    image_engine="siliconflow"
)

# Track a step
step = metrics.start_step("image_generation", metadata={"prompt": "a sunny beach"})
try:
    # ... do image generation ...
    metrics.end_step(step, status="success")
except Exception as e:
    metrics.end_step(step, status="failed", error=str(e))

# Track provider attempts
metrics.track_provider_attempt("pollinations", success=False, duration_ms=5000, error="IP-blocked")
metrics.track_provider_attempt("siliconflow", success=True, duration_ms=2500)

# Finish collection
metrics.finish(success=True, output_path="/output/video.mp4")

# Export as JSON
json_metrics = metrics.log_json()
print(json_metrics)

# Get summary
summary = metrics.get_summary()
print(f"Generation took {summary['total_time_sec']}s with success rate {summary['image_provider_success_rate']}%")
```

### JSON Output Example

```json
{
  "request_id": "abc12345",
  "timestamp": "2026-06-28T15:30:45.123456",
  "config_name": "my_video",
  "language": "en",
  "tts_backend": "edge-tts",
  "image_engine": "siliconflow",
  "success": true,
  "total_duration_ms": 45234.5,
  "error": null,
  "output_path": "/output/video.mp4",
  "steps": [
    {
      "name": "tts_audio",
      "status": "success",
      "duration_ms": 8234.5,
      "error": null,
      "metadata": {"language": "en"}
    },
    {
      "name": "image_generation",
      "status": "success",
      "duration_ms": 2500.0,
      "error": null,
      "metadata": {"prompts_count": 5}
    },
    {
      "name": "subtitles",
      "status": "success",
      "duration_ms": 1234.0,
      "error": null,
      "metadata": {}
    },
    {
      "name": "assembly",
      "status": "success",
      "duration_ms": 32000.0,
      "error": null,
      "metadata": {}
    }
  ],
  "providers": {
    "pollinations": {
      "attempts": 1,
      "successes": 0,
      "failures": 1,
      "success_rate": 0.0,
      "total_time_ms": 5000.0,
      "avg_time_ms": 5000.0,
      "last_error": "IP-blocked"
    },
    "siliconflow": {
      "attempts": 1,
      "successes": 1,
      "failures": 0,
      "success_rate": 100.0,
      "total_time_ms": 2500.0,
      "avg_time_ms": 2500.0,
      "last_error": null
    }
  },
  "summary": {
    "image_provider_attempts": 2,
    "image_provider_success_rate": 50.0,
    "total_failovers": 1
  }
}
```

### Structured Logging Example

```python
from src.json_logging import setup_json_logging, get_structured_logger

# Setup JSON logging once at app start
setup_json_logging(log_file="output/logs/metrics.jsonl")

# Use structured logger
logger = get_structured_logger("my_module")

# Log with context
logger.info(
    "Image generation started",
    request_id="abc123",
    provider="siliconflow",
    prompt_count=5
)

# All logs are JSON formatted
# Output: {"timestamp": "...", "level": "INFO", "message": "Image generation started", "request_id": "abc123", ...}
```

## Key Features

### 1. **Request Tracing**
Every generation gets a unique 8-character request ID that appears in all logs and metrics for that run. Easy to correlate events across the system.

```
[abc12345] Starting step: tts_audio
[abc12345] Completed step tts_audio: success (8234.5ms)
[abc12345] Trying provider 1/2: pollinations...
[abc12345] Provider pollinations: FAILED (5000.0ms) - IP-blocked
```

### 2. **Provider Performance Tracking**
Monitor which providers work best on your infrastructure:
- Success rates (how often does this provider succeed?)
- Execution times (is it fast or slow?)
- Failure patterns (what errors do we see?)
- Failover frequency (how often do we need to try backups?)

### 3. **Step-Level Timing**
Identify bottlenecks in the pipeline:
- TTS audio generation: 8s
- Image generation: 2.5s ← Fast failover saves time here
- Subtitle rendering: 1.2s
- Video assembly: 32s ← Slowest step

### 4. **JSON Export**
All metrics available as structured JSON for:
- Integration with monitoring systems (Prometheus, Datadog, etc.)
- Statistical analysis (success rates over time, performance trends)
- Debugging (trace exact sequence of events)
- Alerting (trigger on low success rates or long generation times)

## Performance Metrics Available

| Metric | Type | Use Case |
|--------|------|----------|
| `request_id` | string | Trace single generation through all logs |
| `total_duration_ms` | float | Overall generation time |
| `steps[*].duration_ms` | float | Identify bottleneck pipeline stages |
| `providers[*].success_rate` | float | Monitor provider reliability |
| `providers[*].avg_time_ms` | float | Compare provider speed |
| `total_failovers` | int | Measure fault tolerance performance |
| `image_provider_success_rate` | float | Overall system health |

## Integration Points

### Already Integrated
- ✅ Provider Manager: Times and tracks all provider attempts
- ✅ Metrics tests: 21 comprehensive unit tests (all passing)

### Ready for Integration (Next Steps)
- [ ] Orchestrator: Track TTS, image, subtitle, assembly steps
- [ ] Adapters: Pass metrics collector through context
- [ ] UI: Display metrics in Streamlit interface
- [ ] Monitoring: Export metrics to external systems

## Testing

Run metrics tests:
```bash
pytest tests/test_metrics.py -v
```

Results: **21 tests passing**
- 3 ProviderMetrics tests
- 3 StepMetrics tests  
- 4 GenerationMetrics tests
- 6 MetricsCollector tests
- 2 StructuredLogger tests
- 3 JSONFormatter tests

## Logging Configuration Examples

### Development (Console Only)
```python
setup_json_logging()  # JSON to stdout only
```

### Production (File + Console)
```python
setup_json_logging(log_file="output/logs/metrics.jsonl")
```

### High-Volume Monitoring (Info Only)
```python
import logging
setup_json_logging(log_file="output/logs/metrics.jsonl", log_level=logging.INFO)
```

## Future Enhancements

1. **Metrics Aggregation**: Collect metrics across multiple runs to calculate averages, percentiles
2. **Provider Health Dashboard**: Real-time visualization of provider performance
3. **Alerting**: Trigger alerts when metrics exceed thresholds (e.g., success rate < 80%)
4. **Performance Trends**: Track metrics over time to identify regressions
5. **Cost Tracking**: Combine with provider pricing to calculate cost per generation
6. **Auto-Tuning**: Use metrics to automatically adjust timeouts, retry counts, provider ordering

## References

- [Python JSON Logging](https://docs.python.org/3/library/json.html)
- [Structured Logging Best Practices](https://kartar.net/2015/12/structured-logging/)
- [Request Tracing Patterns](https://www.w3.org/TR/trace-context/)

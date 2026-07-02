"""
CLI entry point for VideoCreation.

Usage::

    python -m src.main --config my_video.yaml
    python -m src.main --config my_video.json --output-dir /tmp/videos
    python -m src.main --config my_video.yaml --background

Configuration files can be YAML or JSON and must match the
``VideoConfiguration`` schema (see src/schema.py or the README).
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from src.schema import VideoConfiguration
from src.orchestrator import VideoOrchestrator
from src.lock_service import (
    acquire_background_lock,
    release_background_lock
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# Backward compatibility
_acquire_background_lock = acquire_background_lock
_release_background_lock = release_background_lock


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="videocreation",
        description="Generate a video from a YAML or JSON configuration file.",
    )
    parser.add_argument(
        "-c", "--config",
        required=True,
        metavar="FILE",
        help="Path to a .yaml, .yml, or .json configuration file.",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=str(Path(__file__).resolve().parent.parent / "output"),
        metavar="DIR",
        help="Directory to save the generated video and workspace files.",
    )
    parser.add_argument(
        "-b", "--background",
        action="store_true",
        help="Run video generation in the background (detached process).",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error("Configuration file not found: %s", config_path)
        sys.exit(1)

    # Parse config file
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            suffix = config_path.suffix.lower()
            if suffix in (".yaml", ".yml"):
                raw = yaml.safe_load(f)
            elif suffix == ".json":
                raw = json.load(f)
            else:
                logger.error(
                    "Unsupported file format '%s'. Use .yaml, .yml, or .json.", suffix
                )
                sys.exit(1)
    except Exception as exc:
        logger.error("Failed to read configuration file: %s", exc)
        sys.exit(1)

    # Validate against schema
    try:
        config = VideoConfiguration(**raw)
    except Exception as exc:
        logger.error("Invalid configuration: %s", exc)
        sys.exit(1)

    lock_path = Path(args.output_dir) / "logs" / ".generation.lock"
    lock_acquired = False

    if args.background:
        # When running in background, do NOT acquire lock in parent — let the child handle it!
        # This prevents the race condition where parent releases lock before child acquires it
        logger.info("Starting video generation in background...")
        log_dir = Path(args.output_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{config.title}.log"

        # Detach process and run in background
        cmd = [
            sys.executable, "-m", "src.main",
            "--config", str(config_path.resolve()),
            "--output-dir", args.output_dir,
        ]

        with open(log_path, "w") as f:
            proc = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=f,
                start_new_session=True,
                close_fds=True,
            )

        print(f"Background generation started! PID: {proc.pid}")
        print(f"Logs: {log_path}")
        sys.exit(0)

    # Foreground execution: acquire lock and run pipeline
    if not acquire_background_lock(lock_path):
        logger.error(
            "A video generation is already running for output directory %s. "
            "Wait for the current run to finish before starting another one.",
            args.output_dir,
        )
        sys.exit(1)
    lock_acquired = True

    try:
        # Run pipeline in foreground
        orchestrator = VideoOrchestrator(output_dir=args.output_dir)
        result = orchestrator.create_video(config)
        print(f"\nDone: {result['output_path']}")
    except Exception as exc:
        logger.error("Video generation failed: %s", exc)
        sys.exit(1)
    finally:
        if lock_acquired:
            release_background_lock(lock_path)


if __name__ == "__main__":
    main()

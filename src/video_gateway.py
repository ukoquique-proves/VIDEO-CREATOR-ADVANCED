from dataclasses import dataclass
from typing import Callable, Optional, List, Protocol, Any
import logging

logger = logging.getLogger(__name__)

# Adapter Protocols describe expected call signatures for common pipeline
# adapters. These are intentionally lightweight and permissive at runtime;
# they improve static typing and document expected contracts.


class TTSCallable(Protocol):
    def __call__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any: ...


class GenerateFromPromptsCallable(Protocol):
    def __call__(
        self,
        prompts: List[str],
        visuals_dir: str,
        style: Optional[str] = None,
        engine: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        provider_manager: Optional[Any] = None,
    ) -> List[str]: ...


class CopyProvidedImagesCallable(Protocol):
    def __call__(self, images: List[str], dest_dir: str) -> List[str]: ...


class ModifyImagesCallable(Protocol):
    def __call__(self, visual_files: List[str], instructions: str) -> List[str]: ...


class AssembleVideoCallable(Protocol):
    def __call__(
        self,
        audio_path: str,
        visual_files: List[str],
        title: str,
        output_dir: str,
        output_format: str,
        background_music: Optional[str],
        width: int,
        height: int,
        duration: Optional[float],
        visual_durations: Optional[List[float]],
    ) -> str: ...


# Lightweight gateway dataclass to bundle pipeline callables for dependency injection.
# Each callable should follow the signatures used by the current adapters; tests
# and backwards-compatible code can provide thin shims that call the existing
# adapter implementations.


@dataclass
class VideoGateway:
    tts: Optional[TTSCallable] = None
    generate_from_prompts: Optional[GenerateFromPromptsCallable] = None
    copy_provided_images: Optional[CopyProvidedImagesCallable] = None
    modify_images: Optional[ModifyImagesCallable] = None
    assemble_video: Optional[AssembleVideoCallable] = None
    subtitle_backend: Optional[object] = None

    def __post_init__(self):
        # If the gateway is used as a partial bundle (some callables set,
        # others left None), that's often a configuration mistake. Emit a
        # warning so callers notice at startup rather than at runtime.
        provided = {k: v for k, v in self.__dict__.items() if v is not None}
        if provided and len(provided) < len(self.__dict__):
            missing = [k for k, v in self.__dict__.items() if v is None]
            logger.warning(
                "VideoGateway provided partially (%s present, %s missing). Some calls may fall back to module adapters.",
                list(provided.keys()), missing,
            )

        # Basic runtime validation: ensure any provided adapter is callable.
        # This is a lightweight check to fail fast on misconfiguration.
        for name, value in provided.items():
            if name == "subtitle_backend":
                # backend objects are not expected to be callables
                continue
            if not callable(value):
                raise TypeError(f"VideoGateway attribute '{name}' must be callable, got {type(value)!r}")

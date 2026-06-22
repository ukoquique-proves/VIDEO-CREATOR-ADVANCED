from dataclasses import dataclass
from typing import Callable, Optional, List

# Lightweight gateway dataclass to bundle pipeline callables for dependency injection.
# Each callable should follow the signatures used by the current adapters; tests
# and backwards-compatible code can provide thin shims that call the existing
# adapter implementations.


@dataclass
class VideoGateway:
    tts: Optional[Callable] = None
    generate_from_prompts: Optional[Callable] = None
    copy_provided_images: Optional[Callable] = None
    modify_images: Optional[Callable] = None
    assemble_video: Optional[Callable] = None
    subtitle_backend: Optional[object] = None

    def __post_init__(self):
        # Nothing required; dataclass only groups callables for DI.
        pass

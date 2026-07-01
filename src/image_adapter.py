"""
Image Adapter — AI image generation & modification bridge.

Provider priority:
  0. Picsum (seeded)  — used only when `engine="picsum"` is explicitly requested
  1. Native ImageProviders (Cloudflare → SiliconFlow → Pollinations → HuggingFace)
  2. Pillow placeholder fallback  — offline / testing
"""

import os
import re
import time
import logging
import textwrap
import warnings
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import quote

from src import config_loader
from src.image_providers.manager import ProviderManager
from src.image_providers.registry import get_provider_registry, auto_register_providers

logger = logging.getLogger(__name__)

# Global manager instance to persist provider health/failover state across calls (backward compatibility)
_provider_manager: Optional[ProviderManager] = None


def _get_provider_manager() -> ProviderManager:
    """Get or create the global ProviderManager instance with auto-registered providers."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
        # Auto-register all available providers based on credentials
        auto_register_providers(_provider_manager)
        # Log provider status for debugging
        get_provider_registry().log_provider_status()
    return _provider_manager


# ---------------------------------------------------------------------------
# NEW Stable Public API
# ---------------------------------------------------------------------------

def generate_images_from_prompts(
    prompts: List[str],
    output_dir: str,
    *,
    style: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    engine: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    context: Optional[Any] = None,
    provider_manager: Optional[ProviderManager] = None,
) -> List[str]:
    """Generate one image per prompt and return a list of file paths.

    Args:
        prompts: List of text prompts for AI image generation
        output_dir: Directory where generated images should be saved
        style: Optional style preset (overrides config default)
        aspect_ratio: Optional aspect ratio (overrides config default)
        engine: Optional image engine to use (overrides config default)
        width: Optional image width in pixels
        height: Optional image height in pixels
        context: Optional VideoContext object (for backward compatibility)
        provider_manager: Optional ProviderManager for dependency injection

    Returns:
        List of file paths to the generated images
    """
    # Determine config and logger
    if context is not None:
        cfg = context.merged_config.get("image", {})
        vcfg = context.merged_config.get("video", {})
        use_logger = context.logger
    else:
        cfg = config_loader.image()
        vcfg = config_loader.video()
        use_logger = logger

    # Resolve parameters with defaults from config
    if style is None:
        style = cfg.get("style", "photorealistic")
    if aspect_ratio is None:
        aspect_ratio = cfg.get("aspect_ratio", "9:16")
    if engine is None:
        engine = cfg.get("engine")

    if engine in {"unsplash", "pexels"}:
        raise ValueError(
            f"Unsupported image engine '{engine}'. "
            "Unsplash and Pexels are not implemented yet. "
            "Use cloudflare, siliconflow, pollinations, huggingface, or picsum."
        )

    # Resolve dimensions
    if width is None or height is None:
        base_w = vcfg.get("width", 1080)
        base_h = vcfg.get("height", 1920)
        _w, _h = _dimensions_for_aspect(aspect_ratio, base_w, base_h)
        if width is None:
            width = _w
        if height is None:
            height = _h

    os.makedirs(output_dir, exist_ok=True)

    # Try Picsum first if explicitly requested
    if engine == "picsum":
        stock_dir = os.path.join(output_dir, "stock")
        os.makedirs(stock_dir, exist_ok=True)
        paths = _picsum_batch(prompts, stock_dir, width, height, use_logger)
        if paths:
            return paths
        use_logger.warning("Picsum failed or returned partial results — trying next provider.")

    # Try native image generation
    gen_dir = os.path.join(output_dir, "generated")
    os.makedirs(gen_dir, exist_ok=True)
    native_paths = _try_native_image_generation(prompts, gen_dir, style, width, height, engine, use_logger, provider_manager)
    if native_paths:
        return native_paths

    # Fall back to placeholders
    use_logger.warning("Native image generation failed or unavailable — using Pillow placeholder images.")
    return _generate_placeholder_images(prompts, gen_dir, width=width, height=height, vcfg=vcfg, log=use_logger)


def copy_user_provided_media(
    image_paths: List[str],
    output_dir: str,
    *,
    context: Optional[Any] = None,
) -> List[str]:
    """Validate and copy user-provided visual files into the workspace.

    Args:
        image_paths: List of file paths to user-provided images/videos
        output_dir: Directory where files should be copied
        context: Optional VideoContext object (for backward compatibility)

    Returns:
        List of file paths to the copied files
    """
    use_logger = context.logger if context is not None else logger
    import shutil
    cached_dir = os.path.join(output_dir, "cached")
    os.makedirs(cached_dir, exist_ok=True)
    copied: List[str] = []
    for src in image_paths:
        if not os.path.isfile(src):
            use_logger.warning("Visual asset not found, skipping: %s", src)
            continue
        dst = os.path.join(cached_dir, os.path.basename(src))
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


# ---------------------------------------------------------------------------
# Legacy Public API (Backward Compatibility)
# ---------------------------------------------------------------------------

from src.schema import VideoContext

def generate_from_prompts(
    *args,
    **kwargs
) -> List[str]:
    """Generate one image per prompt and return a list of file paths.

    DEPRECATED: Use generate_images_from_prompts() instead.

    The preferred call style is keyword-based, for example:
    generate_from_prompts(prompts=[...], output_dir="...", context=context)

    Legacy positional calls that pass a VideoContext as the first argument are
    still supported for compatibility, but they emit a DeprecationWarning.
    """
    warnings.warn(
        "generate_from_prompts() is deprecated; use generate_images_from_prompts() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    
    provider_manager = kwargs.pop("provider_manager", None)
    
    if args and isinstance(args[0], VideoContext):
        warnings.warn(
            "Passing VideoContext positionally to generate_from_prompts() is deprecated; use context=... instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        context = args[0]
        prompts = args[1] if len(args) > 1 else kwargs.pop("prompts", None)
        output_dir = args[2] if len(args) > 2 else kwargs.pop("output_dir", None)
        style = args[3] if len(args) > 3 else kwargs.pop("style", None)
        aspect_ratio = args[4] if len(args) > 4 else kwargs.pop("aspect_ratio", None)
        engine = args[5] if len(args) > 5 else kwargs.pop("engine", None)
        width = args[6] if len(args) > 6 else kwargs.pop("width", None)
        height = args[7] if len(args) > 7 else kwargs.pop("height", None)
    else:
        context = None
        prompts = args[0] if len(args) > 0 else kwargs.pop("prompts", None)
        output_dir = args[1] if len(args) > 1 else kwargs.pop("output_dir", None)
        style = args[2] if len(args) > 2 else kwargs.pop("style", None)
        aspect_ratio = args[3] if len(args) > 3 else kwargs.pop("aspect_ratio", None)
        engine = args[4] if len(args) > 4 else kwargs.pop("engine", None)
        width = args[5] if len(args) > 5 else kwargs.pop("width", None)
        height = args[6] if len(args) > 6 else kwargs.pop("height", None)
    
    # Delegate to the new stable API
    return generate_images_from_prompts(
        prompts=prompts,
        output_dir=output_dir,
        style=style,
        aspect_ratio=aspect_ratio,
        engine=engine,
        width=width,
        height=height,
        context=context,
        provider_manager=provider_manager,
    )


def copy_provided_images(*args, **kwargs) -> List[str]:
    """Validate and copy user-provided visual files into the workspace.

    DEPRECATED: Use copy_user_provided_media() instead.

    The preferred call style is keyword-based, for example:
    copy_provided_images(image_paths=[...], output_dir="...", context=context)

    Legacy positional calls that pass a VideoContext as the first argument are
    still supported for compatibility, but they emit a DeprecationWarning.
    """
    warnings.warn(
        "copy_provided_images() is deprecated; use copy_user_provided_media() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    
    if args and isinstance(args[0], VideoContext):
        warnings.warn(
            "Passing VideoContext positionally to copy_provided_images() is deprecated; use context=... instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        context = args[0]
        image_paths = args[1] if len(args) > 1 else kwargs.pop("image_paths", None)
        output_dir = args[2] if len(args) > 2 else kwargs.pop("output_dir", None)
    else:
        context = None
        image_paths = args[0] if len(args) > 0 else kwargs.pop("image_paths", None)
        output_dir = args[1] if len(args) > 1 else kwargs.pop("output_dir", None)
    
    # Delegate to the new stable API
    return copy_user_provided_media(
        image_paths=image_paths,
        output_dir=output_dir,
        context=context,
    )


# Forward-looking alias — same behavior, clearer name for mixed media callers.
copy_provided_media = copy_provided_images


def modify_images(image_paths: List[str], instructions: str) -> List[str]:
    """Apply AI modifications to images.

    This feature is not yet implemented. The pipeline should fail fast when
    a user explicitly requests image modifications, rather than silently
    continuing with unchanged visuals.
    """
    raise NotImplementedError(
        "image_modification_instructions is not yet implemented. "
        "Remove this field from your configuration or wait for the feature."
    )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _dimensions_for_aspect(aspect: str, base_w: int, base_h: int) -> tuple:
    """Resolve width/height from aspect ratio string (e.g. '16:9')."""
    if aspect == "16:9":
        return max(base_w, base_h), min(base_w, base_h)
    return min(base_w, base_h), max(base_w, base_h)


def _try_native_image_generation(
    prompts: List[str],
    output_dir: str,
    style: str,
    width: int,
    height: int,
    preferred_engine: Optional[str] = None,
    log = logger,
    provider_manager: Optional[ProviderManager] = None,
) -> Optional[List[str]]:
    """Use the provided ProviderManager (or global one if not provided) to generate images with automatic failover."""
    manager = provider_manager if provider_manager is not None else _get_provider_manager()
    
    manager.output_dir = Path(output_dir)
    manager.output_dir.mkdir(parents=True, exist_ok=True)
    
    if preferred_engine:
        has_preferred = any(p.name == preferred_engine for p in manager.providers)
        if not has_preferred:
            log.warning("Preferred engine '%s' not found among configured providers.", preferred_engine)
        manager.providers.sort(key=lambda p: 0 if p.name == preferred_engine else 1)

    results = manager.generate_images_batch(prompts, width=width, height=height, style=style)
    
    if all(r.success for r in results):
        return [r.image_path for r in results if r.image_path]
    
    log.warning("Native image generation batch incomplete.")
    return None


# ---------------------------------------------------------------------------
# Picsum seeded by prompt keywords
# ---------------------------------------------------------------------------

def _prompt_to_seed(prompt: str, index: Optional[int] = None) -> str:
    """Extract the first few meaningful words from a prompt to use as a Picsum seed."""
    stopwords = {"a", "an", "the", "at", "in", "on", "of", "and", "with", "for", "to", "is"}
    words = re.sub(r"[^a-z0-9 ]", "", prompt.lower()).split()
    keywords = [w for w in words if w not in stopwords][:4]
    base = "-".join(keywords) if keywords else "photo"
    if index is not None:
        return f"{base}-{index}"
    return base


def _picsum_batch(
    prompts: List[str],
    output_dir: str,
    width: int,
    height: int,
    log = logger,
) -> List[str]:
    """Fetch one Picsum image per prompt using a keyword-derived seed."""
    import requests

    paths: List[str] = []
    timeout = 30

    for idx, prompt in enumerate(prompts):
        seed = _prompt_to_seed(prompt, idx)
        url  = f"https://picsum.photos/seed/{seed}/{width}/{height}.jpg"
        log.info("[%d/%d] Picsum seed='%s' — %s", idx + 1, len(prompts), seed, prompt[:60])

        try:
            response = requests.get(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 200:
                filename  = f"picsum_{idx:03d}_{seed}.jpg"
                file_path = os.path.join(output_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(response.content)
                paths.append(file_path)
                log.info("  ✓ saved → %s", file_path)
            else:
                log.warning("  HTTP %d for seed '%s'", response.status_code, seed)
        except Exception as exc:
            log.warning("  failed for seed '%s': %s", seed, exc)

        if idx < len(prompts) - 1:
            time.sleep(0.5)

    if len(paths) < len(prompts):
        log.warning(
            "Picsum batch incomplete: %d/%d images fetched — "
            "discarding partial results to maintain video synchronization.",
            len(paths), len(prompts),
        )
        return []

    log.info("Picsum batch: %d/%d images fetched successfully.", len(paths), len(prompts))
    return paths


# ---------------------------------------------------------------------------
# Pillow placeholder fallback
# ---------------------------------------------------------------------------

def _generate_placeholder_images(
    prompts: List[str],
    output_dir: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
    vcfg = None,
    log = logger,
) -> List[str]:
    """Create gradient placeholder images with prompt text overlay."""
    from PIL import Image, ImageDraw, ImageFont

    if vcfg is None:
        vcfg = config_loader.video()
    if width is None:
        width = vcfg.get("width", 1080)
    if height is None:
        height = vcfg.get("height", 1920)

    paths: List[str] = []
    for idx, prompt in enumerate(prompts):
        img  = Image.new("RGB", (width, height), color=(30, 30, 50))
        draw = ImageDraw.Draw(img)

        for y in range(height):
            r = int(30 + (y / height) * 50)
            g = int(30 + (y / height) * 30)
            b = int(50 + (y / height) * 60)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        except OSError:
            font = ImageFont.load_default()

        label = f"Scene {idx + 1}"
        bbox  = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((width - tw) // 2, (height - th) // 2 - 40), label, fill=(220, 220, 220), font=font)

        wrapped = textwrap.fill(prompt, width=40)
        draw.text(((width - 300) // 2, (height + th) // 2), wrapped, fill=(180, 180, 180), font=font)

        filename  = f"placeholder_{idx:03d}.png"
        file_path = os.path.join(output_dir, filename)
        img.save(file_path)
        paths.append(file_path)

    return paths

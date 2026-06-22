"""
Image Adapter — AI image generation & modification bridge.

Provider priority:
  0. Picsum (seeded)  — used only when `engine="picsum"` is explicitly requested
  1. Lingo_PERSONAS FootageGeneratorV2  — used for AI image generation when available
     (provider order: Cloudflare Workers AI → SiliconFlow → Pollinations → HuggingFace)
  2. Pillow placeholder fallback  — offline / testing
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from src.lingo_utils import ensure_lingo_on_path
from src import config_loader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_from_prompts(
    prompts: List[str],
    output_dir: str,
    style: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    engine: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> List[str]:
    """Generate one image per prompt and return a list of file paths.

    Provider priority: Picsum (seeded, only if ``engine="picsum"``) →
    FootageGeneratorV2 (Lingo) → Pillow placeholders.
    """
    cfg = config_loader.image()
    if style is None:
        style = cfg.get("style", "photorealistic")
    if aspect_ratio is None:
        aspect_ratio = cfg.get("aspect_ratio", "9:16")
    if engine is None:
        engine = cfg.get("engine")

    if width is None or height is None:
        vcfg = config_loader.video()
        base_w = vcfg.get("width", 1080)
        base_h = vcfg.get("height", 1920)
        _w, _h = _dimensions_for_aspect(aspect_ratio, base_w, base_h)
        if width is None:
            width = _w
        if height is None:
            height = _h

    os.makedirs(output_dir, exist_ok=True)

    # 1. Picsum — only when explicitly requested
    if engine == "picsum":
        stock_dir = os.path.join(output_dir, "stock")
        os.makedirs(stock_dir, exist_ok=True)
        paths = _picsum_batch(prompts, stock_dir, width, height)
        if paths:
            return paths
        logger.warning("Picsum failed or returned partial results — trying next provider.")

    # 2. FootageGeneratorV2 (Lingo)
    gen_dir = os.path.join(output_dir, "generated")
    os.makedirs(gen_dir, exist_ok=True)
    lingo_paths = _try_footage_generator(prompts, gen_dir, style, aspect_ratio, engine)
    if lingo_paths:
        return lingo_paths

    # 3. Pillow placeholders
    logger.warning("FootageGeneratorV2 unavailable — using Pillow placeholder images.")
    return _generate_placeholder_images(prompts, gen_dir, width=width, height=height)


def copy_provided_images(image_paths: List[str], output_dir: str) -> List[str]:
    """Validate and copy user-provided visual files into the workspace.

    Despite the name (kept for backward compatibility), this performs no
    image-specific validation — it works for any local file, including
    video clips used via ``VisualAssetType.MEDIA_SEQUENCE``. Prefer the
    ``copy_provided_media`` alias in new code for clarity.
    """
    import shutil
    cached_dir = os.path.join(output_dir, "cached")
    os.makedirs(cached_dir, exist_ok=True)
    copied: List[str] = []
    for src in image_paths:
        if not os.path.isfile(src):
            logger.warning("Visual asset not found, skipping: %s", src)
            continue
        dst = os.path.join(cached_dir, os.path.basename(src))
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


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
# Picsum seeded by prompt keywords
# ---------------------------------------------------------------------------

def _prompt_to_seed(prompt: str) -> str:
    """Extract the first few meaningful words from a prompt to use as a Picsum seed.

    Picsum's seed endpoint returns a consistent image for the same seed string,
    so different prompts get different images and reruns are deterministic.
    Example: 'A futuristic city skyline at night' → 'futuristic-city-skyline'
    """
    stopwords = {"a", "an", "the", "at", "in", "on", "of", "and", "with", "for", "to", "is"}
    words = re.sub(r"[^a-z0-9 ]", "", prompt.lower()).split()
    keywords = [w for w in words if w not in stopwords][:4]
    return "-".join(keywords) if keywords else "photo"


def _picsum_batch(
    prompts: List[str],
    output_dir: str,
    width: int,
    height: int,
) -> List[str]:
    """Fetch one Picsum image per prompt using a keyword-derived seed.

    URL format: https://picsum.photos/seed/{seed}/{width}/{height}.jpg
    Picsum returns a 302 redirect — must follow with allow_redirects=True.
    Same seed → same image every run. Different prompts → different seeds → different images.
    """
    import requests

    paths: List[str] = []
    timeout = 30

    for idx, prompt in enumerate(prompts):
        seed = _prompt_to_seed(prompt)
        url  = f"https://picsum.photos/seed/{seed}/{width}/{height}.jpg"
        logger.info("[%d/%d] Picsum seed='%s' — %s", idx + 1, len(prompts), seed, prompt[:60])

        try:
            response = requests.get(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 200:
                filename  = f"picsum_{idx:03d}_{seed}.jpg"
                file_path = os.path.join(output_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(response.content)
                paths.append(file_path)
                logger.info("  ✓ saved → %s", file_path)
            else:
                logger.warning("  HTTP %d for seed '%s'", response.status_code, seed)
        except Exception as exc:
            logger.warning("  failed for seed '%s': %s", seed, exc)

        if idx < len(prompts) - 1:
            time.sleep(0.5)

    if len(paths) < len(prompts):
        logger.warning(
            "Picsum batch incomplete: %d/%d images fetched — "
            "discarding partial results to maintain video synchronization.",
            len(paths), len(prompts),
        )
        return []  # Caller will fall through to next provider (e.g. AI generation)

    logger.info("Picsum batch: %d/%d images fetched successfully.", len(paths), len(prompts))
    return paths


# ---------------------------------------------------------------------------
# Lingo_PERSONAS FootageGeneratorV2 (secondary)
# ---------------------------------------------------------------------------

def _try_footage_generator(
    prompts: List[str],
    output_dir: str,
    style: str,
    aspect_ratio: str,
    engine: Optional[str] = None,
) -> Optional[List[str]]:
    """Attempt to use FootageGeneratorV2 from Lingo_PERSONAS.

    Returns None if Lingo is not installed. Re-raises runtime errors.
    Credentials for Cloudflare, SiliconFlow, and HuggingFace are read
    from environment variables automatically by FootageGeneratorV2.

    Imports footage_generator_v2 directly via importlib to avoid triggering
    shorts_creator/__init__.py, which has heavy optional dependencies
    (openai, json_repair, etc.) that are not required for image generation.
    """
    try:
        import importlib.util as _ilu
        ensure_lingo_on_path()
        # Resolve the module file directly to bypass shorts_creator/__init__.py
        import sys as _sys
        lingo_root = None
        for p in _sys.path:
            candidate = Path(p) / "shorts_creator" / "footage_generator_v2.py"
            if candidate.exists():
                lingo_root = p
                break
        if lingo_root is None:
            raise ImportError("footage_generator_v2.py not found on sys.path")
        spec = _ilu.spec_from_file_location(
            "shorts_creator.footage_generator_v2",
            str(Path(lingo_root) / "shorts_creator" / "footage_generator_v2.py"),
        )
        mod = _ilu.module_from_spec(spec)
        # Register parent package stub so relative imports inside the module work
        if "shorts_creator" not in _sys.modules:
            import types as _types
            pkg = _types.ModuleType("shorts_creator")
            pkg.__path__ = [str(Path(lingo_root) / "shorts_creator")]
            pkg.__package__ = "shorts_creator"
            _sys.modules["shorts_creator"] = pkg
        spec.loader.exec_module(mod)
        FootageGeneratorV2 = mod.FootageGeneratorV2  # type: ignore[attr-defined]
    except ImportError as exc:
        logger.warning("FootageGeneratorV2 not available (%s).", exc)
        return None

    try:
        gen = FootageGeneratorV2(
            output_dir=output_dir,
            cloudflare_account_id=os.environ.get('CLOUDFLARE_ACCOUNT_ID', ''),
            cloudflare_token=os.environ.get('CLOUDFLARE_API_TOKEN', ''),
            siliconflow_key=os.environ.get('SILICONFLOW_API_KEY', ''),
            huggingface_key=os.environ.get('HUGGINGFACE_API_KEY', ''),
            preferred_engine=engine,
        )
        paths = gen.generate_images_batch(prompts, style=style, aspect_ratio=aspect_ratio, delay=3.0)
        return paths if paths else None
    except Exception as exc:
        logger.error("FootageGeneratorV2 raised an unexpected error: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Pillow placeholder fallback
# ---------------------------------------------------------------------------

def _generate_placeholder_images(
    prompts: List[str],
    output_dir: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> List[str]:
    """Create gradient placeholder images with prompt text overlay."""
    from PIL import Image, ImageDraw, ImageFont

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

        snippet = prompt[:80] + ("…" if len(prompt) > 80 else "")
        try:
            small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except OSError:
            small = ImageFont.load_default()
        draw.text((60, (height // 2) + 40), snippet, fill=(160, 160, 180), font=small)

        path = os.path.join(output_dir, f"gen_img_{idx:03d}.png")
        img.save(path)
        paths.append(path)
        logger.info("Placeholder image → %s", path)

    return paths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dimensions_for_aspect(aspect_ratio: str, base_w: int, base_h: int) -> tuple:
    """Return (width, height) for the given aspect ratio string."""
    mapping = {
        "9:16":  (min(base_w, base_h), max(base_w, base_h)),
        "16:9":  (max(base_w, base_h), min(base_w, base_h)),
        "1:1":   (min(base_w, base_h), min(base_w, base_h)),
    }
    return mapping.get(aspect_ratio, (base_w, base_h))

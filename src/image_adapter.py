"""
Image Adapter — AI image generation & modification bridge.

Provider priority:
  1. Picsum (seed-based)  — free, no auth, deterministic per prompt keyword seed
  2. Lingo_PERSONAS FootageGeneratorV2  — used only if Picsum fails entirely
  3. Pillow placeholder fallback  — offline / testing
"""

import os
import re
import time
import logging
from typing import List, Optional
from urllib.parse import quote

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

    Provider priority: Picsum (seeded) → FootageGeneratorV2 → Pillow placeholders.
    """
    cfg = config_loader.image()
    if style is None:
        style = cfg.get("style", "photorealistic")
    if aspect_ratio is None:
        aspect_ratio = cfg.get("aspect_ratio", "9:16")

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

    # 1. Picsum seeded by prompt keywords
    if engine == "picsum" or (engine is None and cfg.get("use_picsum", True)):
        paths = _picsum_batch(prompts, output_dir, width, height)
        if paths:
            return paths
        logger.warning("Picsum failed or returned partial results — trying next provider.")
    else:
        logger.info("Picsum skipped due to engine='%s' or config.", engine)

    # 2. FootageGeneratorV2 (Lingo)
    lingo_paths = _try_footage_generator(prompts, output_dir, style, aspect_ratio, engine=engine)
    if lingo_paths:
        return lingo_paths

    # 3. Pillow placeholders
    logger.warning("FootageGeneratorV2 unavailable — using Pillow placeholder images.")
    return _generate_placeholder_images(prompts, output_dir, width=width, height=height)


def copy_provided_images(image_paths: List[str], output_dir: str) -> List[str]:
    """Validate and copy user-provided images into the workspace."""
    import shutil
    os.makedirs(output_dir, exist_ok=True)
    copied: List[str] = []
    for src in image_paths:
        if not os.path.isfile(src):
            logger.warning("Image not found, skipping: %s", src)
            continue
        dst = os.path.join(output_dir, os.path.basename(src))
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def modify_images(image_paths: List[str], instructions: str) -> List[str]:
    """Apply AI modifications to images (placeholder — returns originals).

    .. note::
        Real AI image editing (e.g. SDXL img2img) is planned for Phase 4.
    """
    # TODO: integrate an img2img provider here
    logger.warning(
        "modify_images: NOT YET IMPLEMENTED — image_modification_instructions ('%s') "
        "was set but no modifications were applied; originals returned unchanged.",
        instructions[:60],
    )
    return image_paths


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
            response = requests.get(url, timeout=timeout)
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
            "Picsum batch incomplete: %d/%d images fetched — discarding partial results.",
            len(paths), len(prompts),
        )
        return []  # Caller will fall through to next provider

    logger.info("Picsum batch: %d/%d images fetched.", len(paths), len(prompts))
    return paths


# ---------------------------------------------------------------------------
# Lingo_PERSONAS FootageGeneratorV2 (secondary)
# ---------------------------------------------------------------------------

def _try_footage_generator(
    prompts: List[str],
    output_dir: str,
    style: str,
    aspect_ratio: str,
) -> Optional[List[str]]:
    """Attempt to use FootageGeneratorV2 from Lingo_PERSONAS.

    Returns None if Lingo is not installed. Re-raises runtime errors.
    """
    try:
        ensure_lingo_on_path()
        from shorts_creator.footage_generator_v2 import FootageGeneratorV2  # type: ignore[import-untyped]
    except (ImportError, Exception) as exc:
        logger.warning("FootageGeneratorV2 not available (%s).", exc)
        return None

    try:
        gen   = FootageGeneratorV2(output_dir=output_dir)
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

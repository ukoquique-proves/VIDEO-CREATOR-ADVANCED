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
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

from src import config_loader
from src.image_providers.manager import ProviderManager

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
    Native ImageProviders → Pillow placeholders.
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

    # 2. Native Image Generation
    gen_dir = os.path.join(output_dir, "generated")
    os.makedirs(gen_dir, exist_ok=True)
    native_paths = _try_native_image_generation(prompts, gen_dir, style, width, height, engine)
    if native_paths:
        return native_paths

    # 3. Pillow placeholders
    logger.warning("Native image generation failed or unavailable — using Pillow placeholder images.")
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
) -> Optional[List[str]]:
    """Use the local ProviderManager to generate images with automatic failover."""
    manager = ProviderManager(output_dir=output_dir)
    
    # Configure providers from environment/config
    # 1. Cloudflare
    manager.add_cloudflare(
        account_id=os.environ.get('CLOUDFLARE_ACCOUNT_ID'),
        api_token=os.environ.get('CLOUDFLARE_API_TOKEN')
    )
    
    # 2. SiliconFlow
    manager.add_siliconflow(api_key=os.environ.get('SILICONFLOW_API_KEY'))
    
    # 3. Pollinations (free)
    manager.add_pollinations()
    
    # 4. HuggingFace
    manager.add_huggingface_flux(api_key=os.environ.get('HUGGINGFACE_API_KEY'))
    
    # 5. Picsum (last resort fallback)
    manager.add_picsum()
    
    # Reorder if an engine is preferred
    if preferred_engine:
        manager.providers.sort(key=lambda p: 0 if p.name == preferred_engine else 1)

    results = manager.generate_images_batch(prompts, width=width, height=height, style=style)
    
    # Return paths only if ALL prompts succeeded
    if all(r.success for r in results):
        return [r.image_path for r in results if r.image_path]
    
    logger.warning("Native image generation batch incomplete.")
    return None


# ---------------------------------------------------------------------------
# Picsum seeded by prompt keywords
# ---------------------------------------------------------------------------

def _prompt_to_seed(prompt: str) -> str:
    """Extract the first few meaningful words from a prompt to use as a Picsum seed."""
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
    """Fetch one Picsum image per prompt using a keyword-derived seed."""
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
        return []

    logger.info("Picsum batch: %d/%d images fetched successfully.", len(paths), len(prompts))
    return paths


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

        wrapped = textwrap.fill(prompt, width=40)
        draw.text(((width - 300) // 2, (height + th) // 2), wrapped, fill=(180, 180, 180), font=font)

        filename  = f"placeholder_{idx:03d}.png"
        file_path = os.path.join(output_dir, filename)
        img.save(file_path)
        paths.append(file_path)

    return paths

import textwrap

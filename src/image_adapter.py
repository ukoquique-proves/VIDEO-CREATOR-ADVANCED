"""
Image Adapter — AI image generation & modification bridge.

Supports:
  - Lingo_PERSONAS FootageGeneratorV2 (Pollinations / HuggingFace / Picsum)
  - Pillow placeholder fallback for offline / testing use
"""

import os
import logging
from typing import List, Optional

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

    Tries Lingo_PERSONAS FootageGeneratorV2 first; falls back to Pillow
    placeholders if the import or network call fails.

    Parameters
    ----------
    engine:
        Image engine override for this video (e.g. ``"pollinations"``).
        Takes precedence over the config default.
    style:
        Style preset override for this video. Takes precedence over config.
    """
    cfg = config_loader.image()
    if style is None:
        style = cfg.get("style", "photorealistic")
    if aspect_ratio is None:
        aspect_ratio = cfg.get("aspect_ratio", "9:16")
    # engine is passed through to _try_footage_generator; config default used there
    os.makedirs(output_dir, exist_ok=True)

    paths = _try_footage_generator(prompts, output_dir, style, aspect_ratio, engine=engine)
    if paths is not None:
        return paths

    logger.info("Using Pillow placeholder images (FootageGeneratorV2 unavailable).")
    return _generate_placeholder_images(prompts, output_dir, width=width, height=height)


def copy_provided_images(image_paths: List[str], output_dir: str) -> List[str]:
    """Validate and copy user-provided images into the workspace.

    Returns a list of absolute paths inside *output_dir*.
    """
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


def modify_images(
    image_paths: List[str],
    instructions: str,
) -> List[str]:
    """Apply AI modifications to images (placeholder — returns originals).

    .. note::
        Real AI image editing (e.g. SDXL img2img) is planned for Phase 4.
    """
    logger.info(
        "Image modification requested ('%s') — not yet implemented, returning originals.",
        instructions[:60],
    )
    # TODO: integrate an img2img provider here
    return image_paths


# ---------------------------------------------------------------------------
# Lingo_PERSONAS integration
# ---------------------------------------------------------------------------

def _try_footage_generator(
    prompts: List[str],
    output_dir: str,
    style: str,
    aspect_ratio: str,
    engine: Optional[str] = None,
) -> Optional[List[str]]:
    """Attempt to use FootageGeneratorV2 from Lingo_PERSONAS."""
    try:
        ensure_lingo_on_path()
        from shorts_creator.footage_generator_v2 import FootageGeneratorV2  # type: ignore[import-untyped]

        cfg = config_loader.image()

        gen = FootageGeneratorV2(output_dir=output_dir)
        paths = gen.generate_images_batch(
            prompts,
            style=style,
            aspect_ratio=aspect_ratio,
            delay=1.0,
        )
        if paths:
            return paths
        return None
    except Exception as exc:
        logger.warning("FootageGeneratorV2 unavailable (%s).", exc)
        return None


# ---------------------------------------------------------------------------
# Pillow fallback
# ---------------------------------------------------------------------------

def _generate_placeholder_images(
    prompts: List[str],
    output_dir: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> List[str]:
    """Create simple gradient placeholder images with prompt text."""
    from PIL import Image, ImageDraw, ImageFont

    vcfg = config_loader.video()
    if width is None:
        width = vcfg.get("width", 1080)
    if height is None:
        height = vcfg.get("height", 1920)

    paths: List[str] = []
    for idx, prompt in enumerate(prompts):
        img = Image.new("RGB", (width, height), color=(30, 30, 50))
        draw = ImageDraw.Draw(img)

        # Gradient background
        for y in range(height):
            r = int(30 + (y / height) * 50)
            g = int(30 + (y / height) * 30)
            b = int(50 + (y / height) * 60)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Text
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48,
            )
        except OSError:
            font = ImageFont.load_default()

        label = f"Scene {idx + 1}"
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((width - tw) // 2, (height - th) // 2 - 40),
            label,
            fill=(220, 220, 220),
            font=font,
        )

        # Prompt snippet
        snippet = prompt[:80] + ("…" if len(prompt) > 80 else "")
        try:
            small_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28,
            )
        except OSError:
            small_font = ImageFont.load_default()
        draw.text(
            (60, (height // 2) + 40),
            snippet,
            fill=(160, 160, 180),
            font=small_font,
        )

        path = os.path.join(output_dir, f"gen_img_{idx:03d}.png")
        img.save(path)
        paths.append(path)
        logger.info("Placeholder image → %s", path)

    return paths

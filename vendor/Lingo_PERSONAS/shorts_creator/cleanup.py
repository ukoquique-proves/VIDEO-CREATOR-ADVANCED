"""
Cleanup utility for Shorts Creator

Manages cleanup of temporary and old output files to prevent accumulation
of unused materials.
"""

import os
import shutil
import glob
from pathlib import Path
from typing import List, Optional


def cleanup_shorts_output(
    output_dir: str = 'output/shorts',
    keep_final_videos: int = 5,
    keep_scripts: int = 10,
    clean_generated: bool = True,
    clean_audio: bool = True,
    clean_placeholders: bool = True,
    dry_run: bool = False
) -> dict:
    """
    Clean up old shorts creator output files.
    
    Args:
        output_dir: Base output directory for shorts
        keep_final_videos: Number of most recent final videos to keep
        keep_scripts: Number of most recent scripts to keep
        clean_generated: Remove all generated AI images
        clean_audio: Remove all audio files
        clean_placeholders: Remove placeholder images
        dry_run: If True, only report what would be deleted without deleting
        
    Returns:
        Dict with cleanup statistics
    """
    stats = {
        'deleted_files': [],
        'kept_files': [],
        'errors': [],
        'space_freed_mb': 0
    }
    
    output_path = Path(output_dir)
    if not output_path.exists():
        return stats
    
    # Clean generated AI images
    if clean_generated:
        generated_dir = output_path / 'footage' / 'generated'
        if generated_dir.exists():
            _clean_directory(generated_dir, stats, dry_run)
    
    # Clean stock images (optional, usually keep these)
    # stock_dir = output_path / 'footage' / 'stock'
    
    # Clean placeholder images
    if clean_placeholders:
        for placeholder in (output_path / 'footage').glob('placeholder_*.png'):
            _delete_file(placeholder, stats, dry_run)
    
    # Clean audio files
    if clean_audio:
        audio_dir = output_path / 'audio'
        if audio_dir.exists():
            _clean_directory(audio_dir, stats, dry_run)
    
    # Clean old final videos (keep only N most recent)
    final_dir = output_path / 'final'
    if final_dir.exists():
        videos = sorted(
            final_dir.glob('*.mp4'),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for i, video in enumerate(videos):
            if i >= keep_final_videos:
                _delete_file(video, stats, dry_run)
            else:
                stats['kept_files'].append(str(video))
    
    # Clean old scripts (keep only N most recent)
    scripts_dir = output_path / 'scripts'
    if scripts_dir.exists():
        scripts = sorted(
            scripts_dir.glob('*.json'),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for i, script in enumerate(scripts):
            if i >= keep_scripts:
                _delete_file(script, stats, dry_run)
            else:
                stats['kept_files'].append(str(script))
    
    return stats


def _clean_directory(directory: Path, stats: dict, dry_run: bool):
    """Clean all files in a directory."""
    if not directory.exists():
        return
    
    for file_path in directory.iterdir():
        if file_path.is_file():
            _delete_file(file_path, stats, dry_run)


def _delete_file(file_path: Path, stats: dict, dry_run: bool):
    """Delete a single file and update stats."""
    try:
        if not dry_run:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            stats['space_freed_mb'] += size_mb
            file_path.unlink()
        else:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            stats['space_freed_mb'] += size_mb
        
        stats['deleted_files'].append(str(file_path))
    except Exception as e:
        stats['errors'].append(f"Failed to delete {file_path}: {e}")


def auto_cleanup_before_creation(output_dir: str = 'output/shorts', dry_run: bool = False) -> dict:
    """
    Automatic cleanup to run before creating a new video.
    Removes temporary files but keeps recent final videos.
    
    Args:
        output_dir: Base output directory
        dry_run: If True, only show what would be deleted
        
    Returns:
        Cleanup statistics
    """
    return cleanup_shorts_output(
        output_dir=output_dir,
        keep_final_videos=1,  # Keep only last video (most recent)
        keep_scripts=3,       # Keep last 3 scripts
        clean_generated=True, # Clean all AI generated images
        clean_audio=True,     # Clean all audio files
        clean_placeholders=True,
        dry_run=dry_run
    )


def aggressive_cleanup(output_dir: str = 'output/shorts', dry_run: bool = False) -> dict:
    """
    Aggressive cleanup for when disk space is low.
    Keeps only the most recent video and script.
    
    Args:
        output_dir: Base output directory
        dry_run: If True, only show what would be deleted
        
    Returns:
        Cleanup statistics
    """
    return cleanup_shorts_output(
        output_dir=output_dir,
        keep_final_videos=1,  # Keep only last video
        keep_scripts=3,       # Keep only last 3 scripts
        clean_generated=True,
        clean_audio=True,
        clean_placeholders=True,
        dry_run=dry_run
    )


def print_cleanup_report(stats: dict):
    """Print a formatted cleanup report."""
    print("\n" + "="*60)
    print("🧹 CLEANUP REPORT")
    print("="*60)
    
    print(f"\n📁 Files deleted: {len(stats['deleted_files'])}")
    if stats['deleted_files']:
        for f in stats['deleted_files'][:10]:  # Show first 10
            print(f"   - {os.path.basename(f)}")
        if len(stats['deleted_files']) > 10:
            print(f"   ... and {len(stats['deleted_files']) - 10} more")
    
    print(f"\n📁 Files kept: {len(stats['kept_files'])}")
    
    print(f"\n💾 Space freed: {stats['space_freed_mb']:.1f} MB")
    
    if stats['errors']:
        print(f"\n⚠️  Errors: {len(stats['errors'])}")
        for e in stats['errors'][:5]:
            print(f"   - {e}")
    
    print("="*60)


if __name__ == '__main__':
    # Test the cleanup
    print("Testing auto-cleanup (dry run)...")
    stats = auto_cleanup_before_creation(dry_run=True)
    print_cleanup_report(stats)
    
    print("\n\nTo actually clean up, run:")
    print("  from shorts_creator.cleanup import auto_cleanup_before_creation, print_cleanup_report")
    print("  stats = auto_cleanup_before_creation(dry_run=False)")
    print("  print_cleanup_report(stats)")

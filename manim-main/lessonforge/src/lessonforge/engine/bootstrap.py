"""Environment self-healing: locate ffmpeg / LaTeX / SoX and generate sound assets.
ensure_all() runs all steps once at package import (see app/__init__.py)."""
import os
import shutil
import subprocess
import logging

from .config import RENDER_DIR

logger = logging.getLogger(__name__)

def ensure_ffmpeg_on_path():
    if shutil.which("ffmpeg"):
        return
    logger.info("FFmpeg not found on PATH. Attempting self-healing discovery...")

    candidate_dirs = []
    # Windows: winget drops ffmpeg.exe somewhere under the packages tree.
    winget_packages = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.isdir(winget_packages):
        for root, _dirs, files in os.walk(winget_packages):
            if "ffmpeg.exe" in files:
                candidate_dirs.append(root)
                break
    # macOS (Homebrew) and Linux: well-known bin locations.
    candidate_dirs += ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/snap/bin"]

    for d in candidate_dirs:
        exe = os.path.join(d, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if os.path.exists(exe):
            logger.info(f"Self-healing: found FFmpeg at {d}")
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
            return

    logger.warning(
        "FFmpeg could not be located. Video rendering will fail until it is "
        "installed and on PATH (e.g. `apt install ffmpeg` / `brew install ffmpeg`)."
    )


def ensure_latex_on_path():
    if shutil.which("latex") and shutil.which("dvisvgm"):
        return
    logger.info("LaTeX or dvisvgm not found on PATH. Attempting self-healing discovery...")

    candidate_dirs = [
        # User local programs install (MiKTeX)
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin"),
        # System-wide programs install
        r"C:\Program Files\MiKTeX\miktex\bin\x64",
        r"C:\Program Files\MiKTeX\miktex\bin",
    ]
    # Scan for any texlive versions as well
    texlive_root = r"C:\texlive"
    if os.path.isdir(texlive_root):
        for year in os.listdir(texlive_root):
            p = os.path.join(texlive_root, year, "bin", "windows" if os.name == "nt" else "x86_64-linux")
            if os.path.isdir(p):
                candidate_dirs.append(p)

    for d in candidate_dirs:
        if os.path.isdir(d):
            exe = os.path.join(d, "latex.exe" if os.name == "nt" else "latex")
            if os.path.exists(exe):
                logger.info(f"Self-healing: found LaTeX at {d}")
                os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
                return

    logger.warning(
        "LaTeX could not be located on PATH. If installed, please add its bin folder to PATH."
    )


def ensure_sox_on_path():
    if shutil.which("sox"):
        return
    logger.info("SoX not found on PATH. Creating a dummy sox.bat to satisfy manim-voiceover checks...")
    try:
        dummy_sox_path = RENDER_DIR
        os.makedirs(dummy_sox_path, exist_ok=True)
        bat_file = os.path.join(dummy_sox_path, "sox.bat" if os.name == "nt" else "sox")
        with open(bat_file, "w") as f:
            if os.name == "nt":
                f.write("@echo off\necho Dummy SoX wrapper to satisfy manim-voiceover checks.\nexit /b 0\n")
            else:
                # The `sox` Python package parses `sox -h` for an "AUDIO FILE FORMATS:"
                # line at import and IndexErrors without one — so a stand-in that just
                # prints a greeting is WORSE than no sox at all (it turns a logged
                # warning into a crash of every render subprocess). Answer in SoX's shape.
                f.write('#!/bin/sh\n'
                        'case " $* " in\n'
                        '  *" -h "*) echo "SoX v14.4.2"; echo "AUDIO FILE FORMATS: wav mp3 ogg flac";;\n'
                        '  *) echo "1.0";;\n'
                        'esac\nexit 0\n')
        os.chmod(bat_file, 0o755)
        os.environ["PATH"] = dummy_sox_path + os.pathsep + os.environ["PATH"]
        
        # Monkeypatch subprocess.check_output on Windows to prevent WinError 2 
        # when manim_voiceover imports sox, since Windows doesn't resolve .bat 
        # inside subprocess without shell=True.
        import subprocess
        _original_check_output = subprocess.check_output
        def _mock_check_output(args, *pargs, **kwargs):
            if isinstance(args, list) and args and args[0] == 'sox':
                if '-h' in args:
                    return b'SoX v14.4.2\nAUDIO FILE FORMATS: wav mp3 ogg flac\n'
                else:
                    return b'1.0\n'
            return _original_check_output(args, *pargs, **kwargs)
        subprocess.check_output = _mock_check_output
        logger.info("Monkeypatched subprocess.check_output for 'sox'")
    except Exception as e:
        logger.warning(f"Failed to create dummy sox.bat: {e}")


def ensure_sound_assets():
    # (name, freq_hz, duration_ms) — pop.mp3 is short+snappy for bouncy elastic appearances
    for name, freq, dur in [("thud.mp3", 60, 500), ("whoosh.mp3", 300, 500), ("pop.mp3", 800, 120)]:
        for path in [os.path.join(RENDER_DIR, name)]:
            if not os.path.exists(path):
                try:
                    from pydub.generators import Sine
                    sound = Sine(freq).to_audio_segment(duration=dur, volume=-3.0).fade_out(min(60, dur // 2))
                    sound.export(path, format="mp3")
                    logger.info(f"Generated default sound asset: {path}")
                except Exception as e:
                    logger.warning(f"Could not generate default sound asset {path}: {e}")

def ensure_all():
    """Run every environment self-healing step once, in the original import-time order."""
    ensure_ffmpeg_on_path()
    ensure_latex_on_path()
    ensure_sox_on_path()
    ensure_sound_assets()

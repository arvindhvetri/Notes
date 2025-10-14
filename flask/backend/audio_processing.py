# audio_processing.py
import subprocess
import os
import re
import sys
import platform
import urllib.request
import zipfile
from pathlib import Path
import shutil

# This import is needed for the Windows installer to modify the user's PATH
if platform.system().lower() == "windows":
    import winreg

# --- FFmpeg INSTALLER FUNCTION ---
def install_ffmpeg(progress_queue):
    """
    Checks for a local FFmpeg installation. If not found, downloads and
    extracts it to a persistent folder for future use.
    """
    system = platform.system().lower()

    # First, check if ffmpeg is already in the system's PATH
    try:
        result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            progress_queue.put("✅ FFmpeg is already installed and in the system PATH.")
            return True
    except FileNotFoundError:
        pass # Not in PATH, so we'll check our local folder.

    if system == "windows":
        # ✅ CHANGED: Point to the 'ffmpeg_extracted' folder one level up in the project root.
        install_dir = Path("../ffmpeg_extracted")
        
        # --- CACHING LOGIC ---
        # 1. Check if the installation directory and the 'bin' folder already exist.
        try:
            existing_bin_dir = next(install_dir.glob("**/bin"))
            if existing_bin_dir.is_dir():
                os.environ["PATH"] = str(existing_bin_dir.resolve()) + os.pathsep + os.environ["PATH"]
                progress_queue.put("✅ Found and using existing local FFmpeg installation.")
                return True
        except StopIteration:
            # This means the directory or its 'bin' subfolder doesn't exist, so we proceed to download.
            progress_queue.put("🔧 Local FFmpeg not found. Starting first-time setup...")

        # --- DOWNLOAD LOGIC (runs only if the check above fails) ---
        zip_path = Path("ffmpeg.zip")
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        
        try:
            progress_queue.put(f"📥 Downloading FFmpeg for Windows...")
            urllib.request.urlretrieve(url, zip_path)
            
            # Extract to the persistent directory in the project root
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(install_dir)

            ffmpeg_bin_dir = next(install_dir.glob("**/bin"))
            
            os.environ["PATH"] = str(ffmpeg_bin_dir.resolve()) + os.pathsep + os.environ["PATH"]
            
            progress_queue.put("✅ FFmpeg downloaded. It's available for this and future sessions.")
            
            os.remove(zip_path)
            return True

        except Exception as e:
            if install_dir.exists():
                shutil.rmtree(install_dir)
            progress_queue.put(f"❌ ERROR: Failed to install FFmpeg on Windows: {e}")
            return False

    # For macOS and Linux, manual installation is more reliable
    elif system == "darwin": # macOS
        progress_queue.put("⚠️ On macOS, please install FFmpeg manually using Homebrew: 'brew install ffmpeg'")
        return False
    elif system == "linux":
        progress_queue.put("⚠️ On Linux, please install FFmpeg using your package manager, e.g., 'sudo apt install ffmpeg'")
        return False
    else:
        progress_queue.put(f"❌ Unsupported OS for automatic installation: {system}")
        return False

# --- MAIN CONVERSION FUNCTION (No changes needed below this line) ---
def run_audio_conversion(task_id, video_path, progress_queue):
    """
    Installs FFmpeg if needed, then converts video to audio.
    """
    if not install_ffmpeg(progress_queue):
        raise RuntimeError("FFmpeg is not installed. Please install it manually to proceed.")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_dir = Path('output') / task_id / 'Audio'
    os.makedirs(output_dir, exist_ok=True)
    output_audio_path = output_dir / f"{Path(video_path).stem}.mp3"

    cmd = [
        'ffmpeg', '-i', str(video_path), 
        '-vn', '-acodec', 'libmp3lame', '-b:a', '192k',
        '-y', str(output_audio_path)
    ]

    progress_queue.put(f"🎬 Converting '{os.path.basename(video_path)}' to audio...")
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    
    total_duration = None
    time_regex = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.\d{2}')

    for line in iter(process.stdout.readline, ''):
        if "Duration" in line and not total_duration:
            match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.\d{2}', line)
            if match:
                h, m, s = map(int, match.groups())
                total_duration = h * 3600 + m * 60 + s
        
        time_match = time_regex.search(line)
        if time_match and total_duration and total_duration > 0:
            h, m, s = map(int, time_match.groups())
            current_time = h * 3600 + m * 60 + s
            percent = min(100, int((current_time / total_duration) * 100))
            progress_queue.put(f"PROGRESS:{percent}")
            progress_queue.put(f"⏱️ Converting: {percent}%")
    
    process.wait()

    if process.returncode == 0 and os.path.exists(output_audio_path):
        progress_queue.put("✅ Success! Audio saved.")
        return str(output_audio_path)
    else:
        raise RuntimeError("FFmpeg conversion failed. Check console for errors.")
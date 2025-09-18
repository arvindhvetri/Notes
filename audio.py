import subprocess
import os
import sys
import platform
from pathlib import Path
import urllib.request
import zipfile
import winreg
import re

def install_ffmpeg(progress_queue):
    """
    Automatically installs FFmpeg on Windows, macOS, or Linux.
    Adds to PATH if necessary.
    """
    system = platform.system().lower()
    progress_queue.put(f"🔍 Detecting OS: {system}")

    try:
        result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            progress_queue.put("✅ FFmpeg is already installed.")
            return
    except FileNotFoundError:
        pass

    progress_queue.put("⏳ Installing FFmpeg...")

    if system == "windows":
        zip_path = "ffmpeg.zip"
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

        try:
            progress_queue.put("📥 Downloading FFmpeg...")
            urllib.request.urlretrieve(url, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall("ffmpeg")

            ffmpeg_dir = next(Path(".").glob("ffmpeg*/ffmpeg-master-latest-win64-gpl/bin"))
            ffmpeg_bin = ffmpeg_dir.resolve()

            os.environ["PATH"] = str(ffmpeg_bin) + os.pathsep + os.environ["PATH"]

            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
                current_path, _ = winreg.QueryValueEx(key, "Path")
                if str(ffmpeg_bin) not in current_path:
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, str(ffmpeg_bin) + os.pathsep + current_path)
                    progress_queue.put(f"📌 Added FFmpeg to user PATH: {ffmpeg_bin}")
                winreg.CloseKey(key)
            except Exception as e:
                progress_queue.put(f"⚠️ Could not modify registry PATH: {e} (but session PATH is set)")

            progress_queue.put("✅ FFmpeg installed and added to PATH (session).")
            os.remove(zip_path)

        except Exception as e:
            progress_queue.put(f"❌ Failed to install FFmpeg on Windows: {e}")
            sys.exit(1)

    elif system == "darwin":
        try:
            subprocess.run(["brew", "install", "ffmpeg"], check=True)
            progress_queue.put("✅ FFmpeg installed via Homebrew.")
        except FileNotFoundError:
            progress_queue.put("❌ Homebrew not found. Please install Homebrew first.")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            progress_queue.put(f"❌ Failed to install FFmpeg via brew: {e}")
            sys.exit(1)

    elif system == "linux":
        try:
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "ffmpeg"], check=True)
            progress_queue.put("✅ FFmpeg installed via apt.")
        except subprocess.CalledProcessError:
            try:
                subprocess.run(["sudo", "yum", "install", "-y", "ffmpeg"], check=True)
                progress_queue.put("✅ FFmpeg installed via yum.")
            except subprocess.CalledProcessError:
                try:
                    subprocess.run(["sudo", "dnf", "install", "-y", "ffmpeg"], check=True)
                    progress_queue.put("✅ FFmpeg installed via dnf.")
                except subprocess.CalledProcessError:
                    progress_queue.put("❌ Could not install FFmpeg.")
                    sys.exit(1)
    else:
        progress_queue.put(f"❌ Unsupported OS: {system}.")
        sys.exit(1)


def video_to_audio(video_path, output_audio_path=None, format='mp3', progress_queue=None):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if output_audio_path is None:
        base_name = os.path.splitext(video_path)[0]
        output_audio_path = f"{base_name}.{format}"

    cmd = ['ffmpeg', '-i', video_path, '-vn', '-y', output_audio_path]

    if format == 'mp3':
        cmd[4:4] = ['-acodec', 'libmp3lame', '-b:a', '192k']
    elif format == 'aac':
        cmd[4:4] = ['-acodec', 'copy']
    elif format == 'wav':
        cmd[4:4] = ['-acodec', 'pcm_s16le']
    else:
        cmd[4:4] = ['-acodec', 'copy']

    progress_queue.put(f"🎬 Converting '{os.path.basename(video_path)}' to audio...")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    total_duration = None
    time_regex = re.compile(r'time=(\d{2}):(\d{2}):(\d{2})\.\d{2}')

    while True:
        line = process.stdout.readline()
        if not line:
            break

        if "Duration" in line and total_duration is None:
            match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.\d{2}', line)
            if match:
                hours, minutes, seconds = map(int, match.groups())
                total_duration = hours * 3600 + minutes * 60 + seconds
        
        time_match = time_regex.search(line)
        if time_match and total_duration:
            hours, minutes, seconds = map(int, time_match.groups())
            current_time = hours * 3600 + minutes * 60 + seconds
            progress = int((current_time / total_duration) * 100)
            progress_queue.put(f"PROGRESS:{progress}")
            progress_queue.put(f"⏱️  Converting: {progress}%")

    process.wait()

    if process.returncode == 0:
        progress_queue.put(f"✅ Success! Audio saved.")
    else:
        progress_queue.put("❌ Error during conversion.")
        raise RuntimeError("FFmpeg conversion failed.")
    
def start_audio(video_path, progress_queue):
    SCRIPT_DIR = Path(__file__).parent.resolve()
    audio_output_dir = SCRIPT_DIR / "Output" / "Audio"
    audio_path = audio_output_dir / "videoplayback.mp3"

    os.makedirs(audio_output_dir, exist_ok=True)

    install_ffmpeg(progress_queue)
    video_to_audio(str(video_path), str(audio_path), progress_queue=progress_queue)
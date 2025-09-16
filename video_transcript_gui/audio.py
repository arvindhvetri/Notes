import subprocess
import os
import sys
import platform
from pathlib import Path

def install_ffmpeg():
    """
    Automatically installs FFmpeg on Windows, macOS, or Linux.
    Adds to PATH if necessary.
    """
    system = platform.system().lower()
    print(f"🔍 Detecting OS: {system}")

    # Check if ffmpeg is already installed
    try:
        result = subprocess.run(['ffmpeg', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            print("✅ FFmpeg is already installed.")
            return
    except FileNotFoundError:
        pass  # ffmpeg not found — proceed to install

    print("⏳ Installing FFmpeg...")

    if system == "windows":
        zip_path = "ffmpeg.zip"
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

        try:
            import urllib.request
            print("📥 Downloading FFmpeg...")
            urllib.request.urlretrieve(url, zip_path)

            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall("ffmpeg")

            ffmpeg_dir = next(Path(".").glob("ffmpeg*/ffmpeg-master-latest-win64-gpl/bin"))
            ffmpeg_bin = ffmpeg_dir.resolve()

            os.environ["PATH"] = str(ffmpeg_bin) + os.pathsep + os.environ["PATH"]

            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
                current_path, _ = winreg.QueryValueEx(key, "Path")
                if str(ffmpeg_bin) not in current_path:
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, str(ffmpeg_bin) + os.pathsep + current_path)
                    print(f"📌 Added FFmpeg to user PATH: {ffmpeg_bin}")
                winreg.CloseKey(key)
            except Exception as e:
                print(f"⚠️ Could not modify registry PATH: {e} (but session PATH is set)")

            print("✅ FFmpeg installed and added to PATH (session).")
            os.remove(zip_path)

        except Exception as e:
            print(f"❌ Failed to install FFmpeg on Windows: {e}")
            sys.exit(1)

    elif system == "darwin":  # macOS
        try:
            subprocess.run(["brew", "install", "ffmpeg"], check=True)
            print("✅ FFmpeg installed via Homebrew.")
        except FileNotFoundError:
            print("❌ Homebrew not found. Please install Homebrew first: https://brew.sh/")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install FFmpeg via brew: {e}")
            sys.exit(1)

    elif system == "linux":
        try:
            subprocess.run(["sudo", "apt-get", "update"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "ffmpeg"], check=True)
            print("✅ FFmpeg installed via apt.")
        except subprocess.CalledProcessError:
            try:
                subprocess.run(["sudo", "yum", "install", "-y", "ffmpeg"], check=True)
                print("✅ FFmpeg installed via yum.")
            except subprocess.CalledProcessError:
                try:
                    subprocess.run(["sudo", "dnf", "install", "-y", "ffmpeg"], check=True)
                    print("✅ FFmpeg installed via dnf.")
                except subprocess.CalledProcessError:
                    print("❌ Could not install FFmpeg via apt/yum/dnf. Try manually: https://ffmpeg.org/download.html")
                    sys.exit(1)
    else:
        print(f"❌ Unsupported OS: {system}. Please install FFmpeg manually: https://ffmpeg.org/download.html")
        sys.exit(1)


def video_to_audio(video_path, output_audio_path=None, format='mp3'):
    """
    Convert video file to audio using FFmpeg (fast, no re-encoding if possible)
    Works perfectly for 1hr+ files.

    :param video_path: Path to input video file
    :param output_audio_path: Optional output path. If None, uses video name + .mp3
    :param format: Output format ('mp3', 'aac', 'wav', etc.)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if output_audio_path is None:
        base_name = os.path.splitext(video_path)[0]
        output_audio_path = f"{base_name}.{format}"

    # Build FFmpeg command
    cmd = ['ffmpeg', '-i', video_path, '-vn', '-y', output_audio_path]

    if format == 'mp3':
        # For MP3: Must re-encode AAC → MP3
        cmd[4:4] = ['-acodec', 'libmp3lame', '-b:a', '192k']  # Insert after -i
    elif format == 'aac':
        # For AAC: Can copy if source is AAC
        cmd[4:4] = ['-acodec', 'copy']
    elif format == 'wav':
        # For WAV: Copy or decode to PCM
        cmd[4:4] = ['-acodec', 'pcm_s16le']  # Standard 16-bit PCM
    else:
        # Default: try to copy if possible, else default to mp3
        cmd[4:4] = ['-acodec', 'copy']

    #progress bar   
    cmd.extend(['-progress', 'pipe:1', '-loglevel', 'info'])
    print(f"🎬 Converting '{video_path}' to '{output_audio_path}'...")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    if result.returncode == 0:
        print(f"✅ Success! Audio saved to: {output_audio_path}")
    else:
        print("❌ Error during conversion:")
        print(result.stdout)
        raise RuntimeError("FFmpeg conversion failed.")


if __name__ == "__main__":
    print("🚀 Starting automated video-to-audio converter...\n")

    # Step 1: Install FFmpeg automatically (if needed)
    install_ffmpeg()

    # Step 2: Use YOUR video file — located at ../Video/videoplayback.mp4
    your_video_path = "./Video/videoplayback.mp4"

    print(f"📁 Using video file: {your_video_path}")

    # Validate the file exists
    if not os.path.exists(your_video_path):
        print(f"❌ ERROR: Video file not found at:\n{os.path.abspath(your_video_path)}")
        print("Please ensure the file exists at: ../Video/videoplayback.mp4")
        sys.exit(1)

    # Step 3: Convert to audio
    audio_file = "videoplayback.mp3"
    video_to_audio(your_video_path, audio_file)

    print("\n🎉 All done! Your audio file is ready.")
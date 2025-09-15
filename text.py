import os
import subprocess
import concurrent.futures
import tempfile
from pathlib import Path
import whisper
import sys

# CONFIGURATION
SCRIPT_DIR = Path(__file__).parent.resolve()
AUDIO_FILE = SCRIPT_DIR/"videoplayback.mp3"          # Your input file
OUTPUT_FILE = SCRIPT_DIR/"transcript.txt"           # Final output
CHUNK_DURATION = 600                     # 10 minutes in seconds
MODEL_SIZE = "tiny"                      # Fastest accurate model
NUM_WORKERS = os.cpu_count()             # Use all CPU cores


def get_audio_duration(audio_path):
    """Return total duration of audio file in seconds."""
    result = subprocess.run([
        'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
        '-of', 'csv=p=0', audio_path
    ], capture_output=True, text=True)
    return float(result.stdout.strip())


def split_audio_into_chunks(audio_path, chunk_duration=600):
    """Split audio into chunks of chunk_duration seconds. Returns list of chunk filenames."""
    print(f"✂️  Splitting '{audio_path}' into {chunk_duration}-second chunks...")

    total_duration = get_audio_duration(audio_path)
    num_chunks = int(total_duration // chunk_duration) + 1

    chunks = []
    base_name = os.path.splitext(audio_path)[0]

    for i in range(num_chunks):
        start_time = i * chunk_duration
        chunk_name = f"{base_name}_chunk_{i:03d}.mp3"
        chunks.append(chunk_name)

        if os.path.exists(chunk_name):
            print(f"⏭️  Chunk {i} already exists: {chunk_name}")
            continue

        cmd = [
            'ffmpeg',
            '-i', audio_path,
            '-ss', str(start_time),
            '-t', str(chunk_duration),
            '-acodec', 'mp3',
            '-ar', '16000',
            '-ac', '1',
            '-y',
            chunk_name
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"📦 Created: {chunk_name}")

    return chunks


def transcribe_chunk(chunk_path):
    """Transcribe a single audio chunk using tiny model."""
    try:
        model = whisper.load_model(MODEL_SIZE)
        result = model.transcribe(
            chunk_path,
            language=None,
            fp16=False,
            verbose=False,
            temperature=0.0,
            condition_on_previous_text=False
        )
        return result["text"].strip()
    except Exception as e:
        return f"[ERROR transcribing {chunk_path}: {str(e)}]"


def transcribe_single_file(audio_path):
    """Transcribe entire file without splitting."""
    print(f"🎙️  Transcribing entire file '{audio_path}' (single pass)...")
    model = whisper.load_model(MODEL_SIZE)
    result = model.transcribe(
        audio_path,
        language=None,
        fp16=False,
        verbose=True,
        temperature=0.0,
        condition_on_previous_text=False
    )
    return result["text"].strip()


def merge_transcriptions(transcriptions, output_file):
    """Write all transcriptions to final file."""
    print(f"📝 Merging results into '{output_file}'...")
    with open(output_file, 'w', encoding='utf-8') as f:
        for text in transcriptions:
            f.write(text + "\n\n")


if __name__ == "__main__":
    print("🚀 Starting smart audio-to-text transcription...\n")

    if not os.path.exists(AUDIO_FILE):
        print(f"❌ ERROR: Audio file not found: {AUDIO_FILE}")
        sys.exit(1)

    duration = get_audio_duration(AUDIO_FILE)
    print(f"⏱️  Audio duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")

    if duration < CHUNK_DURATION:
        print("🎯 File is under 10 minutes → Transcribing as single unit (fastest mode)")
        text = transcribe_single_file(AUDIO_FILE)
        merge_transcriptions([text], OUTPUT_FILE)
    else:
        print(f"📊 File is over 10 minutes → Splitting into {int(duration // CHUNK_DURATION) + 1} chunks and transcribing in parallel")
        chunks = split_audio_into_chunks(AUDIO_FILE, CHUNK_DURATION)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(transcribe_chunk, chunk) for chunk in chunks]
            results = [future.result() for future in futures]

        merge_transcriptions(results, OUTPUT_FILE)

        # Clean up chunks
        print("🧹 Cleaning up temporary chunks...")
        for chunk in chunks:
            if os.path.exists(chunk):
                os.remove(chunk)
                print(f"🗑️  Deleted: {chunk}")

    print(f"\n🎉 All done! Transcript saved to: {OUTPUT_FILE}")
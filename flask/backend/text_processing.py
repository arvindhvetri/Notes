# text_processing.py
import os
import subprocess
import concurrent.futures
from pathlib import Path
import whisper

# --- CONFIGURATION ---
CHUNK_DURATION = 600        # 10 minutes in seconds
MODEL_SIZE = "tiny"         # Fast and lightweight
NUM_WORKERS = os.cpu_count() or 1  # Fallback if cpu_count() returns None

# --- LAZY LOADING: Load model once ---
_transcriber_model = None

def get_transcriber():
    """Load Whisper model once and reuse it (critical for performance in Flask)."""
    global _transcriber_model
    if _transcriber_model is None:
        print(f"🧠 Loading Whisper '{MODEL_SIZE}' model...")
        _transcriber_model = whisper.load_model(MODEL_SIZE)
        print("✅ Transcription model ready.")
    return _transcriber_model

# --- HELPER FUNCTIONS ---
def get_audio_duration(audio_path):
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run([
        'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
        '-of', 'csv=p=0', str(audio_path)
    ], capture_output=True, text=True)
    return float(result.stdout.strip())

def split_audio_into_chunks(audio_path, chunk_duration):
    """Split audio into normalized chunks for reliable transcription."""
    total_duration = get_audio_duration(audio_path)
    num_chunks = int(total_duration // chunk_duration) + 1
    chunks = []
    
    audio_dir = Path(audio_path).parent
    base_name = Path(audio_path).stem

    for i in range(num_chunks):
        start_time = i * chunk_duration
        chunk_path = audio_dir / f"{base_name}_chunk_{i:03d}.mp3"
        chunk_path_str = str(chunk_path)
        chunks.append(chunk_path_str)

        if os.path.exists(chunk_path_str):
            continue

        # Apply loudnorm + standardize for Whisper
        cmd = [
            'ffmpeg',
            '-i', str(audio_path),
            '-ss', str(start_time),
            '-t', str(chunk_duration),
            '-vn',                  # No video
            '-ar', '16000',         # Whisper sample rate
            '-ac', '1',             # Mono
            '-c:a', 'libmp3lame',   # MP3 codec
            '-af', 'loudnorm',      # Normalize loudness (your fix ✅)
            '-y',
            chunk_path_str
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return chunks

# --- TRANSCRIPTION FUNCTIONS ---
def transcribe_chunk(chunk_path):
    """Transcribe a single chunk using the shared model."""
    try:
        model = get_transcriber()
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
        return f"[ERROR transcribing {Path(chunk_path).name}: {e}]"

def transcribe_single_file(audio_path):
    """Transcribe short file in one go."""
    model = get_transcriber()
    result = model.transcribe(
        audio_path,
        language=None,
        fp16=False,
        verbose=True,
        temperature=0.0,
        condition_on_previous_text=False
    )
    return result["text"].strip()

# --- MAIN FLASK ENTRY POINT ---
def run_transcription(task_id, audio_file_path, progress_queue):
    """
    Flask-compatible transcription orchestrator.
    - task_id: unique ID for this job (e.g., UUID)
    - audio_file_path: full path to input audio
    - progress_queue: queue.Queue() or similar for progress updates
    """
    # Ensure output dir exists
    output_dir = Path('output') / task_id / 'Transcript'
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / 'transcript.txt'

    # Get duration
    duration = get_audio_duration(audio_file_path)
    chunks_to_delete = []

    if duration < CHUNK_DURATION:
        progress_queue.put("🎤 File is short, transcribing as a single unit...")
        final_content = transcribe_single_file(audio_file_path)
    else:
        num_chunks_total = int(duration // CHUNK_DURATION) + 1
        progress_queue.put(f"📊 Splitting into {num_chunks_total} chunks for parallel processing...")

        chunks = split_audio_into_chunks(audio_file_path, CHUNK_DURATION)
        chunks_to_delete = chunks

        # Parallel transcription
        results = [""] * len(chunks)
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            future_to_index = {
                executor.submit(transcribe_chunk, chunk): i 
                for i, chunk in enumerate(chunks)
            }

            completed = 0
            for future in concurrent.futures.as_completed(future_to_index):
                idx = future_to_index[future]
                results[idx] = future.result()
                completed += 1

                progress = int((completed / len(chunks)) * 100)
                progress_queue.put(f"PROGRESS:{progress}")
                progress_queue.put(f"🎙️ Transcribed chunk {completed}/{len(chunks)}.")

        final_content = "\n\n".join(results)

    # Save final transcript
    with open(transcript_path, 'w', encoding='utf-8') as f:
        f.write(final_content)

    # Cleanup
    if chunks_to_delete:
        progress_queue.put("🧹 Cleaning up temporary audio chunks...")
        for chunk in chunks_to_delete:
            try:
                os.remove(chunk)
            except OSError:
                pass  # Ignore if already gone

    progress_queue.put(f"✅ Transcription saved to: {transcript_path}")
    return str(transcript_path)
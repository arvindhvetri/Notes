# text.py
import os
import subprocess
import concurrent.futures
import tempfile
from pathlib import Path
import whisper
import sys
import queue

# CONFIGURATION
SCRIPT_DIR = Path(__file__).parent.resolve()
AUDIO_FILE = SCRIPT_DIR/"Output"/"Audio"/"videoplayback.mp3"          # Your input file

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
    
    total_duration = get_audio_duration(audio_path)
    num_chunks = int(total_duration // chunk_duration) + 1

    chunks = []
    base_name = os.path.splitext(audio_path)[0]

    for i in range(num_chunks):
        start_time = i * chunk_duration
        chunk_name = f"{base_name}_chunk_{i:03d}.mp3"
        chunks.append(chunk_name)

        if os.path.exists(chunk_name):
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

    return chunks


def transcribe_chunk(chunk_path, progress_queue):
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
        progress_queue.put(f"[ERROR transcribing {chunk_path}: {str(e)}]")
        return f"[ERROR transcribing {chunk_path}: {str(e)}]"


def transcribe_single_file(audio_path, progress_queue):
    """Transcribe entire file without splitting."""
    progress_queue.put("🎙️  Transcribing entire file... (single pass)")
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


def start_text(progress_queue):
    if not os.path.exists(AUDIO_FILE):
        progress_queue.put("❌ ERROR: Audio file not found!")
        sys.exit(1)

    duration = get_audio_duration(AUDIO_FILE)
    if duration < CHUNK_DURATION:
        progress_queue.put("🎯 File is under 10 minutes. Transcribing as single unit.")
        transcription = transcribe_single_file(AUDIO_FILE, progress_queue)
        final_content = transcription
    else:
        progress_queue.put(f"📊 File is over 10 minutes. Splitting into {int(duration // CHUNK_DURATION) + 1} chunks and transcribing in parallel.")
        chunks = split_audio_into_chunks(AUDIO_FILE, CHUNK_DURATION)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = {executor.submit(transcribe_chunk, chunk, progress_queue): chunk for chunk in chunks}
            
            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                completed_count += 1
                progress = int((completed_count / len(chunks)) * 100)
                progress_queue.put(f"PROGRESS:{progress}")
                progress_queue.put(f"🎙️  Completed transcription for chunk {completed_count}/{len(chunks)}.")
                
            results = [f.result() for f in futures]
            final_content = "\n\n".join(results)

        progress_queue.put("🧹 Cleaning up temporary chunks...")
        for chunk in chunks:
            if os.path.exists(chunk):
                os.remove(chunk)
                progress_queue.put(f"🗑️  Deleted: {os.path.basename(chunk)}")
    
    # Send the final content back to the frontend
    progress_queue.put(f"FINAL_CONTENT:{final_content}")

def save_final_transcript(content, filename):
    """Saves the transcribed content to a file with the provided filename."""
    SCRIPT_DIR = Path(__file__).parent.resolve()
    output_dir = SCRIPT_DIR/"Output"/"Text"
    os.makedirs(output_dir, exist_ok=True)
    
    final_path = output_dir / filename
    
    with open(final_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    return str(final_path)
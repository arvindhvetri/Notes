# text.py
import os
import subprocess
import concurrent.futures
import tempfile
from pathlib import Path
import whisper
import sys

# CONFIGURATION — now accepts parameters
def transcribe_audio_file(
    audio_path,
    output_file=None,
    chunk_duration=600,
    model_size="tiny",
    num_workers=None
):
    """
    Transcribe audio file. Splits if > chunk_duration seconds.
    Returns path to transcript.
    """
    if output_file is None:
        output_file = os.path.splitext(audio_path)[0] + ".txt"

    if num_workers is None:
        num_workers = os.cpu_count() or 1

    def get_audio_duration(path):
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', path
        ], capture_output=True, text=True)
        return float(result.stdout.strip())

    def split_audio_into_chunks(path, duration):
        print(f"✂️  Splitting '{path}' into {duration}-second chunks...")
        total_duration = get_audio_duration(path)
        num_chunks = int(total_duration // duration) + 1
        chunks = []
        base_name = os.path.splitext(path)[0]

        for i in range(num_chunks):
            start_time = i * duration
            chunk_name = f"{base_name}_chunk_{i:03d}.mp3"
            chunks.append(chunk_name)

            if os.path.exists(chunk_name):
                print(f"⏭️  Chunk {i} already exists: {chunk_name}")
                continue

            cmd = [
                'ffmpeg',
                '-i', path,
                '-ss', str(start_time),
                '-t', str(duration),
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
        try:
            model = whisper.load_model(model_size)
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

    def transcribe_single(path):
        print(f"🎙️  Transcribing entire file '{path}'...")
        model = whisper.load_model(model_size)
        result = model.transcribe(
            path,
            language=None,
            fp16=False,
            verbose=False,
            temperature=0.0,
            condition_on_previous_text=False
        )
        return result["text"].strip()

    def merge_transcriptions(transcriptions, out_file):
        with open(out_file, 'w', encoding='utf-8') as f:
            for text in transcriptions:
                f.write(text + "\n\n")

    duration = get_audio_duration(audio_path)
    print(f"⏱️  Audio duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")

    if duration < chunk_duration:
        text = transcribe_single(audio_path)
        merge_transcriptions([text], output_file)
    else:
        chunks = split_audio_into_chunks(audio_path, chunk_duration)
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(transcribe_chunk, chunk) for chunk in chunks]
            results = [future.result() for future in futures]
        merge_transcriptions(results, output_file)
        for chunk in chunks:
            if os.path.exists(chunk):
                os.remove(chunk)
                print(f"🗑️  Deleted: {chunk}")

    print(f"🎉 Transcript saved to: {output_file}")
    return output_file
# app.py
import os
import queue
import threading
import time
from uuid import uuid4
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# Import your refactored processing modules
import audio_processing
import text_processing
import summary_processing
import notes_processing

# --- FLASK APP CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key' # Change this in production
app.config['UPLOADS_DIR'] = os.path.join(os.getcwd(), 'uploads')
app.config['OUTPUT_DIR'] = os.path.join(os.getcwd(), 'output')

# Ensure directories exist
os.makedirs(app.config['UPLOADS_DIR'], exist_ok=True)
os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)

# --- IN-MEMORY TASK MANAGEMENT ---
# In a real-world app, you'd use a more robust solution like Redis or Celery
tasks = {}

def update_task_status(task_id, message):
    """Helper to push messages to the task's queue."""
    if task_id in tasks:
        tasks[task_id]['queue'].put(message)

def run_pipeline(task_id, video_path):
    """
    The main processing pipeline that runs in a background thread.
    Each step calls the corresponding function from your refactored scripts.
    """
    try:
        # --- STAGE 1: Video to Audio ---
        update_task_status(task_id, "🚀 Starting Stage 1: Converting Video to Audio...")
        audio_file_path = audio_processing.run_audio_conversion(
            task_id, video_path, tasks[task_id]['queue']
        )
        if not audio_file_path:
            raise Exception("Audio conversion failed.")
        update_task_status(task_id, "✅ Stage 1 Complete: Audio file created.")
        time.sleep(1)

        # --- STAGE 2: Audio to Text ---
        update_task_status(task_id, "🚀 Starting Stage 2: Transcribing Audio to Text...")
        transcript_file_path = text_processing.run_transcription(
            task_id, audio_file_path, tasks[task_id]['queue']
        )
        if not transcript_file_path:
            raise Exception("Transcription failed.")
        update_task_status(task_id, "✅ Stage 2 Complete: Transcript created.")
        time.sleep(1)

        # --- STAGE 3: Text to Summary ---
        update_task_status(task_id, "🚀 Starting Stage 3: Summarizing Transcript...")
        summary_file_path = summary_processing.run_summarization(
            task_id, transcript_file_path, tasks[task_id]['queue']
        )
        if not summary_file_path:
            raise Exception("Summarization failed.")
        update_task_status(task_id, "✅ Stage 3 Complete: Summary created.")
        time.sleep(1)

        # --- STAGE 4: Summary to PDF Notes ---
        update_task_status(task_id, "🚀 Starting Stage 4: Generating PDF Notes...")
        pdf_file_path = notes_processing.run_notes_generation(
            task_id, summary_file_path, tasks[task_id]['queue']
        )
        if not pdf_file_path:
            raise Exception("PDF generation failed.")
        update_task_status(task_id, "✅ Stage 4 Complete: PDF notes generated.")
        
        # --- FINAL ---
        final_filename = os.path.basename(pdf_file_path)
        update_task_status(task_id, f"FINAL_PDF:{final_filename}")

    except Exception as e:
        # Report any errors back to the user
        error_message = f"❌ PIPELINE ERROR: {str(e)}"
        update_task_status(task_id, error_message)
    finally:
        # Mark the task as finished
        update_task_status(task_id, "TASK_COMPLETE")


# --- FLASK ROUTES ---
@app.route('/', methods=['GET'])
def index():
    """Render the main upload page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle video file uploads and start the background processing pipeline."""
    if 'videoFile' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['videoFile']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        video_path = os.path.join(app.config['UPLOADS_DIR'], filename)
        file.save(video_path)
        
        # Create a unique ID and a queue for this task
        task_id = str(uuid4())
        tasks[task_id] = {'queue': queue.Queue()}
        
        # Start the pipeline in a background thread
        thread = threading.Thread(target=run_pipeline, args=(task_id, video_path))
        thread.daemon = True
        thread.start()
        
        return jsonify({"task_id": task_id})

@app.route('/progress/<task_id>')
def progress(task_id):
    """Provide real-time progress updates for a given task."""
    if task_id not in tasks:
        return jsonify({"status": "error", "message": "Task not found."})
        
    try:
        # Get a message from the queue without blocking
        message = tasks[task_id]['queue'].get_nowait()
        return jsonify({"status": "running", "message": message})
    except queue.Empty:
        return jsonify({"status": "waiting"})

@app.route('/download/<path:filename>')
def download_file(filename):
    """Serve the final generated PDF file for download."""
    return send_from_directory(
        directory=os.path.join(app.config['OUTPUT_DIR'], 'Notes'), 
        path=filename, 
        as_attachment=True
    )

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
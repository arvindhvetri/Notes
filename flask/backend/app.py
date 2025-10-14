# backend/app.py
import os
import queue
import threading
import time
from uuid import uuid4
from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Processing modules
import audio_processing
import text_processing
import summary_processing
import notes_processing

# --- APP SETUP ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key'
app.config['UPLOADS_DIR'] = os.path.join(os.getcwd(), 'uploads')
app.config['OUTPUT_DIR'] = os.path.join(os.getcwd(), 'output')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app, supports_credentials=True, origins=["http://localhost:5173"])  # or your frontend URL

os.makedirs(app.config['UPLOADS_DIR'], exist_ok=True)
os.makedirs(app.config['OUTPUT_DIR'], exist_ok=True)

# --- DATABASE ---
db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

with app.app_context():
    db.create_all()

# --- LOGIN MANAGER ---
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- TASK STORAGE PER USER ---
user_tasks = {}  # { user_id: { task_id: { 'queue': Queue } } }

def get_user_tasks():
    uid = current_user.id
    if uid not in user_tasks:
        user_tasks[uid] = {}
    return user_tasks[uid]

def update_task_status(task_id, message):
    tasks = get_user_tasks()
    if task_id in tasks:
        tasks[task_id]['queue'].put(message)

# --- AUTH ROUTES ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User registered"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        login_user(user)
        return jsonify({"user_id": user.id, "username": user.username}), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out"}), 200

@app.route('/api/user', methods=['GET'])
def get_user():
    if current_user.is_authenticated:
        return jsonify({"user_id": current_user.id, "username": current_user.username})
    return jsonify({"user": None}), 200

# --- PROTECTED ROUTES ---
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    try:
        if 'videoFile' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['videoFile']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        filename = secure_filename(file.filename)
        user_upload_dir = os.path.join(app.config['UPLOADS_DIR'], str(current_user.id))
        os.makedirs(user_upload_dir, exist_ok=True)
        video_path = os.path.join(user_upload_dir, filename)
        file.save(video_path)

        task_id = str(uuid4())
        tasks = get_user_tasks()
        tasks[task_id] = {'queue': queue.Queue()}

        thread = threading.Thread(target=run_pipeline, args=(task_id, video_path))
        thread.daemon = True
        thread.start()

        return jsonify({"task_id": task_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Upload failed", "details": str(e)}), 500

@app.route('/progress/<task_id>')
@login_required
def progress(task_id):
    tasks = get_user_tasks()
    if task_id not in tasks:
        return jsonify({"status": "error", "message": "Task not found"}), 404
    try:
        message = tasks[task_id]['queue'].get_nowait()
        return jsonify({"status": "running", "message": message})
    except queue.Empty:
        return jsonify({"status": "waiting"})

@app.route('/download/<task_id>/<filename>')
@login_required
def download_file(task_id, filename):
    directory = os.path.join(app.config['OUTPUT_DIR'], str(current_user.id), task_id, 'Notes')
    if not os.path.isdir(directory):
        return jsonify({"error": "Output not found"}), 404
    return send_from_directory(directory=directory, path=filename, as_attachment=True)

# --- MAIN PAGE ---
@app.route('/')
def index():
    return render_template('index.html')

# --- PIPELINE ---
def run_pipeline(task_id, video_path):
    try:
        update_task_status(task_id, "🚀 Starting Stage 1: Converting Video to Audio...")
        audio_file_path = audio_processing.run_audio_conversion(task_id, video_path, get_user_tasks()[task_id]['queue'])
        if not audio_file_path:
            raise Exception("Audio conversion failed.")
        update_task_status(task_id, "✅ Stage 1 Complete")

        transcript_file_path = text_processing.run_transcription(task_id, audio_file_path, get_user_tasks()[task_id]['queue'])
        if not transcript_file_path:
            raise Exception("Transcription failed.")
        update_task_status(task_id, "✅ Stage 2 Complete")

        summary_file_path = summary_processing.run_summarization(task_id, transcript_file_path, get_user_tasks()[task_id]['queue'])
        if not summary_file_path:
            raise Exception("Summarization failed.")
        update_task_status(task_id, "✅ Stage 3 Complete")

        pdf_file_path = notes_processing.run_notes_generation(task_id, summary_file_path, get_user_tasks()[task_id]['queue'])
        if not pdf_file_path:
            raise Exception("PDF generation failed.")
        update_task_status(task_id, "✅ Stage 4 Complete")

        final_filename = os.path.basename(pdf_file_path)
        update_task_status(task_id, f"FINAL_PDF:{final_filename}")

    except Exception as e:
        update_task_status(task_id, f"❌ PIPELINE ERROR: {str(e)}")
    finally:
        update_task_status(task_id, "TASK_COMPLETE")

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
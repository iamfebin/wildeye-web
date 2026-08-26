from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
import subprocess
import os
import sys
import time
import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'wildeye_mqtt_launcher_secret')

active_processes = {}
DETECTION_SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "edge_node", "animal_using_video.py"))
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "media", "User_Uploaded_Analysis"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WildEye - AI Wildlife Detection & Analysis Center</title>
    <!-- Google Fonts: Inter -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Bootstrap Icons -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
    
    <style>
        :root {
            --bg-dark: #0f172a;
            --card-bg: #1e293b;
            --card-border: #334155;
            --accent-green: #10b981;
            --accent-blue: #0284c7;
            --accent-indigo: #6366f1;
            --text-primary: #f8fafc;
            --text-muted: #94a3b8;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            padding-bottom: 3rem;
        }

        .navbar-custom {
            background: rgba(30, 41, 59, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--card-border);
        }

        .main-container {
            max-width: 900px;
            margin-top: 2rem;
        }

        .glass-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 1rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }

        .card-header-custom {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-bottom: 1px solid var(--card-border);
            padding: 1.5rem;
        }

        .nav-tabs-custom {
            border-bottom: 1px solid var(--card-border);
            padding: 0 1rem;
            background: rgba(15, 23, 42, 0.4);
        }

        .nav-tabs-custom .nav-link {
            color: var(--text-muted);
            border: none;
            padding: 1rem 1.25rem;
            font-weight: 500;
            font-size: 0.95rem;
            transition: all 0.2s ease;
            border-bottom: 2px solid transparent;
        }

        .nav-tabs-custom .nav-link:hover {
            color: var(--text-primary);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .nav-tabs-custom .nav-link.active {
            color: var(--accent-blue);
            background: transparent;
            border-bottom: 2px solid var(--accent-blue);
        }

        .form-label {
            font-weight: 500;
            color: #cbd5e1;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
        }

        .form-control-custom, .form-select-custom {
            background-color: #0f172a;
            border: 1px solid var(--card-border);
            color: #f8fafc;
            border-radius: 0.5rem;
            padding: 0.75rem 1rem;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        .form-control-custom:focus, .form-select-custom:focus {
            background-color: #0f172a;
            border-color: var(--accent-blue);
            color: #ffffff;
            box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.25);
        }

        .btn-launch {
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            color: white;
            font-weight: 600;
            border: none;
            padding: 0.8rem 1.75rem;
            border-radius: 0.5rem;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        .btn-launch:hover {
            background: linear-gradient(135deg, #0369a1 0%, #075985 100%);
            color: white;
            transform: translateY(-1px);
            box-shadow: 0 10px 15px -3px rgba(2, 132, 199, 0.4);
        }

        .btn-launch-green {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        }
        .btn-launch-green:hover {
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.4);
        }

        .dropzone-container {
            border: 2px dashed var(--card-border);
            border-radius: 0.75rem;
            padding: 2.5rem 1.5rem;
            text-align: center;
            background: rgba(15, 23, 42, 0.5);
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .dropzone-container:hover, .dropzone-container.dragover {
            border-color: var(--accent-blue);
            background: rgba(2, 132, 199, 0.05);
        }

        .dropzone-icon {
            font-size: 2.5rem;
            color: var(--accent-blue);
            margin-bottom: 0.75rem;
        }

        .context-banner {
            background: rgba(2, 132, 199, 0.1);
            border: 1px solid rgba(2, 132, 199, 0.3);
            border-radius: 0.75rem;
            padding: 1rem 1.25rem;
            margin-bottom: 1.5rem;
        }

        .process-card {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--card-border);
            border-radius: 0.75rem;
            padding: 1rem 1.25rem;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .pulse-dot {
            width: 10px;
            height: 10px;
            background-color: var(--accent-green);
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse 1.6s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        .help-box {
            background: rgba(99, 102, 241, 0.08);
            border: 1px solid rgba(99, 102, 241, 0.2);
            border-radius: 0.75rem;
            padding: 1rem 1.25rem;
            font-size: 0.875rem;
            color: #cbd5e1;
        }

        .preview-img {
            max-height: 180px;
            border-radius: 0.5rem;
            border: 1px solid var(--card-border);
            object-fit: contain;
        }
    </style>
</head>
<body>

    <!-- Header Navigation -->
    <nav class="navbar navbar-custom sticky-top">
        <div class="container-fluid px-4">
            <a class="navbar-brand d-flex align-items-center text-white font-weight-bold" href="#">
                <i class="bi bi-eye-fill text-info me-2 fs-4"></i>
                <span>WildEye AI Detection Center</span>
            </a>
            <div class="d-flex align-items-center">
                <span class="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 px-3 py-2 rounded-pill me-3 d-none d-sm-inline-flex align-items-center">
                    <span class="pulse-dot me-2"></span>YOLOv8 Wildlife Engine Active
                </span>
                <a href="http://127.0.0.1:8000/forest_officer_home/" class="btn btn-outline-light btn-sm rounded-pill px-3">
                    <i class="bi bi-arrow-left me-1"></i> Dashboard
                </a>
            </div>
        </div>
    </nav>

    <div class="container main-container">

        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{% if category == 'error' %}danger{% elif category == 'success' %}success{% else %}info{% endif %} alert-dismissible fade show rounded-3 shadow-sm mb-4" role="alert">
                        <i class="bi {% if category == 'success' %}bi-check-circle-fill{% elif category == 'error' %}bi-exclamation-triangle-fill{% else %}bi-info-circle-fill{% endif %} me-2"></i>
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- Prefill Context Alert (if launched from Django) -->
        {% if prefill_camera_source or prefill_camera_id is not none %}
        <div class="context-banner d-flex align-items-center justify-content-between">
            <div class="d-flex align-items-center">
                {% if active_mode == 'image' %}
                    <i class="bi bi-file-earmark-image-fill text-info fs-3 me-3"></i>
                    <div>
                        <h6 class="mb-0 text-white fw-bold">Image Analysis Context Ready</h6>
                        <small class="text-muted">Analyzing target image: <code class="text-info">{{ prefill_camera_source }}</code></small>
                    </div>
                {% else %}
                    <i class="bi bi-camera-video-fill text-success fs-3 me-3"></i>
                    <div>
                        <h6 class="mb-0 text-white fw-bold">Camera Launch Context Ready</h6>
                        <small class="text-muted">Assigned Camera ID: <span class="badge bg-primary">#{{ prefill_camera_id }}</span></small>
                    </div>
                {% endif %}
            </div>
            <span class="badge bg-info bg-opacity-20 text-info px-3 py-2 rounded-pill">Pre-configured</span>
        </div>
        {% endif %}

        <!-- Main Launcher Card -->
        <div class="glass-card mb-4">
            <div class="card-header-custom">
                <h4 class="mb-1 text-white fw-bold"><i class="bi bi-play-circle-fill text-info me-2"></i>Detection Launcher</h4>
                <p class="text-muted mb-0 small">Select a detection source to start real-time YOLOv8 wildlife inference and event logging.</p>
            </div>

            <!-- Mode Navigation Tabs -->
            <ul class="nav nav-tabs nav-tabs-custom" id="detectionTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link {% if active_mode == 'live' %}active{% endif %}" id="webcam-tab" data-bs-toggle="tab" data-bs-target="#webcam-panel" type="button" role="tab">
                        <i class="bi bi-webcam-fill me-2"></i>Live Webcam
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link {% if active_mode == 'rtsp' %}active{% endif %}" id="rtsp-tab" data-bs-toggle="tab" data-bs-target="#rtsp-panel" type="button" role="tab">
                        <i class="bi bi-broadcast me-2"></i>IP Camera / RTSP Stream
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link {% if active_mode == 'image' %}active{% endif %}" id="image-tab" data-bs-toggle="tab" data-bs-target="#image-panel" type="button" role="tab">
                        <i class="bi bi-image-fill me-2"></i>Analyze Image File
                    </button>
                </li>
            </ul>

            <div class="tab-content p-4" id="detectionTabsContent">

                <!-- TAB 1: LIVE WEBCAM -->
                <div class="tab-pane fade {% if active_mode == 'live' %}show active{% endif %}" id="webcam-panel" role="tabpanel">
                    <form method="POST" action="{{ url_for('start_detection') }}">
                        <input type="hidden" name="mode" value="live">
                        
                        <div class="row g-3">
                            <div class="col-md-6">
                                <label for="webcam_select" class="form-label">
                                    <i class="bi bi-camera-video me-1"></i>Select Webcam Device
                                </label>
                                <select class="form-select form-select-custom" id="webcam_select" name="camera_source" onchange="document.getElementById('webcam_custom_input').value=this.value">
                                    <option value="0" {% if prefill_camera_source == '0' or not prefill_camera_source %}selected{% endif %}>Primary Webcam (Device #0)</option>
                                    <option value="1" {% if prefill_camera_source == '1' %}selected{% endif %}>Secondary Webcam (Device #1)</option>
                                    <option value="2" {% if prefill_camera_source == '2' %}selected{% endif %}>External Camera (Device #2)</option>
                                </select>
                                <input type="hidden" id="webcam_custom_input" value="{{ prefill_camera_source if prefill_camera_source else '0' }}">
                            </div>

                            <div class="col-md-6">
                                <label for="webcam_camera_id" class="form-label">
                                    <i class="bi bi-hash me-1"></i>Assigned Camera DB ID
                                    <i class="bi bi-question-circle text-muted ms-1" data-bs-toggle="tooltip" title="Database ID of the registered camera to log detections against. Use 0 for unassigned testing."></i>
                                </label>
                                <input type="number" class="form-control form-control-custom" id="webcam_camera_id" name="camera_id" 
                                       value="{{ prefill_camera_id if prefill_camera_id is not none else '1' }}" required min="0">
                            </div>
                        </div>

                        <div class="mt-4 text-end">
                            <button type="submit" class="btn btn-launch btn-launch-green">
                                <i class="bi bi-play-fill fs-5 me-1 align-middle"></i>Start Live Detection
                            </button>
                        </div>
                    </form>
                </div>

                <!-- TAB 2: RTSP STREAM / VIDEO FILE -->
                <div class="tab-pane fade {% if active_mode == 'rtsp' %}show active{% endif %}" id="rtsp-panel" role="tabpanel">
                    <form method="POST" action="{{ url_for('start_detection') }}">
                        <input type="hidden" name="mode" value="rtsp">
                        
                        <div class="row g-3">
                            <div class="col-md-8">
                                <label for="rtsp_source" class="form-label">
                                    <i class="bi bi-link-45deg me-1"></i>Stream URL or Local Video Path
                                </label>
                                <input type="text" class="form-control form-control-custom" id="rtsp_source" name="camera_source" 
                                       placeholder="e.g. rtsp://192.168.1.100:554/stream or C:/videos/sample.mp4" 
                                       value="{{ prefill_camera_source if active_mode == 'rtsp' else '' }}" required>
                                <div class="form-text text-muted small">Supports RTSP, HTTP live streams, or video files (.mp4, .avi).</div>
                            </div>

                            <div class="col-md-4">
                                <label for="rtsp_camera_id" class="form-label">
                                    <i class="bi bi-hash me-1"></i>Camera DB ID
                                </label>
                                <input type="number" class="form-control form-control-custom" id="rtsp_camera_id" name="camera_id" 
                                       value="{{ prefill_camera_id if prefill_camera_id is not none else '1' }}" required min="0">
                            </div>
                        </div>

                        <div class="mt-4 text-end">
                            <button type="submit" class="btn btn-launch">
                                <i class="bi bi-broadcast me-1 align-middle"></i>Connect & Start Stream
                            </button>
                        </div>
                    </form>
                </div>

                <!-- TAB 3: ANALYZE IMAGE FILE -->
                <div class="tab-pane fade {% if active_mode == 'image' %}show active{% endif %}" id="image-panel" role="tabpanel">
                    <form method="POST" action="{{ url_for('start_detection') }}" enctype="multipart/form-data">
                        <input type="hidden" name="mode" value="image">
                        <input type="hidden" name="camera_id" value="{{ prefill_camera_id if prefill_camera_id is not none else '0' }}">
                        
                        <!-- File Upload Dropzone -->
                        <div class="dropzone-container mb-3" id="dropzone" onclick="document.getElementById('image_file').click();">
                            <i class="bi bi-cloud-arrow-up-fill dropzone-icon"></i>
                            <h5 class="text-white fw-bold mb-1">Drag & Drop Image or Click to Browse</h5>
                            <p class="text-muted small mb-0">Supports JPG, PNG, WEBP, BMP formats for instant AI analysis</p>
                            <input type="file" id="image_file" name="image_file" accept="image/*" class="d-none" onchange="handleFileSelect(this)">
                        </div>

                        <div id="image_preview_box" class="text-center my-3 d-none">
                            <img id="preview_img" src="#" alt="Selected Image" class="preview-img mb-2">
                            <div id="file_name_display" class="text-info small font-monospace"></div>
                        </div>

                        <!-- Or Option for Existing Path -->
                        <div class="mb-3">
                            <label for="image_path_input" class="form-label">
                                <i class="bi bi-folder2-open me-1"></i>Or Enter Existing File Path on Server:
                            </label>
                            <input type="text" class="form-control form-control-custom" id="image_path_input" name="camera_source" 
                                   placeholder="e.g. C:/uploads/report_image.jpg" 
                                   value="{{ prefill_camera_source if prefill_camera_source else '' }}">
                        </div>

                        <div class="mt-4 text-end">
                            <button type="submit" class="btn btn-launch btn-launch-green">
                                <i class="bi bi-search me-1 align-middle"></i>Analyze Image with AI
                            </button>
                        </div>
                    </form>
                </div>

            </div>
        </div>

        <!-- Managed Processes List -->
        <div class="glass-card mb-4">
            <div class="card-header-custom d-flex align-items-center justify-content-between">
                <div>
                    <h5 class="mb-0 text-white fw-bold"><i class="bi bi-cpu-fill text-info me-2"></i>Active Detection Processes</h5>
                    <small class="text-muted">Real-time background detection workers managed by this system</small>
                </div>
                <button onclick="fetchProcessStatus()" class="btn btn-outline-secondary btn-sm rounded-pill">
                    <i class="bi bi-arrow-clockwise me-1"></i>Refresh
                </button>
            </div>

            <div class="p-4" id="processes_container">
                {% if active_processes %}
                    {% for cid, data in active_processes.items() %}
                        <div class="process-card">
                            <div class="d-flex align-items-center">
                                <span class="pulse-dot me-3"></span>
                                <div>
                                    <div class="text-white fw-bold">
                                        Camera ID #{{ cid }}
                                        <span class="badge bg-secondary bg-opacity-50 text-light ms-2 font-monospace">PID: {{ data.pid }}</span>
                                    </div>
                                    <small class="text-muted">Source: <code class="text-info">{{ data.source }}</code></small>
                                </div>
                            </div>
                            <div>
                                {% if data.status == 'running' %}
                                    <form method="POST" action="{{ url_for('stop_detection_process', camera_id_to_stop=cid) }}" class="d-inline">
                                        <button type="submit" class="btn btn-danger btn-sm rounded-pill px-3">
                                            <i class="bi bi-stop-fill me-1"></i>Stop Process
                                        </button>
                                    </form>
                                {% else %}
                                    <span class="badge bg-secondary rounded-pill px-3 py-2">Terminated</span>
                                {% endif %}
                            </div>
                        </div>
                    {% endfor %}
                {% else %}
                    <div class="text-center text-muted py-4">
                        <i class="bi bi-inbox fs-2 text-secondary d-block mb-2"></i>
                        No active detection processes currently running.
                    </div>
                {% endif %}
            </div>
        </div>

        <!-- Guidance Helper Box -->
        <div class="help-box d-flex align-items-start">
            <i class="bi bi-info-circle-fill fs-4 text-indigo me-3 mt-1"></i>
            <div>
                <strong class="text-white">How WildEye AI Detection Works:</strong>
                <ul class="mb-0 mt-1 ps-3 text-muted">
                    <li>Launching a process triggers the <strong>YOLOv8 Deep Learning Model</strong> configured for 45+ wildlife species.</li>
                    <li>A live visual feed window will open on the host machine with bounding boxes and confidence scores.</li>
                    <li>Any detected wildlife automatically logs an event to the <strong>WildEye MySQL Database</strong> and triggers real-time <strong>MQTT alerts</strong>.</li>
                </ul>
            </div>
        </div>

    </div>

    <!-- Bootstrap 5 Bundle JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Initialize tooltips
        document.addEventListener('DOMContentLoaded', function () {
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        });

        // Drag and Drop Image Handler
        const dropzone = document.getElementById('dropzone');
        if (dropzone) {
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropzone.addEventListener(eventName, preventDefaults, false);
            });

            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }

            ['dragenter', 'dragover'].forEach(eventName => {
                dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
            });

            ['dragleave', 'drop'].forEach(eventName => {
                dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
            });

            dropzone.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files.length > 0) {
                    document.getElementById('image_file').files = files;
                    handleFileSelect(document.getElementById('image_file'));
                }
            });
        }

        function handleFileSelect(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('preview_img').src = e.target.result;
                    document.getElementById('file_name_display').textContent = 'Selected: ' + input.files[0].name;
                    document.getElementById('image_preview_box').classList.remove('d-none');
                }
                reader.readAsDataURL(input.files[0]);
            }
        }

        // Live status polling
        function fetchProcessStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    console.log("Process status poll:", data);
                })
                .catch(err => console.error("Error polling process status:", err));
        }
        setInterval(fetchProcessStatus, 5000);
    </script>
</body>
</html>
"""

def refresh_process_statuses():
    for cam_id in list(active_processes.keys()):
        process_info = active_processes[cam_id]
        if process_info['status'] == 'running':
            if process_info['process'].poll() is not None:
                process_info['status'] = 'terminated'
                print(f"Process for camera ID {cam_id} (PID {process_info['pid']}) found terminated with code {process_info['process'].returncode}.")
                flash(f"Process for Camera ID #{cam_id} (PID {process_info['pid']}) has terminated.", "info")

@app.route('/', methods=['GET'])
def index():
    refresh_process_statuses()
    prefill_camera_id_str = request.args.get('camera_id_to_prefill')
    prefill_camera_source_val = request.args.get('camera_source_default', '')
    req_mode = request.args.get('mode', '')

    processed_prefill_camera_id = None
    if prefill_camera_id_str:
        try:
            processed_prefill_camera_id = int(prefill_camera_id_str)
        except ValueError:
            flash(f"Warning: Invalid prefill camera ID '{prefill_camera_id_str}' received.", "error")

    # Auto-detect mode if not explicitly passed
    active_mode = req_mode
    if not active_mode:
        if prefill_camera_source_val and any(prefill_camera_source_val.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff']):
            active_mode = 'image'
        elif prefill_camera_source_val.startswith('rtsp://') or prefill_camera_source_val.endswith('.mp4'):
            active_mode = 'rtsp'
        else:
            active_mode = 'live'

    return render_template_string(
        HTML_TEMPLATE,
        active_processes=active_processes,
        prefill_camera_id=processed_prefill_camera_id,
        prefill_camera_source=prefill_camera_source_val,
        active_mode=active_mode
    )

@app.route('/start', methods=['POST'])
def start_detection():
    camera_id_str = request.form.get('camera_id', '0')
    camera_source = request.form.get('camera_source', '')
    mode = request.form.get('mode', 'live')

    # Handle image file upload if uploaded
    if 'image_file' in request.files:
        file = request.files['image_file']
        if file and file.filename != '' and allowed_file(file.filename):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
            filename = secure_filename(timestamp + file.filename)
            saved_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(saved_path)
            camera_source = saved_path
            print(f"Saved uploaded image for analysis to: {saved_path}")

    if not camera_source:
        flash("Camera Source or Image File is required.", "error")
        return redirect(url_for('index'))

    try:
        camera_id = int(camera_id_str) if camera_id_str else 0
    except ValueError:
        flash("Camera ID must be an integer.", "error")
        return redirect(url_for('index'))

    refresh_process_statuses()
    if camera_id in active_processes and active_processes[camera_id]['status'] == 'running':
        flash(f"Detection process for Camera ID #{camera_id} is already running (PID: {active_processes[camera_id]['pid']}).", "error")
        return redirect(url_for('index'))

    if not os.path.exists(DETECTION_SCRIPT_PATH):
        errmsg = f"CRITICAL: Detection script not found at {DETECTION_SCRIPT_PATH}"
        print(errmsg)
        flash(errmsg, "error")
        return redirect(url_for('index'))

    cmd = [sys.executable, DETECTION_SCRIPT_PATH, '--camera-id', str(camera_id), '--camera-source', camera_source]
    try:
        print(f"Attempting to start process: {' '.join(cmd)}")
        process = subprocess.Popen(cmd)
        active_processes[camera_id] = {'process': process, 'pid': process.pid, 'source': camera_source, 'status': 'running'}
        msg = f"Started detection process for Camera ID #{camera_id} (PID: {process.pid}). Detection window will launch on the edge device/server."
        print(msg)
        flash(msg, "success")
    except Exception as e:
        errmsg = f"Failed to start detection process for Camera ID #{camera_id}: {e}"
        print(errmsg)
        flash(errmsg, "error")

    return redirect(url_for('index'))

@app.route('/stop/<int:camera_id_to_stop>', methods=['POST'])
def stop_detection_process(camera_id_to_stop):
    refresh_process_statuses()
    if camera_id_to_stop in active_processes and active_processes[camera_id_to_stop]['status'] == 'running':
        process_info = active_processes[camera_id_to_stop]
        print(f"Attempting to stop process for Camera ID {camera_id_to_stop} (PID {process_info['pid']})")
        try:
            process_info['process'].terminate()
            try:
                process_info['process'].wait(timeout=5)
                flash(f"Stopped process for Camera ID #{camera_id_to_stop} (PID: {process_info['pid']}).", "success")
            except subprocess.TimeoutExpired:
                process_info['process'].kill()
                flash(f"Force stopped process for Camera ID #{camera_id_to_stop} (PID: {process_info['pid']}).", "warning")
            process_info['status'] = 'terminated'
        except Exception as e:
            flash(f"Error stopping process for Camera ID #{camera_id_to_stop}: {e}", "error")
    elif camera_id_to_stop in active_processes and active_processes[camera_id_to_stop]['status'] == 'terminated':
        flash(f"Process for Camera ID #{camera_id_to_stop} was already terminated.", "info")
    else:
        flash(f"No active process found for Camera ID #{camera_id_to_stop}.", "error")
    return redirect(url_for('index'))

@app.route('/api/status', methods=['GET'])
def api_status():
    refresh_process_statuses()
    status_data = []
    for cid, data in active_processes.items():
        status_data.append({
            'camera_id': cid,
            'pid': data['pid'],
            'source': data['source'],
            'status': data['status']
        })
    return jsonify({'processes': status_data})

if __name__ == '__main__':
    if not os.path.exists(DETECTION_SCRIPT_PATH):
        print(f"CRITICAL ERROR: The detection script 'animal_using_video.py' not found at: {os.path.abspath(DETECTION_SCRIPT_PATH)}")
    else:
        print(f"Detection script expected at: {os.path.abspath(DETECTION_SCRIPT_PATH)}")

    flask_debug = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    flask_host = os.getenv('FLASK_HOST', '127.0.0.1')
    flask_port = int(os.getenv('FLASK_PORT', 5000))
    app.run(debug=flask_debug, host=flask_host, port=flask_port)
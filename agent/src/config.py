"""
config.py — Central configuration for the Security Camera app.
Edit these values to tune behavior without touching any other file.
"""

import os

# ─────────────────────────────────────────────
# CAMERA
# ─────────────────────────────────────────────
CAMERA_INDEX = 0            # 0 = default webcam; change to 1/2 for external cameras
FRAME_WIDTH  = 1280         # Capture resolution (pixels). Lower = faster but less detail.
FRAME_HEIGHT = 720
TARGET_FPS   = 30           # Desired capture FPS (webcam may cap at its own max)

# ─────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────
MODEL_NAME   = "yolov8n.pt"         # 'n'=nano (fastest). Options: n/s/m/l/x (nano→extra-large)
                                     # First run auto-downloads the weights into models/
MODELS_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
DEVICE       = "cuda"               # 'cuda' for NVIDIA GPU, 'cpu' for CPU-only
                                     # falls back to 'cpu' automatically if CUDA absent

# Inference input size — smaller = faster, larger = more accurate for small objects
INFERENCE_IMG_SIZE = 640            # YOLOv8 default; try 320 if you need more FPS

# Skip-frame optimisation: run detection only every Nth frame
# 1 = every frame (max accuracy), 2 = every other frame (huge FPS boost), etc.
FRAME_SKIP = 1

# ─────────────────────────────────────────────
# DETECTION
# ─────────────────────────────────────────────
PERSON_CLASS_ID    = 0              # COCO class 0 = "person"
CONFIDENCE_THRESH  = 0.45           # Minimum confidence to count as a detection (0–1)
IOU_THRESH         = 0.45           # Non-maximum suppression IoU threshold

# ─────────────────────────────────────────────
# EVENTS  (debounce / cooldown)
# ─────────────────────────────────────────────
# After a person event fires, wait this many seconds before firing again.
# Prevents log spam when a person stays in frame the whole time.
EVENT_COOLDOWN_SECONDS = 10.0

# ─────────────────────────────────────────────
# OUTPUTS
# ─────────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.dirname(__file__))  # project root
LOGS_DIR         = os.path.join(BASE_DIR, "logs")
SNAPSHOTS_DIR    = os.path.join(BASE_DIR, "outputs", "snapshots")
CLIPS_DIR        = os.path.join(BASE_DIR, "outputs", "clips")

SAVE_SNAPSHOTS   = True             # Save a JPEG image on each detection event
SAVE_CLIPS       = True             # Save a short video clip on each detection event
CLIP_DURATION_S  = 8                # How many seconds to record after detection
CLIP_CODEC       = "mp4v"           # FourCC codec for clip files (mp4v works everywhere)
CLIP_FPS         = 20               # FPS to encode clips at

LOG_FILENAME     = "detections.log" # Written into logs/

# ─────────────────────────────────────────────
# DISPLAY
# ─────────────────────────────────────────────
SHOW_FPS         = True             # Draw live FPS counter on the preview window
BOX_COLOR        = (0, 255, 0)      # BGR — green bounding boxes
BOX_THICKNESS    = 2
LABEL_COLOR      = (0, 255, 0)
FONT_SCALE       = 0.6
ALERT_COLOR      = (0, 0, 255)      # BGR — red "PERSON DETECTED" banner
WINDOW_TITLE     = "Security Camera — press Q to quit"

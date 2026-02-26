# 🔒 Security Camera — Person Detection App

A laptop-webcam security camera that detects humans in real time using **YOLOv8** and **OpenCV**, with snapshot + video-clip saving on detection.

---

## Folder Structure

```
Security Camera/
├── src/
│   ├── main.py            ← Entry point (run this)
│   ├── config.py          ← All tuneable settings
│   ├── detector.py        ← YOLOv8 person detection
│   ├── event_handler.py   ← Debounce / logging / snapshot / clip
│   └── display.py         ← Frame overlay drawing
├── models/                ← Auto-downloaded YOLOv8 weights
├── logs/
│   └── detections.log     ← ISO-timestamp event log
├── outputs/
│   ├── snapshots/         ← JPEG snapshots on detection
│   └── clips/             ← MP4 video clips on detection
└── requirements.txt
```

---

## Quick-Start (Windows + NVIDIA GPU)

### 1. Create a virtual environment (recommended)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install PyTorch with CUDA 12.1 support (RTX 3050 Ti)

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

> ⚠️ Do this **before** the next step — it pins the correct CUDA-enabled torch.

### 3. Install remaining dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run the app

```powershell
python src/main.py
```

On the **first run**, YOLOv8 will download the `yolov8n.pt` weights (~6 MB) automatically.

---

## Keyboard Controls (while the preview window is open)

| Key | Action |
|-----|--------|
| **Q** | Quit gracefully |
| **S** | Save manual snapshot right now |
| **SPACE** | Pause / Resume |
| **+** / **-** | Raise / lower confidence threshold by 5% |

---

## Configuration (`src/config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `CAMERA_INDEX` | `0` | Webcam index (try 1/2 for external cams) |
| `MODEL_NAME` | `yolov8n.pt` | Model size: n/s/m/l/x (nano→extra-large) |
| `DEVICE` | `cuda` | `'cuda'` or `'cpu'` |
| `CONFIDENCE_THRESH` | `0.45` | Min confidence to count as a person |
| `EVENT_COOLDOWN_SECONDS` | `10.0` | Seconds between repeated alerts |
| `CLIP_DURATION_S` | `8` | How long each clip records (seconds) |
| `FRAME_SKIP` | `1` | Run detection every Nth frame |
| `INFERENCE_IMG_SIZE` | `640` | YOLOv8 input size (try 320 for more FPS) |
| `SAVE_SNAPSHOTS` | `True` | Save JPEG on detection |
| `SAVE_CLIPS` | `True` | Save MP4 clip on detection |

---

## Performance Tips

| Tip | Effect |
|-----|--------|
| Use `yolov8n.pt` (nano) | Fastest model; still very accurate for persons |
| Set `FRAME_SKIP = 2` | Run detection every 2nd frame → ~2× FPS |
| Lower `INFERENCE_IMG_SIZE` to `320` | Faster inference, slightly less accuracy |
| Set `DEVICE = "cuda"` (RTX 3050 Ti) | 5–10× faster than CPU |
| Lower `FRAME_WIDTH/HEIGHT` to 640×480 | Less data per frame |

---

## Troubleshooting

### ❌ `Cannot open camera`
- Change `CAMERA_INDEX` in `config.py` to `1` or `2`.
- Close any other app using the webcam (Zoom, Teams, OBS).
- Check **Settings → Privacy → Camera** on Windows and allow access.

### ❌ `CUDA requested but not available`
The app falls back to CPU automatically. To fix:
```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```
Then verify: `python -c "import torch; print(torch.cuda.is_available())"` → should print `True`.

### ❌ Model download fails
Manually download `yolov8n.pt` from [Ultralytics releases](https://github.com/ultralytics/assets/releases) and place it in the `models/` folder.

### ❌ Very slow FPS on CPU
Set `FRAME_SKIP = 3`, lower `INFERENCE_IMG_SIZE` to `320`, and switch to `yolov8n.pt`.

### ❌ Clips have no sound / wrong format
The app records video only (no audio). Use `CLIP_CODEC = "XVID"` and `.avi` extension if `.mp4` doesn't play on your system.

---

## Log Format

Entries in `logs/detections.log` follow this pattern:
```
2026-02-26T18:50:00+0000  INFO  PERSON DETECTED | count=1 | confidences=[92%]
2026-02-26T18:50:00+0000  INFO  Snapshot saved → outputs/snapshots/snapshot_2026-02-26T18-50-00Z.jpg
2026-02-26T18:50:00+0000  INFO  Recording clip (8s) → outputs/clips/clip_2026-02-26T18-50-00Z.mp4
```

---

## Architecture

```
VideoCapture → PersonDetector (YOLOv8/CUDA)
                     ↓ detections
               EventHandler (debounce → log → snapshot → clip)
                     ↓ alert_active flag
               display helpers (boxes, banner, FPS, status dot)
                     ↓
               cv2.imshow (live preview window)
```

---

## Ethics & Privacy

- No face recognition or biometric identification.
- No network transmission — all data stays on your machine.
- App window is always visible — no stealth operation.
- Intended for personal, transparent, user-controlled use.

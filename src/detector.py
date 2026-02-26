"""
detector.py — Wraps YOLOv8 (Ultralytics) for person-only detection.

Responsibilities:
  1. Load the model once at startup (GPU/CPU auto-selected).
  2. Run inference on a single OpenCV frame.
  3. Return a clean list of Detection namedtuples (box, confidence).
"""

import os
from collections import namedtuple
from pathlib import Path

import torch
from ultralytics import YOLO

import sys
sys.path.insert(0, os.path.dirname(__file__))
import config

# A simple data container for each detected person in a frame.
Detection = namedtuple("Detection", ["x1", "y1", "x2", "y2", "confidence"])


class PersonDetector:
    """
    Loads a YOLOv8 model and exposes a single `detect(frame)` method.

    Parameters
    ----------
    model_name : str
        YOLOv8 weight filename, e.g. 'yolov8n.pt'. Downloaded automatically
        on first run and cached in the models/ directory.
    device : str
        'cuda' for GPU, 'cpu' for CPU. Automatically falls back to CPU if
        CUDA is unavailable.
    """

    def __init__(
        self,
        model_name: str = config.MODEL_NAME,
        device: str     = config.DEVICE,
    ):
        # ── Resolve model path ──────────────────────────────────────────────
        # Tell Ultralytics to store downloaded weights in our models/ folder
        # instead of the default ~/.ultralytics/ cache.
        models_dir = Path(config.MODELS_DIR)
        models_dir.mkdir(parents=True, exist_ok=True)
        model_path = models_dir / model_name

        # ── Pick device ─────────────────────────────────────────────────────
        if device == "cuda" and not torch.cuda.is_available():
            print("[WARN] CUDA requested but not available — falling back to CPU.")
            device = "cpu"
        self.device = device

        # ── Load model ──────────────────────────────────────────────────────
        # If weights exist locally, Ultralytics loads them directly.
        # Otherwise it downloads them from the official Ultralytics CDN.
        print(f"[INFO] Loading model '{model_name}' on device='{device}' …")
        self.model = YOLO(str(model_path) if model_path.exists() else model_name)
        self.model.to(device)

        # Cache the model to models/ so future runs are instant
        if not model_path.exists():
            self.model.save(str(model_path))
            print(f"[INFO] Model weights saved to {model_path}")

        print(f"[INFO] Model ready. Classes available: {len(self.model.names)}")

    # ────────────────────────────────────────────────────────────────────────
    def detect(self, frame) -> list[Detection]:
        """
        Run person detection on a single BGR frame (as returned by cv2.VideoCapture).

        Parameters
        ----------
        frame : np.ndarray
            An OpenCV BGR image (H x W x 3).

        Returns
        -------
        list[Detection]
            One entry per detected person; empty list if none found.
        """
        # Run YOLOv8 inference.
        # verbose=False suppresses per-frame console spam.
        results = self.model.predict(
            source    = frame,
            imgsz     = config.INFERENCE_IMG_SIZE,
            conf      = config.CONFIDENCE_THRESH,
            iou       = config.IOU_THRESH,
            classes   = [config.PERSON_CLASS_ID],   # Only detect "person"
            device    = self.device,
            verbose   = False,
        )

        detections: list[Detection] = []

        # results is a list with one element per image (we only pass one frame).
        r = results[0]

        if r.boxes is None:
            return detections

        for box in r.boxes:
            # box.xyxy[0] → tensor([x1, y1, x2, y2]) in pixel coordinates
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            detections.append(
                Detection(
                    x1=int(x1), y1=int(y1),
                    x2=int(x2), y2=int(y2),
                    confidence=conf,
                )
            )

        return detections

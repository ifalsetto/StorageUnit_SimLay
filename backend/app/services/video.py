from pathlib import Path


def extract_keyframes(video_path: Path, output_dir: Path, interval_seconds: float = 1.0, max_keyframes: int = 100) -> list[Path]:
    """Extract interval keyframes using OpenCV when installed.
    This is deterministic and cost-capped. Scene-based extraction can be added behind this interface.
    """
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Video keyframe extraction requires opencv-python-headless") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_interval = max(1, int(fps * interval_seconds))
    frames: list[Path] = []
    idx = 0
    saved = 0
    while saved < max_keyframes:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % frame_interval == 0:
            path = output_dir / f"keyframe_{saved+1:03d}.jpg"
            cv2.imwrite(str(path), frame)
            frames.append(path)
            saved += 1
        idx += 1
    cap.release()
    return frames

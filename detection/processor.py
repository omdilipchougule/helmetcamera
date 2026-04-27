"""
Video processor — tuned v2.
Changes from v1:
  - Model upgraded yolov8n -> yolov8s (better accuracy, auto-downloads ~22MB)
  - YOLO confidence default raised 0.40 -> 0.45 (fewer false positives)
  - Frame check rate doubled: every 3rd frame instead of every 5th
  - Evidence clip extended: 20s before + 20s after (was 15+15)
  - Minimum gap between saved clips raised: 25s (was 20s)
  - Progress bar updates every 15 frames (was 25) for smoother display
"""

import cv2, sys
from pathlib import Path
from datetime import datetime
from collections import deque
from ultralytics import YOLO
from detection.rules_engine import RulesEngine, Violation
from utils.logger import setup_logger

logger = setup_logger("processor")

RELEVANT = {
    0:"person", 1:"bicycle", 2:"car", 3:"motorcycle",
    5:"bus", 7:"truck", 9:"traffic light", 11:"stop sign",
}
COLORS = {
    "person":(0,200,255), "bicycle":(0,255,127), "car":(255,200,0),
    "motorcycle":(255,100,0), "bus":(200,0,255), "truck":(180,0,180),
    "traffic light":(0,255,0), "stop sign":(0,0,255),
}

EVIDENCE_DIR = Path("./evidence")
EVIDENCE_DIR.mkdir(exist_ok=True)

PRE_EVENT_SEC  = 20     # seconds of footage before violation (was 15)
POST_EVENT_SEC = 20     # seconds of footage after violation  (was 15)
FRAME_SKIP     = 3      # run YOLO every Nth frame            (was 5)
CLIP_GAP_SEC   = 25     # min seconds between saved clips     (was 20)


def _bar(cur, total, w=44, suffix=""):
    if total <= 0: return ""
    p = cur / total
    b = "=" * int(w*p) + "-" * (w - int(w*p))
    return f"\r  [{b}] {p:5.1%}  {cur}/{total}  {suffix}   "


class VideoProcessor:
    def __init__(self, confidence=0.45):          # raised default 0.40 -> 0.45
        self.conf  = confidence
        self.rules = RulesEngine()

        print("\n  Loading optimized NCNN model for Raspberry Pi...")
        self.model = YOLO("yolov8n_ncnn_model")   # Points to your converted folder
        print("  Model ready.\n")

    def process_video(self, path: str, show_preview=False) -> list:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            logger.error(f"Cannot open: {path}")
            logger.error("Try: ffmpeg -i input.webm output.mp4")
            return []

        fps   = cap.get(cv2.CAP_PROP_FPS) or 25
        W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"  File     : {Path(path).name}")
        print(f"  Size     : {W}x{H}  |  {fps:.1f} fps  |  {total/fps:.1f}s  ({total} frames)")
        print(f"  Checking : every {FRAME_SKIP} frames  |  conf threshold: {self.conf}")
        print(f"  Clips    : {PRE_EVENT_SEC}s before + {POST_EVENT_SEC}s after each violation")
        print(f"  Preview  : {'ON — press Q to skip' if show_preview else 'OFF'}\n")

        buf      = deque(maxlen=int(fps * PRE_EVENT_SEC))
        found    = []
        saved_ts = []
        idx      = 0
        quit_f   = False

        while not quit_f:
            ok, frame = cap.read()
            if not ok: break

            buf.append(frame.copy())
            ts  = idx / fps
            idx += 1

            if idx % 15 == 0 or idx == total:
                sys.stdout.write(_bar(idx, total, suffix=f"violations:{len(found)}"))
                sys.stdout.flush()

            if idx % FRAME_SKIP != 0:
                if show_preview:
                    cv2.imshow("Violation Detector  (Q=skip)", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"): quit_f = True
                continue

            dets  = self._yolo(frame)
            viols = self.rules.check(dets, ts, path)
            pframe = self._draw(frame.copy(), dets, viols)

            if show_preview:
                cv2.imshow("Violation Detector  (Q=skip)", pframe)
                if cv2.waitKey(1) & 0xFF == ord("q"): quit_f = True

            for v in viols:
                if not any(abs(t - ts) < CLIP_GAP_SEC for t in saved_ts):
                    print(f"\n  [VIOLATION]  {v.violation_type}  @  {ts:.1f}s  (conf {v.confidence:.0%})")
                    self._save_clip(cap, buf, v, fps, W, H)
                    saved_ts.append(ts)
                    found.append(v)

        sys.stdout.write("\r" + " "*80 + "\r"); sys.stdout.flush()
        cap.release()
        if show_preview: cv2.destroyAllWindows()
        return found

    def _yolo(self, frame):
        out = []
        for r in self.model(frame, conf=self.conf, verbose=False):
            for box in r.boxes:
                cid = int(box.cls[0])
                if cid not in RELEVANT: continue
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                out.append({
                    "class_name": RELEVANT[cid],
                    "confidence": float(box.conf[0]),
                    "bbox": (x1,y1,x2,y2)
                })
        return out

    def _draw(self, frame, dets, viols):
        for d in dets:
            x1,y1,x2,y2 = d["bbox"]
            col = COLORS.get(d["class_name"], (180,180,180))
            lbl = f"{d['class_name']} {d['confidence']:.0%}"
            cv2.rectangle(frame, (x1,y1),(x2,y2), col, 2)
            (tw,th),_ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(frame, (x1,y1-th-6),(x1+tw+4,y1), col, -1)
            cv2.putText(frame, lbl, (x1+2,y1-4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,0,0), 1)
        for i, v in enumerate(viols):
            cv2.rectangle(frame,(0,i*38),(frame.shape[1],i*38+38),(0,0,180),-1)
            cv2.putText(frame, f"VIOLATION: {v.violation_type.upper()}",
                        (10,i*38+26), cv2.FONT_HERSHEY_SIMPLEX, 0.78,(255,255,255),2)
        cv2.putText(frame, datetime.now().strftime("%Y-%m-%d  %H:%M:%S"),
                    (10,frame.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX,0.45,(180,180,180),1)
        return frame

    def _save_clip(self, cap, buf, v: Violation, fps, W, H):
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = v.violation_type.replace(" ","_")
        clip = EVIDENCE_DIR / f"{name}_{ts}.avi"
        snap = EVIDENCE_DIR / f"{name}_{ts}.jpg"

        wr = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"XVID"), fps, (W,H))
        for f in buf: wr.write(f)                         # pre-event frames
        for _ in range(int(fps * POST_EVENT_SEC)):         # post-event frames
            ok,f = cap.read()
            if not ok: break
            cv2.rectangle(f,(0,0),(W,48),(0,0,160),-1)
            cv2.putText(f, f"VIOLATION: {v.violation_type.upper()}",
                        (10,34), cv2.FONT_HERSHEY_SIMPLEX, 1.0,(255,255,255),2)
            wr.write(f)
        wr.release()

        if buf: cv2.imwrite(str(snap), buf[-1])
        v.evidence_clip = str(clip)
        v.snapshot_path = str(snap)
        logger.info(f"    Saved: {clip.name}")

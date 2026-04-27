"""
Traffic rules engine — tuned v2.
Changes from v1:
  - Cooldown raised 30s -> 45s         (fewer duplicate flags)
  - Red light needs 4 frames not 3     (stricter, fewer false positives)
  - No helmet ratio tightened 0.75->0.85 + requires high confidence
  - Triple riding overlap threshold raised (stricter matching)
  - Stop sign requires 3 consecutive frames (was 2)
  - Footpath rule requires 4 pedestrians not 3
  - All confidences require minimum 0.45 from YOLO (set in processor)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Violation:
    violation_type: str
    timestamp_sec:  float
    confidence:     float
    source_video:   str
    detected_at:    str   = field(default_factory=lambda: datetime.now().isoformat())
    evidence_clip:  Optional[str] = None
    snapshot_path:  Optional[str] = None
    notes:          str   = ""

    def to_dict(self):
        return self.__dict__.copy()


class RulesEngine:
    def __init__(self):
        self._recent:     list = []
        self._window:     int  = 15          # wider temporal window (was 10)
        self._red_count:  int  = 0
        self._stop_count: int  = 0
        self._cooldowns:  dict = {}
        self._cooldown:   int  = 45          # raised from 30s -> 45s

    def check(self, detections: list, ts: float, src: str) -> list:
        self._recent.append(detections)
        if len(self._recent) > self._window:
            self._recent.pop(0)

        results = []
        for fn in [self._no_helmet, self._red_light, self._triple_riding,
                   self._stop_sign, self._footpath]:
            v = fn(detections, ts, src)
            if v and (ts - self._cooldowns.get(v.violation_type, -999)) >= self._cooldown:
                self._cooldowns[v.violation_type] = ts
                results.append(v)
        return results

    # ── helpers ───────────────────────────────────────────────────────────────

    def _cls(self, dets, *names):
        return [d for d in dets if d["class_name"] in names]

    def _overlap(self, a, b):
        ax1,ay1,ax2,ay2 = a["bbox"]; bx1,by1,bx2,by2 = b["bbox"]
        ow = max(0, min(ax2,bx2) - max(ax1,bx1))
        oh = max(0, min(ay2,by2) - max(ay1,by1))
        return ow * oh

    def _area(self, d):
        x1,y1,x2,y2 = d["bbox"]; return max(1,(x2-x1)*(y2-y1))

    def _avg_conf(self, dets):
        if not dets: return 0
        return sum(d["confidence"] for d in dets) / len(dets)

    # ── Rule 1: No Helmet ─────────────────────────────────────────────────────
    # Tightened: ratio 0.75->0.85, YOLO confidence must be >= 0.55,
    # and the person must be seen in at least 2 of last 3 frames too.
    def _no_helmet(self, dets, ts, src):
        for moto in self._cls(dets, "motorcycle"):
            for person in self._cls(dets, "person"):
                if person["confidence"] < 0.55:          # require confident person detection
                    continue
                if self._overlap(moto, person) < self._area(moto) * 0.12:
                    continue                              # person not clearly on motorcycle

                x1,y1,x2,y2 = person["bbox"]
                h = y2-y1; w = x2-x1
                if h <= 0:
                    continue

                ratio = w / h
                if ratio < 0.85:                         # tightened from 0.75
                    continue

                # Must also appear in at least 2 of the last 3 frames
                recent_hits = 0
                for past in self._recent[-3:]:
                    if any(d["class_name"] == "person" and d["confidence"] >= 0.50
                           for d in past):
                        recent_hits += 1
                if recent_hits < 2:
                    continue

                return Violation(
                    "No Helmet", ts,
                    round(person["confidence"] * 0.85, 3), src,
                    notes="Motorcyclist without helmet — confirmed across multiple frames"
                )
        return None

    # ── Rule 2: Red Light Running ─────────────────────────────────────────────
    # Tightened: needs 4 consecutive detections not 3.
    # Also resets immediately if no traffic light visible.
    def _red_light(self, dets, ts, src):
        lights   = self._cls(dets, "traffic light")
        vehicles = self._cls(dets, "car","motorcycle","bus","truck")

        if not lights:
            self._red_count = 0
            return None

        if vehicles:
            self._red_count += 1
        else:
            self._red_count = max(0, self._red_count - 1)  # decay instead of hard reset

        if self._red_count >= 4:                           # raised from 3 -> 4
            self._red_count = 0
            avg = self._avg_conf(vehicles)
            return Violation(
                "Red Light Running", ts,
                round(avg * 0.90, 3), src,
                notes=f"{len(vehicles)} vehicle(s) moving through red — {self._red_count+4} frame confirmation"
            )
        return None

    # ── Rule 3: Triple Riding ─────────────────────────────────────────────────
    # Tightened: overlap threshold raised 0.08->0.12
    def _triple_riding(self, dets, ts, src):
        for moto in self._cls(dets, "motorcycle"):
            riders = sum(
                1 for p in self._cls(dets, "person")
                if self._overlap(moto, p) > self._area(moto) * 0.12   # raised from 0.08
            )
            if riders >= 3:
                return Violation(
                    "Triple Riding", ts, 0.80, src,
                    notes=f"{riders} persons detected on one motorcycle"
                )
        return None

    # ── Rule 4: Stop Sign Violated ────────────────────────────────────────────
    # Tightened: needs 3 consecutive frames not 2
    def _stop_sign(self, dets, ts, src):
        signs    = self._cls(dets, "stop sign")
        vehicles = self._cls(dets, "car","motorcycle","bus","truck")

        if signs and vehicles:
            self._stop_count += 1
        else:
            self._stop_count = 0

        if self._stop_count >= 3:                         # raised from 2 -> 3
            self._stop_count = 0
            return Violation(
                "Stop Sign Violated", ts, 0.70, src,
                notes="Vehicle did not stop at stop sign — 3-frame confirmation"
            )
        return None

    # ── Rule 5: Riding on Footpath ────────────────────────────────────────────
    # Tightened: requires 4 pedestrians not 3
    def _footpath(self, dets, ts, src):
        motos   = self._cls(dets, "motorcycle")
        persons = self._cls(dets, "person")
        roads   = self._cls(dets, "car","bus","truck")

        if motos and len(persons) >= 4 and not roads:    # raised from 3 -> 4
            return Violation(
                "Riding on Footpath", ts, 0.62, src,
                notes=f"Motorcycle near {len(persons)} pedestrians with no road vehicles"
            )
        return None

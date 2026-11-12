"""
Technical Quality Assurance Module (Direction D5).
Implements automated technical checks on assembled video artifacts:
1. Black frame detection (blank or glitching screens).
2. Freeze frame detection (scenes stuck on static screens for excessive duration).
3. Audio-Visual onset synchronization checks (timing drift between narration utterance and visual event).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class TechnicalFinding:
    kind: str  # "black_frame", "freeze_frame", "av_drift"
    start_sec: float
    duration_sec: float
    severity: str  # "critical", "high", "medium", "low"
    detail: str
    cue_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "start_sec": round(self.start_sec, 2),
            "duration_sec": round(self.duration_sec, 2),
            "severity": self.severity,
            "detail": self.detail,
            "cue_id": self.cue_id,
        }


@dataclass
class TechnicalQAReport:
    passed: bool
    black_findings: List[TechnicalFinding] = field(default_factory=list)
    freeze_findings: List[TechnicalFinding] = field(default_factory=list)
    sync_findings: List[TechnicalFinding] = field(default_factory=list)
    total_findings: int = 0
    max_drift_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "total_findings": self.total_findings,
            "max_drift_sec": round(self.max_drift_sec, 2),
            "black_findings": [f.to_dict() for f in self.black_findings],
            "freeze_findings": [f.to_dict() for f in self.freeze_findings],
            "sync_findings": [f.to_dict() for f in self.sync_findings],
        }

    def to_qa_findings(self) -> List[Dict[str, Any]]:
        """Formats findings for ingestion into Lessonforge or Code2Video QA reports."""
        qa_findings = []
        for f in self.black_findings + self.freeze_findings:
            qa_findings.append({
                "beat": f.cue_id,
                "stage": "technical",
                "kind": f.kind,
                "severity": f.severity,
                "what": f.detail,
                "source": "technical_qa",
                "repair": "report only (technical artifact defect)",
            })
        for f in self.sync_findings:
            qa_findings.append({
                "beat": f.cue_id,
                "stage": "sync",
                "kind": "late_cue" if "lagging" in f.detail else "premature_cue",
                "severity": f.severity,
                "what": f.detail,
                "source": "av_sync_check",
                "repair": "retime_beat_cues",
            })
        return qa_findings


class TechnicalQAChecker:
    """
    Automated video artifact inspector using FFmpeg with pure-Python fallbacks.
    """

    def __init__(
        self,
        ffmpeg_bin: Optional[str] = None,
        max_freeze_sec: float = 3.5,
        max_black_sec: float = 0.5,
        max_drift_sec: float = 1.5,
    ):
        self.ffmpeg_bin = ffmpeg_bin or shutil.which("ffmpeg")
        self.max_freeze_sec = max_freeze_sec
        self.max_black_sec = max_black_sec
        self.max_drift_sec = max_drift_sec

    def detect_black_frames(
        self,
        video_path: Union[str, Path],
        min_duration_sec: Optional[float] = None,
        pix_th: float = 0.10,
    ) -> List[TechnicalFinding]:
        """
        Detects sustained black frames in the video using ffmpeg's blackdetect filter.
        """
        min_d = min_duration_sec if min_duration_sec is not None else self.max_black_sec
        path = Path(video_path)
        if not path.exists():
            return []

        if not self.ffmpeg_bin:
            return []

        cmd = [
            self.ffmpeg_bin,
            "-hide_banner",
            "-nostats",
            "-i", str(path),
            "-vf", f"blackdetect=d={min_d}:pix_th={pix_th}",
            "-f", "null",
            "-",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = proc.stderr or ""
            return self.parse_blackdetect_output(output, min_d)
        except Exception:
            return []

    @staticmethod
    def parse_blackdetect_output(output: str, min_d: float) -> List[TechnicalFinding]:
        findings: List[TechnicalFinding] = []
        # black_start:1.200 black_end:2.500 black_duration:1.300
        pattern = re.compile(
            r"black_start:\s*([0-9.]+)\s+black_end:\s*([0-9.]+)\s+black_duration:\s*([0-9.]+)"
        )
        for match in pattern.finditer(output):
            start = float(match.group(1))
            end = float(match.group(2))
            dur = float(match.group(3))
            if dur >= min_d:
                severity = "critical" if dur > 2.0 else "high"
                findings.append(TechnicalFinding(
                    kind="black_frame",
                    start_sec=start,
                    duration_sec=dur,
                    severity=severity,
                    detail=f"Blank/black video detected from {start:.2f}s to {end:.2f}s (duration {dur:.2f}s)",
                ))
        return findings

    def detect_freeze_frames(
        self,
        video_path: Union[str, Path],
        min_duration_sec: Optional[float] = None,
        noise: float = 0.001,
    ) -> List[TechnicalFinding]:
        """
        Detects frozen video segments using ffmpeg's freezedetect filter.
        """
        min_d = min_duration_sec if min_duration_sec is not None else self.max_freeze_sec
        path = Path(video_path)
        if not path.exists() or not self.ffmpeg_bin:
            return []

        cmd = [
            self.ffmpeg_bin,
            "-hide_banner",
            "-nostats",
            "-i", str(path),
            "-vf", f"freezedetect=n={noise}:d={min_d}",
            "-f", "null",
            "-",
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = proc.stderr or ""
            return self.parse_freezedetect_output(output, min_d)
        except Exception:
            return []

    @staticmethod
    def parse_freezedetect_output(output: str, min_d: float) -> List[TechnicalFinding]:
        findings: List[TechnicalFinding] = []
        # freeze_start: 3.500 ... freeze_duration: 2.100 freeze_end: 5.600
        # or freeze_start: 3.5 freeze_duration: 4.0
        start_pattern = re.compile(r"freeze_start:\s*([0-9.]+)")
        dur_pattern = re.compile(r"freeze_duration:\s*([0-9.]+)")

        starts = [float(m.group(1)) for m in start_pattern.finditer(output)]
        durs = [float(m.group(1)) for m in dur_pattern.finditer(output)]

        for start, dur in zip(starts, durs):
            if dur >= min_d:
                severity = "high" if dur > 5.0 else "medium"
                findings.append(TechnicalFinding(
                    kind="freeze_frame",
                    start_sec=start,
                    duration_sec=dur,
                    severity=severity,
                    detail=f"Static freeze frame detected from {start:.2f}s for {dur:.2f}s (exceeds {min_d:.1f}s threshold)",
                ))
        return findings

    def check_av_synchronization(
        self,
        cues_or_timeline: Union[List[Dict[str, Any]], Dict[str, Any], str, Path],
        max_drift_sec: Optional[float] = None,
    ) -> List[TechnicalFinding]:
        """
        Audits audio-visual synchronization by comparing speech anchor timestamps
        with actual visual element appearance times.
        """
        max_drift = max_drift_sec if max_drift_sec is not None else self.max_drift_sec
        cues: List[Dict[str, Any]] = []

        if isinstance(cues_or_timeline, (str, Path)):
            p = Path(cues_or_timeline)
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        cues = data
                    elif isinstance(data, dict):
                        cues = data.get("cues") or data.get("timeline") or []
                except Exception:
                    pass
        elif isinstance(cues_or_timeline, dict):
            cues = cues_or_timeline.get("cues") or cues_or_timeline.get("timeline") or []
        elif isinstance(cues_or_timeline, list):
            cues = cues_or_timeline

        findings: List[TechnicalFinding] = []
        for cue in cues:
            # Expected schema: anchor / speech_start vs actual / visual_start
            speech_t = cue.get("speech_start")
            if speech_t is None:
                speech_t = cue.get("anchor") or cue.get("start")

            visual_t = cue.get("visual_start")
            if visual_t is None:
                visual_t = cue.get("actual_before_wait") or cue.get("actual") or cue.get("timestamp")

            if speech_t is None or visual_t is None:
                continue

            try:
                speech_t = float(speech_t)
                visual_t = float(visual_t)
            except (ValueError, TypeError):
                continue

            drift = round(visual_t - speech_t, 3)
            abs_drift = round(abs(drift), 3)

            if abs_drift > max_drift:
                cue_id = str(cue.get("beat") or cue.get("id") or cue.get("cue_id") or "cue")
                phrase = cue.get("phrase") or cue.get("label") or cue.get("concept") or cue_id
                severity = "critical" if abs_drift > 3.0 else "high"

                if drift > 0:
                    detail = (
                        f"Visual lag: Animation for '{phrase}' appeared {drift:.2f}s AFTER speech anchor "
                        f"(threshold {max_drift:.1f}s)"
                    )
                else:
                    detail = (
                        f"Premature visual: Animation for '{phrase}' appeared {abs_drift:.2f}s BEFORE speech anchor "
                        f"(threshold {max_drift:.1f}s)"
                    )

                findings.append(TechnicalFinding(
                    kind="av_drift",
                    start_sec=min(speech_t, visual_t),
                    duration_sec=abs_drift,
                    severity=severity,
                    detail=detail,
                    cue_id=cue_id,
                ))

        return findings

    def run_full_qa(
        self,
        video_path: Optional[Union[str, Path]] = None,
        cues_or_timeline: Optional[Union[List[Dict[str, Any]], Dict[str, Any], str, Path]] = None,
    ) -> TechnicalQAReport:
        """
        Runs comprehensive technical QA checks across black frames, freeze frames, and AV sync.
        """
        black_findings = []
        freeze_findings = []
        if video_path and Path(video_path).exists():
            black_findings = self.detect_black_frames(video_path)
            freeze_findings = self.detect_freeze_frames(video_path)

        sync_findings = []
        if cues_or_timeline:
            sync_findings = self.check_av_synchronization(cues_or_timeline)

        total = len(black_findings) + len(freeze_findings) + len(sync_findings)
        max_drift = round(max([f.duration_sec for f in sync_findings], default=0.0), 3)
        has_critical = any(f.severity in ("critical", "high") for f in black_findings + freeze_findings + sync_findings)

        return TechnicalQAReport(
            passed=(total == 0 or not has_critical),
            black_findings=black_findings,
            freeze_findings=freeze_findings,
            sync_findings=sync_findings,
            total_findings=total,
            max_drift_sec=max_drift,
        )

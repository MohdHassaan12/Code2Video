"""
Unit tests for Direction D5: Video Artifact Technical Quality Checks.
Tests black frame detection, freeze frame detection, and AV onset synchronization.
"""

from pathlib import Path
from code2video.technical_qa import TechnicalQAChecker, TechnicalFinding, TechnicalQAReport


def test_black_frame_parser():
    checker = TechnicalQAChecker(max_black_sec=0.5)

    sample_output = """
    [blackdetect @ 0x7fa890] black_start: 1.000 black_end: 1.200 black_duration: 0.200
    [blackdetect @ 0x7fa890] black_start: 5.400 black_end: 6.800 black_duration: 1.400
    [blackdetect @ 0x7fa890] black_start: 12.000 black_end: 15.500 black_duration: 3.500
    """

    findings = checker.parse_blackdetect_output(sample_output, min_d=0.5)
    # First duration is 0.200 (< 0.5), so only 2 findings should be kept
    assert len(findings) == 2

    assert findings[0].start_sec == 5.4
    assert findings[0].duration_sec == 1.4
    assert findings[0].severity == "high"

    assert findings[1].start_sec == 12.0
    assert findings[1].duration_sec == 3.5
    assert findings[1].severity == "critical"


def test_freeze_frame_parser():
    checker = TechnicalQAChecker(max_freeze_sec=3.0)

    sample_output = """
    [freezedetect @ 0x123] freeze_start: 2.100 freeze_duration: 1.500 freeze_end: 3.600
    [freezedetect @ 0x123] freeze_start: 10.000 freeze_duration: 4.200 freeze_end: 14.200
    [freezedetect @ 0x123] freeze_start: 25.000 freeze_duration: 6.800 freeze_end: 31.800
    """

    findings = checker.parse_freezedetect_output(sample_output, min_d=3.0)
    assert len(findings) == 2

    assert findings[0].start_sec == 10.0
    assert findings[0].duration_sec == 4.2
    assert findings[0].severity == "medium"

    assert findings[1].start_sec == 25.0
    assert findings[1].duration_sec == 6.8
    assert findings[1].severity == "high"


def test_av_sync_check_lag_and_premature():
    checker = TechnicalQAChecker(max_drift_sec=1.5)

    cues = [
        {
            "cue_id": "beat_01",
            "phrase": "Intro Title",
            "speech_start": 2.0,
            "visual_start": 2.2,  # 0.2s drift (acceptable)
        },
        {
            "cue_id": "beat_02",
            "phrase": "Force Arrow",
            "speech_start": 10.0,
            "visual_start": 12.5,  # 2.5s lag (> 1.5s threshold)
        },
        {
            "cue_id": "beat_03",
            "phrase": "Acceleration Formula",
            "speech_start": 20.0,
            "visual_start": 18.0,  # 2.0s premature (> 1.5s threshold)
        },
    ]

    findings = checker.check_av_synchronization(cues)
    assert len(findings) == 2

    # beat_02 should be visual lag
    assert findings[0].cue_id == "beat_02"
    assert "AFTER speech anchor" in findings[0].detail
    assert findings[0].duration_sec == 2.5

    # beat_03 should be premature
    assert findings[1].cue_id == "beat_03"
    assert "BEFORE speech anchor" in findings[1].detail
    assert findings[1].duration_sec == 2.0


def test_full_technical_qa_report_and_export():
    checker = TechnicalQAChecker(max_drift_sec=1.0)

    cues = [
        {"cue_id": "b1", "phrase": "Good Sync", "speech_start": 1.0, "visual_start": 1.1},
        {"cue_id": "b2", "phrase": "Drifting Cue", "speech_start": 5.0, "visual_start": 6.8},
    ]

    report = checker.run_full_qa(cues_or_timeline=cues)
    assert not report.passed
    assert report.total_findings == 1
    assert report.max_drift_sec == 1.8

    qa_findings = report.to_qa_findings()
    assert len(qa_findings) == 1
    assert qa_findings[0]["stage"] == "sync"
    assert qa_findings[0]["beat"] == "b2"
    assert qa_findings[0]["source"] == "av_sync_check"


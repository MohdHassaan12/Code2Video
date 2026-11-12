"""Test voice catalogue API, preview endpoint, and UniversalTTSService routing for Edge and Local TTS."""
import os
from unittest.mock import patch
from fastapi.testclient import TestClient

from lessonforge.engine.api.voices import voices, tts_preview, TTSPreviewRequest, router
from lessonforge.viz_helpers import UniversalTTSService, EdgeTTSService, LocalTTSService


def test_voices_catalogue_includes_edge_and_local():
    data = voices()
    assert "edge_voices_by_lang" in data
    assert "local_voices_by_lang" in data
    assert "hi-IN" in data["edge_voices_by_lang"]
    assert "hi-IN" in data["local_voices_by_lang"]
    assert "edge" in data["providers_configured"]
    assert "local" in data["providers_configured"]


def test_universal_tts_service_routing():
    # Edge routing
    s_edge = UniversalTTSService(provider="edge", language="hi-IN", speaker="hi-IN-SwaraNeural")
    assert s_edge.provider == "edge"
    assert isinstance(s_edge.delegate, EdgeTTSService)
    assert s_edge.delegate.voice_name == "hi-IN-SwaraNeural"

    # Local routing
    s_local = UniversalTTSService(provider="local", language="en-IN", speaker="af_heart")
    assert s_local.provider == "local"
    assert isinstance(s_local.delegate, LocalTTSService)
    assert s_local.delegate.voice_name == "af_heart"


def test_tts_preview_edge_and_local(tmp_path, monkeypatch):
    monkeypatch.setattr("lessonforge.engine.api.voices.PREVIEW_DIR", str(tmp_path))

    with patch("lessonforge.longform.speech.EdgeBackend.synthesize") as mock_edge_synth:
        req = TTSPreviewRequest(text="Hello from edge", language="en-IN", tts_provider="edge", speaker="en-IN-NeerjaNeural")
        res = tts_preview(req)
        assert res["provider_used"] == "edge"
        assert res["url"].endswith(".mp3")
        assert mock_edge_synth.called

    with patch("lessonforge.longform.speech.KokoroBackend.synthesize") as mock_local_synth:
        req = TTSPreviewRequest(text="Hello from kokoro", language="en-IN", tts_provider="local", speaker="af_heart")
        res = tts_preview(req)
        assert res["provider_used"] == "local"
        assert res["url"].endswith(".wav")
        assert mock_local_synth.called

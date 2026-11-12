"""A git-lfs pointer left where the Kokoro model should be is named as one, with where the real files usually are."""
import pytest

from lessonforge.longform import speech

POINTER = b"version https://git-lfs.github.com/spec/v1\noid sha256:" + b"ab" * 32 + b"\nsize 325532387\n"


def _real(path, size=4096):
    path.write_bytes(b"\x08\x07" + b"\0" * size)
    return str(path)


def test_a_model_that_is_a_git_lfs_pointer_is_named_as_one(tmp_path):
    model = tmp_path / "kokoro-v1.0.onnx"
    model.write_bytes(POINTER)
    backend = speech.KokoroBackend(model=str(model), voices=_real(tmp_path / "voices-v1.0.bin"))
    with pytest.raises(speech.KokoroModelError) as err:
        backend._paths()
    text = str(err.value)
    assert "git-lfs pointer" in text and "kokoro-v1.0.onnx" in text and "KOKORO_MODEL" in text
    assert "/workspace/models/ComfyUI/models_local/tts/kokoro/" in text and "git lfs pull" in text
    assert "no speech backend" not in text


def test_the_voice_pack_as_a_pointer_is_named_too_and_a_tiny_file_is_one_even_without_the_header(tmp_path):
    voices = tmp_path / "voices-v1.0.bin"
    voices.write_bytes(POINTER)
    with pytest.raises(speech.KokoroModelError, match="KOKORO_VOICES.*git-lfs pointer"):
        speech.KokoroBackend(model=_real(tmp_path / "m.onnx"), voices=str(voices))._paths()
    voices.write_bytes(b"x" * 500)                                  # under 1 KB: not a voice pack whatever it says
    with pytest.raises(speech.KokoroModelError, match="git-lfs pointer"):
        speech.KokoroBackend(model=_real(tmp_path / "m.onnx"), voices=str(voices))._paths()


def test_a_large_file_that_starts_with_the_header_is_still_a_pointer(tmp_path):
    model = tmp_path / "m.onnx"
    model.write_bytes(POINTER + b" " * 2000)
    with pytest.raises(speech.KokoroModelError):
        speech.check_not_lfs_pointer("KOKORO_MODEL", str(model))


def test_real_files_pass_and_a_missing_one_keeps_its_own_message(tmp_path):
    model, voices = _real(tmp_path / "m.onnx"), _real(tmp_path / "v.bin")
    assert speech.KokoroBackend(model=model, voices=voices)._paths() == (model, voices)
    with pytest.raises(FileNotFoundError, match="Kokoro file not found"):
        speech.KokoroBackend(model=str(tmp_path / "nope.onnx"), voices=voices)._paths()


def test_synthesize_says_so_before_it_needs_the_kokoro_package(tmp_path):
    model = tmp_path / "kokoro-v1.0.onnx"
    model.write_bytes(POINTER)
    backend = speech.KokoroBackend(model=str(model), voices=_real(tmp_path / "v.bin"))
    with pytest.raises(speech.KokoroModelError, match="git-lfs pointer"):
        backend.synthesize("hello", tmp_path / "out.wav")

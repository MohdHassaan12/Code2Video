"""
Multi-Lingual Dynamic Re-Pacing Engine.
Enables cross-lingual educational video generation with native neural TTS and
automatic dynamic visual re-timing:
- English (en-US), Spanish (es-ES), German (de-DE), French (fr-FR),
  Hindi (hi-IN), Mandarin (zh-CN), Japanese (ja-JP)
- Formula phoneticization for clean mathematical speech
- Automatic Manim animation re-pacing via AstProcessor duration alignment
- Localized WebVTT subtitle track generation
"""

import os
import re
from typing import Dict, List, Any, Tuple, Optional
from adapt_manim.core.audio import NarrationEngine, get_audio_duration
from adapt_manim.core.types import Storyboard, StoryboardSection, LectureCue
from adapt_manim.coding.ast_processor import AstProcessor


class MultiLingualEngine:
    """
    Synthesizes multi-lingual educational voice tracks and automatically re-paces
    Manim animation blocks to match target language speech duration.
    """

    VOICE_REGISTRY = {
        "en": {"code": "en-US", "name": "English", "voice": "en-US-ChristopherNeural"},
        "es": {"code": "es-ES", "name": "Spanish", "voice": "es-ES-AlvaroNeural"},
        "de": {"code": "de-DE", "name": "German", "voice": "de-DE-ConradNeural"},
        "fr": {"code": "fr-FR", "name": "French", "voice": "fr-FR-HenriNeural"},
        "hi": {"code": "hi-IN", "name": "Hindi", "voice": "hi-IN-MadhurNeural"},
        "zh": {"code": "zh-CN", "name": "Mandarin", "voice": "zh-CN-YunxiNeural"},
        "ja": {"code": "ja-JP", "name": "Japanese", "voice": "ja-JP-KeitaNeural"}
    }

    # Phonetic pronunciation mapping for common math formulas across languages
    PHONETIC_FORMULA_MAP = {
        "en": {
            r"e\^\{i\\pi\}\s*\+\s*1\s*=\s*0": "e to the power of i pi plus one equals zero",
            r"e\^\{i\\theta\}": "e to the power of i theta",
            r"a\^2\s*\+\s*b\^2\s*=\s*c\^2": "a squared plus b squared equals c squared",
            r"\\frac\{1\}\{2\}": "one half",
            r"\\min": "minimize",
            r"\\sum": "sum"
        },
        "es": {
            r"e\^\{i\\pi\}\s*\+\s*1\s*=\s*0": "e elevado a la i pi más uno es igual a cero",
            r"e\^\{i\\theta\}": "e elevado a la i theta",
            r"a\^2\s*\+\s*b\^2\s*=\s*c\^2": "a al cuadrado más b al cuadrado es igual a c al cuadrado",
            r"\\frac\{1\}\{2\}": "un medio",
            r"\\min": "minimizar",
            r"\\sum": "suma"
        },
        "de": {
            r"e\^\{i\\pi\}\s*\+\s*1\s*=\s*0": "e hoch i pi plus eins ist gleich null",
            r"e\^\{i\\theta\}": "e hoch i theta",
            r"a\^2\s*\+\s*b\^2\s*=\s*c\^2": "a Quadrat plus b Quadrat gleich c Quadrat",
            r"\\frac\{1\}\{2\}": "ein Halb",
            r"\\min": "minimiere",
            r"\\sum": "Summe"
        },
        "fr": {
            r"e\^\{i\\pi\}\s*\+\s*1\s*=\s*0": "e puissance i pi plus un égale zéro",
            r"e\^\{i\\theta\}": "e puissance i thêta",
            r"a\^2\s*\+\s*b\^2\s*=\s*c\^2": "a au carré plus b au carré égale c au carré",
            r"\\frac\{1\}\{2\}": "un demi",
            r"\\min": "minimiser",
            r"\\sum": "somme"
        },
        "hi": {
            r"e\^\{i\\pi\}\s*\+\s*1\s*=\s*0": "e ki ghat i pi plus ek barabar shunya",
            r"e\^\{i\\theta\}": "e ki ghat i theta",
            r"a\^2\s*\+\s*b\^2\s*=\s*c\^2": "a square plus b square barabar c square",
            r"\\frac\{1\}\{2\}": "aadha",
            r"\\min": "nyunatam",
            r"\\sum": "yog"
        }
    }

    # Core curriculum translation dictionary for key topic concepts
    TOPIC_TRANSLATIONS = {
        "es": {
            "Euler's Formula": "La Fórmula de Euler",
            "Support Vector Machine": "Máquinas de Vectores de Soporte",
            "Pure Fourier Series": "Series de Fourier Puras",
            "Neural Network": "Redes Neuronales",
            "Pythagorean Theorem": "Teorema de Pitágoras",
            "Welcome to": "Bienvenidos a",
            "Notice how": "Observen cómo",
            "This geometric relation": "Esta relación geométrica",
            "In summary": "En resumen"
        },
        "de": {
            "Euler's Formula": "Eulersche Formel",
            "Support Vector Machine": "Support-Vektor-Maschine",
            "Pure Fourier Series": "Reine Fourier-Reihen",
            "Neural Network": "Neuronale Netze",
            "Pythagorean Theorem": "Satz des Pythagoras",
            "Welcome to": "Willkommen zu",
            "Notice how": "Beachten Sie wie",
            "This geometric relation": "Diese geometrische Beziehung",
            "In summary": "Zusammenfassend"
        },
        "fr": {
            "Euler's Formula": "La Formule d'Euler",
            "Support Vector Machine": "Machine à Vecteurs de Support",
            "Pure Fourier Series": "Séries de Fourier Pures",
            "Neural Network": "Réseaux de Neurones",
            "Pythagorean Theorem": "Théorème de Pythagore",
            "Welcome to": "Bienvenue à",
            "Notice how": "Remarquez comment",
            "This geometric relation": "Cette relation géométrique",
            "In summary": "En résumé"
        },
        "hi": {
            "Euler's Formula": "यूलर का सूत्र (Euler's Formula)",
            "Support Vector Machine": "सपोर्ट वेक्टर मशीन (SVM)",
            "Pure Fourier Series": "फूरियर श्रृंखला (Fourier Series)",
            "Neural Network": "न्यूरल नेटवर्क (Neural Network)",
            "Pythagorean Theorem": "पाइथागोरस प्रमेय (Pythagorean Theorem)",
            "Welcome to": "स्वागत है",
            "Notice how": "ध्यान दें कि कैसे",
            "This geometric relation": "यह ज्यामितीय संबंध",
            "In summary": "संक्षेप में"
        }
    }

    @classmethod
    def get_supported_languages(cls) -> List[Dict[str, str]]:
        """Returns list of supported language codes and metadata."""
        return [
            {"code": k, "name": v["name"], "voice": v["voice"]}
            for k, v in cls.VOICE_REGISTRY.items()
        ]

    @classmethod
    def translate_cue_text(cls, text: str, target_lang: str, llm_client: Optional[Any] = None) -> str:
        """Translates lecture cue text into the target language and formats math formulas."""
        if target_lang == "en" or target_lang not in cls.VOICE_REGISTRY:
            return text

        # 1. If LLM is available, perform live pedagogical translation
        if llm_client:
            try:
                lang_name = cls.VOICE_REGISTRY[target_lang]["name"]
                prompt = (
                    f"Translate the following educational animation narration line into natural, spoken {lang_name}. "
                    f"Ensure mathematical terminology is accurate and sounds natural when spoken aloud. "
                    f"Return ONLY the translated sentence.\n\n"
                    f"Narration: {text}"
                )
                translated = llm_client.generate(prompt).strip().strip('"')
                if translated:
                    return cls.phoneticize_formulas(translated, target_lang)
            except Exception:
                pass

        # 2. Rule-based translation fallback
        translated = text
        lang_dict = cls.TOPIC_TRANSLATIONS.get(target_lang, {})
        for eng, foreign in lang_dict.items():
            translated = re.sub(rf"\b{re.escape(eng)}\b", foreign, translated, flags=re.IGNORECASE)

        return cls.phoneticize_formulas(translated, target_lang)

    @classmethod
    def phoneticize_formulas(cls, text: str, lang: str) -> str:
        """Replaces raw LaTeX mathematical patterns with spoken phonetic phrases."""
        phonetic_dict = cls.PHONETIC_FORMULA_MAP.get(lang, cls.PHONETIC_FORMULA_MAP.get("en", {}))
        result = text
        for pat, spoken in phonetic_dict.items():
            result = re.sub(pat, spoken, result)
        return result

    @classmethod
    def synthesize_multilingual_section(
        cls,
        section: StoryboardSection,
        target_lang: str,
        output_dir: str,
        llm_client: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Synthesizes localized audio cues using the language's native neural voice
        and returns duration metadata.
        """
        os.makedirs(output_dir, exist_ok=True)
        voice_info = cls.VOICE_REGISTRY.get(target_lang, cls.VOICE_REGISTRY["en"])
        voice_name = voice_info["voice"]

        cue_metadata = []
        for cue in section.cues:
            clean_text = cue.text.lstrip("- •").strip()
            localized_text = cls.translate_cue_text(clean_text, target_lang, llm_client)

            wav_path = os.path.join(output_dir, f"{cue.cue_id}_{target_lang}.wav")
            success, duration = NarrationEngine.synthesize_cue_audio(
                text=localized_text,
                output_wav_path=wav_path,
                voice=voice_name
            )

            if os.path.exists(wav_path):
                cue_metadata.append({
                    "cue_id": cue.cue_id,
                    "original_text": clean_text,
                    "localized_text": localized_text,
                    "wav_path": wav_path,
                    "duration_sec": duration,
                    "lang": target_lang
                })

        return cue_metadata

    @classmethod
    def re_pace_manim_code_for_language(
        cls,
        code: str,
        cue_durations: List[float],
        section_id: Optional[str] = None
    ) -> str:
        """
        Dynamically stretches or compresses Manim scene animation run times and wait intervals
        to synchronize precisely with foreign language speech duration.
        """
        return AstProcessor.align_animation_durations_to_audio(
            code=code,
            cue_durations=cue_durations,
            section_id=section_id
        )

    @classmethod
    def generate_webvtt_subtitles(
        cls,
        all_cue_metadata: List[Dict[str, Any]],
        output_path: str
    ) -> str:
        """Exports synchronized WebVTT (.vtt) subtitle tracks."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        lines = ["WEBVTT", ""]

        current_time = 0.0
        for idx, item in enumerate(all_cue_metadata, 1):
            dur = item.get("duration_sec", 3.0)
            start_t = current_time
            end_t = current_time + dur
            current_time = end_t + 0.3  # small gap

            def fmt(t: float) -> str:
                hrs = int(t // 3600)
                mins = int((t % 3600) // 60)
                secs = int(t % 60)
                millis = int((t - int(t)) * 1000)
                return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

            lines.append(f"{idx}")
            lines.append(f"{fmt(start_t)} --> {fmt(end_t)}")
            lines.append(item.get("localized_text", item.get("original_text", "")))
            lines.append("")

        content = "\n".join(lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path


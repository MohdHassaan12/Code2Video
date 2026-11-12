import os
import unittest
from unittest.mock import patch, MagicMock
from adapt_manim.core.llm_client import UnifiedLLMClient


class TestUnifiedLLMClientOllama(unittest.TestCase):
    def test_ollama_initialization_defaults(self):
        client = UnifiedLLMClient(provider="ollama", model_name="llama4")
        self.assertEqual(client.provider, "ollama")
        self.assertEqual(client.model_name, "llama4")
        self.assertEqual(client.base_url, "http://localhost:11434")

    def test_ollama_env_detection(self):
        with patch.dict(os.environ, {"OLLAMA_MODEL": "llama4", "OLLAMA_HOST": "http://127.0.0.1:11434"}):
            client = UnifiedLLMClient()
            self.assertEqual(client.provider, "ollama")
            self.assertEqual(client.model_name, "llama4")
            self.assertEqual(client.base_url, "http://127.0.0.1:11434")

    @patch("urllib.request.urlopen")
    def test_ollama_generate_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"response": "```python\\nclass Scene(Scene): pass\\n```"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = UnifiedLLMClient(provider="ollama", model_name="llama4")
        resp = client.generate("Write a Manim scene")
        self.assertIn("Scene", resp)

    def test_ollama_connection_error_raises_clear_message(self):
        client = UnifiedLLMClient(provider="ollama", model_name="llama4", base_url="http://invalid-host:11434")
        with self.assertRaises(RuntimeError) as ctx:
            client.generate("Hello")
        self.assertIn("Failed to connect to Ollama", str(ctx.exception))

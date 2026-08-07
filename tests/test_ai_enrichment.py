import unittest
from unittest.mock import Mock, patch

from app import company_enrichment
from app.routers.ai import _call_ai_provider, _chat_output_text, _openai_output_text


class AIResponseParsingTests(unittest.TestCase):
    def test_openai_accepts_direct_output_text(self):
        self.assertEqual(_openai_output_text({"output_text": "  result  "}), "result")

    def test_chat_accepts_multimodal_text_parts(self):
        payload = {"choices": [{"message": {"content": [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]}}]}
        self.assertEqual(_chat_output_text(payload, "test"), "first\nsecond")

    def test_chat_reports_missing_content(self):
        with self.assertRaisesRegex(ValueError, "没有消息内容"):
            _chat_output_text({"choices": []}, "test")

    def test_deepseek_and_kimi_success_responses_have_provider_label(self):
        response = Mock(ok=True)
        response.json.return_value = {
            "choices": [{"message": {"content": "recognized"}}]
        }
        with (
            patch(
                "app.routers.ai.ai_provider_utils.validate_public_base_url",
                return_value="https://api.example.com/v1",
            ),
            patch("app.routers.ai.requests.post", return_value=response),
        ):
            for provider in ("deepseek", "kimi"):
                with self.subTest(provider=provider):
                    self.assertEqual(
                        _call_ai_provider(provider, "key", "model", "system", "mail"),
                        "recognized",
                    )


class EnrichmentParsingTests(unittest.TestCase):
    def test_extracts_json_from_surrounding_fenced_response(self):
        result = company_enrichment.parse_result(
            '说明如下：\n```json\n{"company_type":"芯片","directions":["Linux"],"note_append":"","sources":[]}\n```',
            [],
            allow_empty=True,
        )
        self.assertEqual(result["company_type"], "芯片")
        self.assertEqual(result["directions"], ["Linux"])

    def test_does_not_append_duplicate_note_with_another_date(self):
        existing = "[AI 知识补全 · 2026-07-31]\n主营芯片设计。"
        result = {
            "note_append": "主营芯片设计。",
            "sources": [],
            "knowledge_based": True,
        }
        self.assertEqual(company_enrichment.appended_note(existing, result, "2026-08-01"), existing)


if __name__ == "__main__":
    unittest.main()

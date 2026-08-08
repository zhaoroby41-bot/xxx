import json
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from scripts.ai_contract import validate_ai_result
from scripts.ai_generation import build_rule_fallback, generate_ai_insights
from scripts.insight_evidence import REQUIRED_MODULES


def packet(period="2026-07", role="dealer"):
    return {
        "role": role,
        "period": {"calendar_month": period},
        "data_scope": {"allowed_entity_ids": ["dealer-1"]},
        "module_status": {module: "ready" for module in REQUIRED_MODULES},
        "evidence": [
            {
                "evidence_id": f"ev-{module}", "module": module, "metric": "observed_signal",
                "value": 0.5, "comparison": None, "scope": {"entity_ids": ["dealer-1"]}, "sample_size": 1,
            }
            for module in REQUIRED_MODULES
        ],
    }


def valid_result(source_packet, mode="ai"):
    result = build_rule_fallback(source_packet)
    result["generation"] = {"mode": mode}
    return validate_ai_result(result, source_packet, {"dealer-1"})


def write_cache(path, source_packet, result):
    path.write_text(json.dumps({
        "cache_version": 1, "role": source_packet["role"],
        "calendar_month": source_packet["period"]["calendar_month"], "result": result,
    }, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return path


def ai_env():
    return {"INSIGHT_AI_API_KEY": "secret-token", "INSIGHT_AI_MODEL": "demo-model"}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class AIGenerationTests(unittest.TestCase):
    def test_provider_success_returns_ai_mode_writes_cache_and_keeps_secret_private(self):
        captured = {}
        source_packet = packet()

        def transport(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["authorization"] = request.get_header("Authorization")
            return FakeResponse({"choices": [{"message": {"content": json.dumps(valid_result(source_packet))}}]})

        cache_path = self.tmp_path / "ai.json"
        result = generate_ai_insights(source_packet, cache_path=cache_path, env=ai_env(), transport=transport)

        self.assertEqual(result["generation"]["mode"], "ai")
        self.assertTrue(cache_path.exists())
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})
        self.assertEqual(captured["body"]["messages"][0]["role"], "system")
        self.assertEqual(captured["body"]["messages"][1]["content"], "Analyze only this dealer. Never compare with or name another dealer.")
        self.assertEqual(json.loads(captured["body"]["messages"][2]["content"]), source_packet)
        self.assertEqual(captured["authorization"], "Bearer secret-token")
        self.assertNotIn("secret-token", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("secret-token", cache_path.read_text(encoding="utf-8"))

    def test_provider_echoed_secret_is_redacted_before_cache_and_return(self):
        source_packet = packet()
        provider_result = valid_result(source_packet)
        provider_result["generation"]["provider_note"] = "secret-token"

        def transport(request, timeout):
            return FakeResponse({"choices": [{"message": {"content": json.dumps(provider_result)}}]})

        cache_path = self.tmp_path / "ai.json"
        result = generate_ai_insights(source_packet, cache_path=cache_path, env=ai_env(), transport=transport)

        self.assertNotIn("secret-token", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("secret-token", cache_path.read_text(encoding="utf-8"))

    def test_provider_echoed_secret_in_field_name_is_redacted(self):
        source_packet = packet()
        provider_result = valid_result(source_packet)
        provider_result["generation"]["secret-token-field"] = "provider echo"

        def transport(request, timeout):
            return FakeResponse({"choices": [{"message": {"content": json.dumps(provider_result)}}]})

        cache_path = self.tmp_path / "ai.json"
        result = generate_ai_insights(source_packet, cache_path=cache_path, env=ai_env(), transport=transport)

        self.assertNotIn("secret-token", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("secret-token", cache_path.read_text(encoding="utf-8"))

    def test_no_key_uses_valid_same_month_cache(self):
        source_packet = packet()
        cache = write_cache(self.tmp_path / "ai.json", source_packet, valid_result(source_packet))
        result = generate_ai_insights(source_packet, cache_path=cache, env={})
        self.assertEqual(result["generation"]["mode"], "cached_ai")

    def test_no_key_without_cache_uses_rule_fallback_for_all_ready_modules(self):
        source_packet = packet()
        result = generate_ai_insights(source_packet, cache_path=self.tmp_path / "missing.json", env={})
        self.assertEqual(result["generation"]["mode"], "rule_fallback")
        self.assertEqual({item["module"] for item in result["insights"]}, set(REQUIRED_MODULES))
        validate_ai_result(result, source_packet, {"dealer-1"})

    def test_rule_fallback_selects_higher_priority_available_evidence(self):
        source_packet = packet()
        source_packet["evidence"] = [
            {
                "evidence_id": "low-first",
                "module": "growth_diagnosis",
                "metric": "low",
                "value": 0.1,
                "comparison": None,
                "scope": {"entity_ids": ["dealer-1"]},
                "sample_size": 1,
                "confidence": "validate",
            },
            {
                "evidence_id": "high-second",
                "module": "growth_diagnosis",
                "metric": "high",
                "value": 0.2,
                "comparison": None,
                "scope": {"entity_ids": ["dealer-1"]},
                "sample_size": 10,
                "confidence": "supported",
            },
        ] + [row for row in packet()["evidence"] if row["module"] != "growth_diagnosis"]

        result = generate_ai_insights(source_packet, cache_path=self.tmp_path / "missing.json", env={})
        growth = next(item for item in result["insights"] if item["module"] == "growth_diagnosis")

        self.assertEqual(growth["evidence_ids"], ["high-second"])
        self.assertIn("1", growth["actions"][0]["success_metric"])

    def test_provider_contract_failure_falls_back_to_valid_cache(self):
        source_packet = packet()
        cache = write_cache(self.tmp_path / "ai.json", source_packet, valid_result(source_packet))

        def invalid_transport(request, timeout):
            return FakeResponse({"choices": [{"message": {"content": "{}"}}]})

        result = generate_ai_insights(source_packet, cache_path=cache, env=ai_env(), transport=invalid_transport)
        self.assertEqual(result["generation"]["mode"], "cached_ai")

    def test_provider_exception_falls_back_to_valid_cache(self):
        source_packet = packet()
        cache = write_cache(self.tmp_path / "ai.json", source_packet, valid_result(source_packet))

        def failing_transport(request, timeout):
            raise OSError("provider unavailable")

        result = generate_ai_insights(source_packet, cache_path=cache, env=ai_env(), transport=failing_transport)
        self.assertEqual(result["generation"]["mode"], "cached_ai")

    def test_other_month_cache_is_not_reused(self):
        old_packet = packet(period="2026-06")
        cache = write_cache(self.tmp_path / "ai.json", old_packet, valid_result(old_packet))
        result = generate_ai_insights(packet(period="2026-07"), cache_path=cache, env={})
        self.assertEqual(result["generation"]["mode"], "rule_fallback")

    def test_invalid_cache_is_not_reused(self):
        source_packet = packet()
        invalid = valid_result(source_packet)
        invalid["insights"][0]["evidence_ids"] = ["unknown"]
        cache = write_cache(self.tmp_path / "ai.json", source_packet, invalid)
        result = generate_ai_insights(source_packet, cache_path=cache, env={})
        self.assertEqual(result["generation"]["mode"], "rule_fallback")

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()


if __name__ == "__main__":
    unittest.main()

import copy
import json
import math
import sys
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from scripts.ai_contract import AIContractError, validate_ai_result


def evidence_packet():
    return {
        "module_status": {
            "growth_diagnosis": "ready",
            "matrix_health": "insufficient_data",
            "content_patterns": "insufficient_data",
            "user_signals": "insufficient_data",
            "regional_strategy": "insufficient_data",
            "action_plan": "insufficient_data",
            "business_opportunities": "insufficient_data",
        },
        "evidence": [
            {
                "evidence_id": "ev-1",
                "module": "growth_diagnosis",
                "metric": "reads_change",
                "value": 0.25,
                "comparison": {"baseline": 100},
                "scope": {"entity_ids": ["dealer-1"]},
                "sample_size": 4,
            },
            {
                "evidence_id": "ev-other",
                "module": "matrix_health",
                "metric": "concentration",
                "value": 0.5,
                "comparison": None,
                "scope": {},
                "sample_size": 2,
            },
        ],
    }


def valid_ai_result():
    return {
        "executive_summary": "增长诊断已完成。",
        "generation": {"mode": "test"},
        "insights": [
            {
                "id": "growth-1",
                "module": "growth_diagnosis",
                "title": "增长机会",
                "judgement": "阅读增长25%。",
                "why": "基线为100。",
                "impact": "样本覆盖4个账户。",
                "statement_type": "inference",
                "evidence_ids": ["ev-1"],
                "confidence": "high",
                "scope": {"entity_ids": ["dealer-1"]},
                "actions": [
                    {
                        "owner": "运营",
                        "action": "放大有效内容",
                        "deadline": "下周",
                        "success_metric": "阅读增长",
                    }
                ],
            }
        ],
    }


class AIContractTests(unittest.TestCase):
    def test_valid_result_preserves_evidence_links(self):
        result = validate_ai_result(valid_ai_result(), evidence_packet(), {"dealer-1", "account-1"})
        self.assertEqual(result["insights"][0]["evidence_ids"], ["ev-1"])

    def test_unknown_evidence_id_is_rejected(self):
        value = valid_ai_result()
        value["insights"][0]["evidence_ids"] = ["made-up"]
        with self.assertRaisesRegex(AIContractError, "unknown_evidence"):
            validate_ai_result(value, evidence_packet(), {"dealer-1"})

    def test_unknown_entity_is_rejected(self):
        value = valid_ai_result()
        value["insights"][0]["scope"]["entity_ids"] = ["peer-dealer"]
        with self.assertRaisesRegex(AIContractError, "unknown_entity"):
            validate_ai_result(value, evidence_packet(), {"dealer-1"})

    def test_nested_action_entity_is_rejected(self):
        value = valid_ai_result()
        value["insights"][0]["actions"][0]["scope"] = {"entity_ids": ["peer-account"]}
        with self.assertRaisesRegex(AIContractError, "unknown_entity"):
            validate_ai_result(value, evidence_packet(), {"dealer-1"})

    def test_unlinked_numeric_claim_is_rejected(self):
        value = valid_ai_result()
        value["insights"][0]["judgement"] = "阅读增长99%。"
        with self.assertRaisesRegex(AIContractError, "unsupported_number"):
            validate_ai_result(value, evidence_packet(), {"dealer-1"})

    def test_action_requires_owner_deadline_and_metric(self):
        value = valid_ai_result()
        value["insights"][0]["actions"] = [{"action": "增加场景内容"}]
        with self.assertRaisesRegex(AIContractError, "incomplete_action"):
            validate_ai_result(value, evidence_packet(), {"dealer-1"})

    def test_invalid_module_statement_type_and_confidence_are_rejected(self):
        value = valid_ai_result()
        value["insights"][0]["module"] = "not-a-module"
        value["insights"][0]["statement_type"] = "opinion"
        value["insights"][0]["confidence"] = "certain"
        with self.assertRaises(AIContractError) as raised:
            validate_ai_result(value, evidence_packet(), {"dealer-1"})
        self.assertTrue({"invalid_module", "invalid_statement_type", "invalid_confidence"} <= set(raised.exception.errors))

    def test_ready_module_requires_corresponding_insight(self):
        packet = evidence_packet()
        packet["module_status"]["content_patterns"] = "ready"
        with self.assertRaisesRegex(AIContractError, "missing_ready_module_insight"):
            validate_ai_result(valid_ai_result(), packet, {"dealer-1"})

    def test_insight_cannot_cite_evidence_from_another_module(self):
        value = valid_ai_result()
        value["insights"][0]["evidence_ids"] = ["ev-other"]
        with self.assertRaisesRegex(AIContractError, "cross_module_evidence"):
            validate_ai_result(value, evidence_packet(), {"dealer-1"})

    def test_result_and_input_are_not_mutated_and_normalized_is_strict_json(self):
        value = valid_ai_result()
        original = copy.deepcopy(value)
        result = validate_ai_result(value, evidence_packet(), {"dealer-1"})
        result["insights"][0]["title"] = "已变更"
        self.assertEqual(value, original)
        self.assertEqual(value["insights"][0]["title"], "增长机会")
        self.assertNotEqual(result["insights"][0]["title"], value["insights"][0]["title"])
        json.dumps(validate_ai_result(value, evidence_packet(), {"dealer-1"}), allow_nan=False)

    def test_nan_and_infinity_are_rejected(self):
        for bad_number in (math.nan, math.inf):
            value = valid_ai_result()
            value["generation"]["latency"] = bad_number
            with self.assertRaisesRegex(AIContractError, "non_finite_number"):
                validate_ai_result(value, evidence_packet(), {"dealer-1"})


if __name__ == "__main__":
    unittest.main()

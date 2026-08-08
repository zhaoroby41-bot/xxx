import copy
import json
import math
import sys
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from scripts.insight_evidence import REQUIRED_MODULES, build_evidence_packet


def period_fixture():
    return {
        "calendar_month": "2026-07",
        "fiscal_year": "FY26",
        "fiscal_quarter": "Q4",
        "fiscal_month": 1,
    }


def history_fixture():
    return {
        "previous_month": {"month": "2026-06", "reads": 800, "interactions": 80, "new_fans": 8},
        "year_ago": {"month": "2025-07", "reads": 700, "interactions": 70, "new_fans": 7},
        "rolling_baseline": {"reads": 750, "interactions": 75, "new_fans": 7.5},
        "comparisons": {
            "previous_month": {"reads": {"ratio_change": 0.25}, "interactions": {"ratio_change": 0.2}, "new_fans": {"ratio_change": 0.25}},
            "year_ago": {"reads": {"ratio_change": 0.43}, "interactions": {"ratio_change": 0.37}, "new_fans": {"ratio_change": 0.43}},
            "rolling_baseline": {"reads": {"ratio_change": 1 / 3}, "interactions": {"ratio_change": 0.28}, "new_fans": {"ratio_change": 1 / 3}},
        },
        "coverage": {"first_month": "2025-07", "months": 12},
    }


def dealer_fixture():
    return {
        "source_month": "2026-07",
        "quality": {"quality_status": "ready", "errors": []},
        "dealer": {
            "dealer_id": "dealer-a", "name": "Dealer A", "cohort": "core_kpi",
            "accounts": [
                {"author_id": "core-1", "account_name": "Shanghai Account", "city": "Shanghai", "region": "East", "confidence": "confirmed", "cohort": "core_kpi", "metrics": {"reads": 600, "likes": 60, "collects": 30, "comments": 10, "shares": 5, "new_fans": 6}},
                {"author_id": "store-1", "account_name": "Shanghai Store", "city": "Shanghai", "region": "East", "confidence": "confirmed", "cohort": "expanded_store", "metrics": {"reads": 400, "likes": 20, "collects": 20, "comments": 10, "shares": 2, "new_fans": 4}},
            ],
            "kpi": {
                "elapsed_ratio": 1 / 3,
                "reads": {"actual": 600, "target": 2700, "completion_rate": 2 / 9, "pacing_gap": -1 / 9},
                "interactions": {"actual": 100, "target": 270, "completion_rate": 10 / 27, "pacing_gap": 1 / 27},
                "fans": {"actual": 6, "target": 27, "completion_rate": 2 / 9, "pacing_gap": -1 / 9},
                "account_statuses": [{"author_id": "core-1", "status": "warning"}],
            },
            "expanded_store_metrics": {"reads": 400, "notes": 2, "interactions": 50, "new_fans": 4},
            "content": {
                "notes": 5, "reads": 1000, "interactions": 150, "shares": 7, "new_fans": 10,
                "reads_per_note": 200, "interaction_rate": 0.15, "fans_per_10k_reads": 100,
                "image_share": 0.6, "video_share": 0.4,
                "categories": [
                    {"category": "promotion", "notes": 3, "note_share": 0.6, "reads": 800, "reads_per_note": 266.67, "interaction_rate": 0.16, "mapping_completeness": 1, "benchmark_note_share": 0.5, "benchmark_reads_per_note": 220, "benchmark_confidence": "supported"},
                    {"category": "service", "notes": 2, "note_share": 0.4, "reads": 200, "reads_per_note": 100, "interaction_rate": 0.1, "mapping_completeness": 1, "benchmark_note_share": 0.5, "benchmark_reads_per_note": 220, "benchmark_confidence": "supported"},
                ],
                "by_city_cohort": [{"city": "Shanghai", "region": "East", "cohort": "core_kpi", "content": {"notes": 3, "reads": 600, "reads_per_note": 200, "categories": [{"category": "promotion", "notes": 3, "reads_per_note": 200}]}}],
            },
            "recommendations": [{"id": "action-1", "rule_id": "category_scale", "type": "category", "confidence": "supported", "priority": "high", "target": {"category": "promotion", "city": "", "account_id": ""}, "evidence": [{"metric": "reads_per_note", "value": 266.67, "benchmark": 220}]}],
        },
    }


def apple_fixture():
    dealer = dealer_fixture()["dealer"]
    return {
        "source_month": "2026-07",
        "quality": {"quality_status": "ready", "errors": []},
        "apple": {
            "network_kpis": copy.deepcopy(dealer["kpi"]),
            "account_counts": {"core_kpi": 1, "expanded_store": 1},
            "dealer_quadrants": [{"dealer_id": "dealer-a", "cohort": "core_kpi", "notes": 5, "reads_per_note": 200, "quadrant": "high_supply_high_efficiency"}],
            "city_summaries": [{"city": "Shanghai", "account_count": 2, "identified_coverage": 1}],
            "category_mix_performance": [{"region": "East", "cohort": "core_kpi", "category": "promotion", "notes": 3, "reads": 800, "reads_per_note": 266.67, "interaction_rate": 0.16}],
            "actions": {"immediate": [{"id": "network-action-1", "rule_id": "category_scale", "confidence": "supported", "priority": "high", "category": "promotion", "affected_dealer_count": 1, "affected_account_count": 1, "evidence": [{"metric": "recommendation_count", "value": 1}]}]},
            "replicable_cases": {"city": [{"city": "Shanghai", "region": "East", "cohort": "core_kpi", "dealer_ids": ["dealer-a"], "evidence": [{"metric": "reads_per_note", "value": 200, "benchmark": 150}]}]},
        },
    }


def sparse_city_fixture():
    payload = dealer_fixture()
    payload["dealer"]["accounts"] = [
        {"author_id": "sparse-1", "account_name": "Sparse Account", "city": "Small City", "region": "West", "confidence": "inferred", "cohort": "core_kpi", "metrics": {"reads": 10, "likes": 1, "collects": 1, "comments": 0, "shares": 0, "new_fans": 0}},
    ]
    payload["dealer"]["content"]["by_city_cohort"] = [{"city": "Small City", "region": "West", "cohort": "core_kpi", "content": {"notes": 1, "reads": 10, "reads_per_note": 10, "categories": []}}]
    return payload


def apple_fixture_with_scoped_city_data():
    payload = apple_fixture()
    payload["dealers"] = [dealer_fixture()["dealer"]]
    return payload


class InsightEvidenceTests(unittest.TestCase):
    def test_packet_covers_every_legacy_analysis_domain(self):
        packet = build_evidence_packet("dealer", dealer_fixture(), history_fixture(), period_fixture())
        self.assertEqual(set(packet["module_status"]), set(REQUIRED_MODULES))
        self.assertEqual({row["module"] for row in packet["evidence"]}, set(REQUIRED_MODULES))

    def test_growth_evidence_contains_history_and_fiscal_pacing(self):
        packet = build_evidence_packet("dealer", dealer_fixture(), history_fixture(), period_fixture())
        metrics = {row["metric"] for row in packet["evidence"] if row["module"] == "growth_diagnosis"}
        self.assertTrue({"reads_change_vs_previous", "reads_change_vs_baseline", "q4_reads_pacing_gap"} <= metrics)

    def test_content_patterns_separate_viral_long_tail_and_hotspot_notes(self):
        rows = build_evidence_packet("apple", apple_fixture(), history_fixture(), period_fixture())["evidence"]
        pattern_types = {row["scope"].get("pattern_type") for row in rows if row["module"] == "content_patterns"}
        self.assertTrue({"viral", "long_tail", "hotspot"} <= pattern_types)

    def test_matrix_health_includes_concentration_and_quadrants(self):
        rows = build_evidence_packet("apple", apple_fixture(), history_fixture(), period_fixture())["evidence"]
        metrics = {row["metric"] for row in rows if row["module"] == "matrix_health"}
        self.assertTrue({"top_20_read_share", "quadrant_distribution", "content_homogeneity"} <= metrics)

    def test_dealer_packet_never_contains_peer_identity(self):
        packet = build_evidence_packet("dealer", dealer_fixture(), history_fixture(), period_fixture())
        self.assertNotIn("PEER_DEALER_NAME", json.dumps(packet, ensure_ascii=False))

    def test_sparse_city_is_validate_confidence_not_supported(self):
        packet = build_evidence_packet("dealer", sparse_city_fixture(), history_fixture(), period_fixture())
        city_rows = [row for row in packet["evidence"] if row["module"] == "regional_strategy"]
        self.assertTrue(city_rows)
        self.assertTrue(all(row["confidence"] == "validate" for row in city_rows))

    def test_packet_is_json_safe_and_does_not_mutate_inputs(self):
        payload = dealer_fixture()
        original = copy.deepcopy(payload)
        packet = build_evidence_packet("dealer", payload, history_fixture(), period_fixture())
        json.dumps(packet, ensure_ascii=False, allow_nan=False)
        self.assertEqual(payload, original)
        self.assertTrue(all(not isinstance(row["value"], float) or math.isfinite(row["value"]) for row in packet["evidence"]))

    def test_empty_scope_marks_each_module_insufficient_without_omitting_it(self):
        packet = build_evidence_packet("dealer", {"source_month": "2026-07", "dealer": {"dealer_id": "empty"}}, {}, period_fixture())
        self.assertEqual(set(packet["module_status"].values()), {"insufficient_data"})
        self.assertEqual({row["module"] for row in packet["evidence"]}, set(REQUIRED_MODULES))

    def test_apple_city_summary_without_numeric_basis_is_insufficient_not_null_ready_evidence(self):
        packet = build_evidence_packet("apple", apple_fixture(), history_fixture(), period_fixture())
        rows = [row for row in packet["evidence"] if row["module"] == "regional_strategy"]
        self.assertEqual(packet["module_status"]["regional_strategy"], "insufficient_data")
        self.assertTrue(all(row["scope"].get("availability") == "insufficient_data" for row in rows))
        self.assertTrue(all(row["value"] is not None for row in rows))

    def test_apple_city_evidence_uses_scoped_account_and_city_content_data_when_available(self):
        packet = build_evidence_packet("apple", apple_fixture_with_scoped_city_data(), history_fixture(), period_fixture())
        row = next(row for row in packet["evidence"] if row["metric"] == "city_content_efficiency")
        self.assertEqual(row["value"], 200)
        self.assertEqual(row["sample_size"], 1)
        self.assertEqual(row["confidence"], "validate")
        self.assertEqual(row["scope"]["recommendation_mode"], "test_only")

    def test_aggregate_content_evidence_is_explicit_about_missing_note_level_rows(self):
        rows = build_evidence_packet("apple", apple_fixture(), history_fixture(), period_fixture())["evidence"]
        content_rows = [row for row in rows if row["module"] == "content_patterns"]
        self.assertTrue(any(row["metric"] == "aggregate_reads_per_note" for row in content_rows))
        self.assertFalse(any(row["metric"] == "hotspot_recency_days" for row in content_rows))
        hotspot = next(row for row in content_rows if row["scope"].get("pattern_type") == "hotspot")
        self.assertEqual(hotspot["scope"]["availability"], "insufficient_data")
        self.assertTrue(all(row["value"] is not None for row in content_rows))

    def test_hotspot_recency_uses_source_month_end(self):
        payload = dealer_fixture()
        payload["dealer"]["notes"] = [{"note_id": "recent", "title": "Recent", "reads": 100, "publish_date": "2026-07-30"}]
        rows = build_evidence_packet("dealer", payload, history_fixture(), period_fixture())["evidence"]
        hotspot = next(row for row in rows if row["metric"] == "hotspot_recency_days")
        self.assertEqual(hotspot["value"], 1)

    def test_apple_matrix_includes_category_share_similarity_posting_frequency_and_tiers(self):
        rows = build_evidence_packet("apple", apple_fixture(), history_fixture(), period_fixture())["evidence"]
        matrix_rows = [row for row in rows if row["module"] == "matrix_health"]
        metrics = {row["metric"] for row in matrix_rows}
        self.assertTrue({"category_share_similarity", "network_posting_frequency", "tier_candidate_count"} <= metrics)
        self.assertTrue(any(row["metric"] == "tier_candidate_count" and row["scope"].get("tier") == "S" for row in matrix_rows))


if __name__ == "__main__":
    unittest.main()

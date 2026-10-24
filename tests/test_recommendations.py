from unittest.mock import patch

from app.routers.recommendations import (
    _attach_added_status, _candidate, _grade_for_score, _normalize_run_result_grades,
    _result_payload, _select_run_records,
)


def test_grade_is_derived_from_score_boundaries():
    assert [_grade_for_score(score) for score in (100, 90, 89, 75, 74, 60, 59, 0)] == [
        "S", "S", "A", "A", "B", "B", "C", "C",
    ]


def test_legacy_history_grade_is_normalized_when_read():
    run = {"result": {"items": [{"recommendation_score": 92, "recommendation_grade": "A"}]}}

    normalized = _normalize_run_result_grades(run)

    assert normalized["result"]["items"][0]["recommendation_grade"] == "S"


def test_history_result_includes_current_added_status():
    run = {"result": {"items": [
        {"record_id": "added", "is_added": False},
        {"record_id": "missing", "is_added": True},
    ]}}
    shared = [{"record_id": "added", "is_added": True}]

    with patch("app.routers.recommendations.local_records.list_shared_records", return_value=shared):
        enriched = _attach_added_status(run, 7)

    assert enriched["result"]["items"][0]["is_added"] is True
    assert enriched["result"]["items"][1]["is_added"] is False


def test_candidate_works_with_company_and_job_only():
    payload = _candidate({
        "record_id": "rec1",
        "company": "示例科技",
        "job": "嵌入式软件工程师",
    })

    assert payload["company"] == "示例科技"
    assert payload["job"] == "嵌入式软件工程师"
    assert payload["city_hint"] == ""
    assert payload["direction_hints"] == []


def test_result_keeps_role_profile_and_resume_evidence():
    records = [{"record_id": "rec1", "company": "示例科技", "job": "固件工程师"}]
    ranked = {"rec1": {
        "score": 82,
        "grade": "A",
        "reason": "C语言项目匹配，驱动经验不足",
        "role_summary": "嵌入式固件开发（模型推断）",
        "work_content": ["固件开发", "硬件联调"],
        "likely_requirements": ["C语言", "MCU"],
        "likely_tech_stack": ["C", "RTOS"],
        "compensation": "未核实；同类岗位通常为当地中等水平",
        "profile_confidence": "high",
        "match_strengths": ["有C语言项目证据"],
        "match_gaps": ["未体现驱动开发"],
    }}

    result = _result_payload(
        records, ranked, {"recommendation_min_score": 45, "recommendation_limit": 12},
        "deepseek", "model", True,
    )

    item = result["items"][0]
    assert item["ai_role_profile"]["work_content"] == ["固件开发", "硬件联调"]
    assert item["ai_role_profile"]["confidence"] == "low"
    assert item["match_strengths"] == ["有C语言项目证据"]


def test_incremental_result_merges_old_items_and_tracks_all_evaluated_ids():
    old_item = {
        "record_id": "old", "recommendation_score": 70,
        "recommendation_grade": "B", "company": "旧公司", "job": "旧岗位",
    }
    records = [{"record_id": "new", "company": "新公司", "job": "新岗位"}]
    ranked = {"new": {"score": 88, "grade": "A", "reason": "匹配"}}

    result = _result_payload(
        records, ranked, {"recommendation_min_score": 45, "recommendation_limit": 12},
        "deepseek", "model", False, seed_items=[old_item],
        prior_evaluated_ids=["old", "rejected"],
    )

    assert [item["record_id"] for item in result["items"]] == ["new", "old"]
    assert result["evaluated_record_ids"] == ["old", "rejected", "new"]


def test_incremental_result_is_sorted_by_score_after_merging():
    seed_items = [
        {"record_id": "old-low", "recommendation_score": 60},
        {"record_id": "old-high", "recommendation_score": 95},
    ]
    records = [
        {"record_id": "new-mid", "company": "新公司", "job": "新岗位"},
    ]
    ranked = {"new-mid": {"score": 80, "grade": "A", "reason": "匹配"}}

    result = _result_payload(
        records, ranked, {"recommendation_min_score": 45, "recommendation_limit": 12},
        "deepseek", "model", False, seed_items=seed_items,
    )

    assert [item["record_id"] for item in result["items"]] == [
        "old-high", "new-mid", "old-low",
    ]


def test_incremental_update_can_reuse_its_own_running_history_row():
    old_item = {"record_id": "old", "recommendation_score": 70}
    run = {
        "id": "history-1",
        "status": "running",
        "run_mode": "incremental",
        "base_run_id": "history-1",
        "result": {
            "items": [old_item],
            "evaluated_record_ids": ["old", "rejected"],
        },
    }
    all_records = [
        {"record_id": "old"},
        {"record_id": "rejected"},
        {"record_id": "new"},
    ]

    records, seed_items, prior_ids = _select_run_records(1, run, all_records)

    assert records == [{"record_id": "new"}]
    assert seed_items == [old_item]
    assert prior_ids == ["old", "rejected"]

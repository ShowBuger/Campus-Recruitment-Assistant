from app.routers.recommendations import _candidate, _result_payload


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

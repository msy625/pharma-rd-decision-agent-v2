from datetime import date

from deepinsight.core.normalized_institution_timeline_service import NormalizedInstitutionTimelineService


AS_OF_DATE = date(2026, 9, 30)


def test_timeline_excludes_cleared_2099_completion_placeholders():
    events = NormalizedInstitutionTimelineService(as_of_date=AS_OF_DATE).build_timeline()["events"]
    assert not any(event["date"]["value"].startswith("2099") for event in events)


def test_future_dates_are_not_presented_as_completed_or_published_events():
    events = NormalizedInstitutionTimelineService(as_of_date=AS_OF_DATE).build_timeline()["events"]
    future_events = [event for event in events if event["date"]["value"] > "2026-09-30"]
    assert future_events
    for event in future_events:
        if event["event_type"] == "study_date":
            assert event["event_type_label"].startswith("预计") or event["event_type_label"] == "未来状态更新（待核验）"
        elif event["event_type"] == "publication_date":
            assert event["event_type_label"] == "未来论文日期（待核验）"


def test_study_date_labels_do_not_overstate_past_plans_as_completed_work():
    service = NormalizedInstitutionTimelineService(as_of_date=AS_OF_DATE)
    assert service._study_date_label("completion_date", "2025-01-01", "Recruiting") == "原计划研究完成（状态待更新）"
    assert service._study_date_label("completion_date", "2025-01-01", "Completed") == "研究完成（已结束研究）"
    assert service._study_date_label("start_date", "2025-01-01", "Recruiting") == "研究开始（登记日期）"
    assert service._study_date_label("completion_date", "2027-01-01", "Recruiting") == "预计研究完成"

from model_ledger.core.observations import (
    FeedbackEvent,
    Observation,
    ValidationReport,
    ValidationRun,
)


def test_observation_defaults():
    obs = Observation(
        content="Model has no independent monitoring",
        source_type="human_reviewer",
        model_version_ref="cCRR Global/2.0.0",
    )
    assert obs.observation_id  # auto-generated UUID
    assert obs.status == "draft"
    assert obs.source_type == "human_reviewer"
    assert obs.priority is None
    assert obs.pillar is None


def test_observation_with_all_fields():
    obs = Observation(
        content="Feature drift detected",
        priority="P1",
        pillar="Input Data Validation",
        source_type="ai_agent",
        source_detail="AutoValidator run 3",
        model_version_ref="cCRR Global/2.0.0",
        status="issued",
    )
    assert obs.priority == "P1"
    assert obs.source_detail == "AutoValidator run 3"
    assert obs.status == "issued"


def test_validation_run_defaults():
    run = ValidationRun(
        source_type="ai_agent",
        model_version_ref="cCRR Global/2.0.0",
    )
    assert run.run_id
    assert run.status == "draft"
    assert run.observations == []


def test_validation_report_immutability_fields():
    report = ValidationReport(
        model_version_ref="cCRR Global/2.0.0",
        issued_observations=["obs-1", "obs-2"],
        issued_by="vignesh",
    )
    assert report.issued_at is not None
    assert len(report.issued_observations) == 2


def test_feedback_event_required_fields():
    event = FeedbackEvent(
        observation_ref="obs-123",
        verdict="remove",
        reason_code="justified_by_design",
        rationale="Model spec explicitly justifies the 60-day window",
        stage="triage",
        actor="vignesh",
    )
    assert event.event_id
    assert event.verdict == "remove"
    assert event.reason_code == "justified_by_design"


def test_feedback_event_verdict_values():
    for verdict in ("keep", "remove", "modify"):
        event = FeedbackEvent(
            observation_ref="obs-1",
            verdict=verdict,
            reason_code="test",
            rationale="test",
            stage="triage",
            actor="test",
        )
        assert event.verdict == verdict

from model_ledger.backends.memory import InMemoryBackend
from model_ledger.core.observations import (
    FeedbackEvent,
    Observation,
    ValidationReport,
    ValidationRun,
)


def test_save_and_get_observation():
    backend = InMemoryBackend()
    obs = Observation(
        content="Missing monitoring",
        source_type="human_reviewer",
        model_version_ref="fraud_detection/2.0.0",
    )
    backend.save_observation(obs)
    retrieved = backend.get_observation(obs.observation_id)
    assert retrieved is not None
    assert retrieved.content == "Missing monitoring"


def test_list_observations_by_model_version():
    backend = InMemoryBackend()
    for i in range(3):
        backend.save_observation(Observation(
            content=f"Finding {i}",
            source_type="ai_agent",
            model_version_ref="fraud_detection/2.0.0",
        ))
    backend.save_observation(Observation(
        content="Other model finding",
        source_type="human_reviewer",
        model_version_ref="credit_model/1.0.0",
    ))
    results = backend.list_observations(model_version_ref="fraud_detection/2.0.0")
    assert len(results) == 3


def test_save_and_get_validation_run():
    backend = InMemoryBackend()
    run = ValidationRun(
        source_type="ai_agent",
        model_version_ref="fraud_detection/2.0.0",
    )
    backend.save_validation_run(run)
    retrieved = backend.get_validation_run(run.run_id)
    assert retrieved is not None


def test_save_and_get_validation_report():
    backend = InMemoryBackend()
    report = ValidationReport(
        model_version_ref="fraud_detection/2.0.0",
        issued_observations=["obs-1", "obs-2"],
        issued_by="vignesh",
    )
    backend.save_validation_report(report)
    retrieved = backend.get_validation_report(report.report_id)
    assert retrieved is not None
    assert len(retrieved.issued_observations) == 2


def test_append_and_list_feedback_events():
    backend = InMemoryBackend()
    obs = Observation(
        content="Test finding",
        source_type="ai_agent",
        model_version_ref="fraud_detection/2.0.0",
    )
    backend.save_observation(obs)
    event = FeedbackEvent(
        observation_ref=obs.observation_id,
        verdict="remove",
        reason_code="justified_by_design",
        rationale="Intentional design choice",
        stage="triage",
        actor="vignesh",
    )
    backend.append_feedback_event(event)
    events = backend.list_feedback_events(observation_ref=obs.observation_id)
    assert len(events) == 1
    assert events[0].verdict == "remove"

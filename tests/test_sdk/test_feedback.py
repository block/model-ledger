from model_ledger.backends.memory import InMemoryBackend
from model_ledger.core.observations import FeedbackEvent, Observation
from model_ledger.sdk.feedback import FeedbackCorpus


def _make_backend_with_feedback():
    backend = InMemoryBackend()
    obs1 = Observation(
        observation_id="obs-1",
        content="Design weakness",
        pillar="Conceptual Soundness",
        source_type="ai_agent",
        model_version_ref="fraud_detection/2.0.0",
    )
    obs2 = Observation(
        observation_id="obs-2",
        content="Missing monitoring",
        pillar="Governance Review",
        source_type="ai_agent",
        model_version_ref="fraud_detection/2.0.0",
    )
    backend.save_observation(obs1)
    backend.save_observation(obs2)
    backend.append_feedback_event(FeedbackEvent(
        observation_ref="obs-1",
        verdict="remove",
        reason_code="justified_by_design",
        rationale="Intentional 60-day window",
        stage="triage",
        actor="vignesh",
    ))
    backend.append_feedback_event(FeedbackEvent(
        observation_ref="obs-2",
        verdict="keep",
        reason_code="valid_finding",
        rationale="Confirmed no monitoring in place",
        stage="triage",
        actor="vignesh",
    ))
    return backend


def test_query_by_verdict():
    corpus = FeedbackCorpus(_make_backend_with_feedback())
    removed = corpus.query(verdict="remove")
    assert len(removed) == 1
    assert removed[0].reason_code == "justified_by_design"


def test_query_by_reason_code():
    corpus = FeedbackCorpus(_make_backend_with_feedback())
    results = corpus.query(reason_code="justified_by_design")
    assert len(results) == 1


def test_summary_stats():
    corpus = FeedbackCorpus(_make_backend_with_feedback())
    stats = corpus.summary_stats()
    assert stats["total"] == 2
    assert stats["by_verdict"]["remove"] == 1
    assert stats["by_verdict"]["keep"] == 1
    assert stats["by_reason_code"]["justified_by_design"] == 1

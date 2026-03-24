# model-ledger Hackweek Launch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the observation/feedback schema, prepare OSS repo files, and finalize docs for the hackweek launch of model-ledger under `github.com/block`.

**Architecture:** Extend the existing v0.1.0 codebase with four new Pydantic models (Observation, ValidationRun, ValidationReport, FeedbackEvent) and a FeedbackCorpus query interface. Add OSS template files (CONTRIBUTING.md, CODEOWNERS, etc.). Docs are already drafted — final polish and sync.

**Tech Stack:** Python 3.10+, Pydantic 2.x, pytest, SQLite, uv, ruff

---

## File Map

### New files to create:
- `src/model_ledger/core/observations.py` — Observation, ValidationRun, ValidationReport, FeedbackEvent models
- `src/model_ledger/sdk/feedback.py` — FeedbackCorpus query interface
- `tests/test_core/test_observations.py` — Tests for observation models and lifecycle
- `tests/test_core/test_observation_backend.py` — Tests for observation storage
- `tests/test_sdk/test_feedback.py` — Tests for FeedbackCorpus queries
- `CONTRIBUTING.md` — Block OSS contribution guide
- `CODEOWNERS` — Project ownership
- `.github/ISSUE_TEMPLATE/bug-report.md` — Bug report template
- `.github/ISSUE_TEMPLATE/config.yml` — Issue config with Discord link

### Files to modify:
- `src/model_ledger/backends/memory.py` — Add observation/feedback storage methods to InMemoryBackend
- `docs/what-and-why.md` — Final polish pass (update test count)
- `docs/technical-design.md` — Final polish pass (verify code examples)

### Deferred to v0.2 (not in this plan):
- `src/model_ledger/backends/protocol.py` — Extend Protocol with observation methods
- `src/model_ledger/backends/sqlite.py` — SQLite observation storage
- `src/model_ledger/sdk/inventory.py` — Observation/feedback convenience methods on Inventory

---

### Task 1: Observation & Feedback Data Models

**Files:**
- Create: `src/model_ledger/core/observations.py`
- Create: `tests/test_core/test_observations.py`

- [ ] **Step 1: Write failing tests for Observation model**

```python
# tests/test_core/test_observations.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/model-ledger && python -m pytest tests/test_core/test_observations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'model_ledger.core.observations'`

- [ ] **Step 3: Implement the observation models**

```python
# src/model_ledger/core/observations.py
"""Observation and feedback models for validation lifecycle tracking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Observation(BaseModel):
    """A validation finding from any source."""

    observation_id: str = Field(default_factory=_uuid)
    content: str
    priority: str | None = None
    pillar: str | None = None

    source_type: str  # human_reviewer, ai_agent, automated_tool, manual_entry
    source_detail: str | None = None
    model_version_ref: str

    status: str = "draft"  # draft, issued, removed

    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class ValidationRun(BaseModel):
    """Groups observations from a single validation effort."""

    run_id: str = Field(default_factory=_uuid)
    timestamp: datetime = Field(default_factory=_now)
    source_type: str
    model_version_ref: str
    config_snapshot: dict[str, Any] = Field(default_factory=dict)

    observations: list[str] = Field(default_factory=list)  # observation IDs
    status: str = "draft"  # draft, superseded, final


class ValidationReport(BaseModel):
    """The published set of issued observations. Immutable after creation."""

    report_id: str = Field(default_factory=_uuid)
    model_version_ref: str
    issued_observations: list[str]  # observation IDs
    issued_at: datetime = Field(default_factory=_now)
    issued_by: str


class FeedbackEvent(BaseModel):
    """What happened to an observation and why. Append-only."""

    event_id: str = Field(default_factory=_uuid)
    observation_ref: str
    verdict: str  # keep, remove, modify
    reason_code: str
    rationale: str
    stage: str  # pipeline_filter, triage, stakeholder_review
    actor: str
    timestamp: datetime = Field(default_factory=_now)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/model-ledger && python -m pytest tests/test_core/test_observations.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/model-ledger
git add src/model_ledger/core/observations.py tests/test_core/test_observations.py
git commit -m "feat(core): add Observation, ValidationRun, ValidationReport, FeedbackEvent models"
```

---

### Task 2: Backend Protocol Extension

**Files:**
- Modify: `src/model_ledger/backends/protocol.py`
- Modify: `src/model_ledger/backends/memory.py`
- Create: `tests/test_core/test_observation_backend.py`

- [ ] **Step 1: Write failing tests for observation storage**

```python
# tests/test_core/test_observation_backend.py
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
        model_version_ref="cCRR/2.0.0",
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
            model_version_ref="cCRR/2.0.0",
        ))
    backend.save_observation(Observation(
        content="Other model finding",
        source_type="human_reviewer",
        model_version_ref="aCRR/1.0.0",
    ))
    results = backend.list_observations(model_version_ref="cCRR/2.0.0")
    assert len(results) == 3


def test_save_and_get_validation_run():
    backend = InMemoryBackend()
    run = ValidationRun(
        source_type="ai_agent",
        model_version_ref="cCRR/2.0.0",
    )
    backend.save_validation_run(run)
    retrieved = backend.get_validation_run(run.run_id)
    assert retrieved is not None


def test_save_and_get_validation_report():
    backend = InMemoryBackend()
    report = ValidationReport(
        model_version_ref="cCRR/2.0.0",
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
        model_version_ref="cCRR/2.0.0",
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/model-ledger && python -m pytest tests/test_core/test_observation_backend.py -v`
Expected: FAIL with `AttributeError: 'InMemoryBackend' object has no attribute 'save_observation'`

- [ ] **Step 3: Add observation methods to InMemoryBackend**

Add to `src/model_ledger/backends/memory.py`:

```python
# Add these imports at top
from model_ledger.core.observations import (
    FeedbackEvent,
    Observation,
    ValidationReport,
    ValidationRun,
)

# Add these to __init__:
self._observations: dict[str, Observation] = {}
self._validation_runs: dict[str, ValidationRun] = {}
self._validation_reports: dict[str, ValidationReport] = {}
self._feedback_events: list[FeedbackEvent] = []

# Add these methods:
def save_observation(self, observation: Observation) -> None:
    self._observations[observation.observation_id] = observation

def get_observation(self, observation_id: str) -> Observation | None:
    return self._observations.get(observation_id)

def list_observations(self, model_version_ref: str | None = None) -> list[Observation]:
    obs = list(self._observations.values())
    if model_version_ref:
        obs = [o for o in obs if o.model_version_ref == model_version_ref]
    return obs

def save_validation_run(self, run: ValidationRun) -> None:
    self._validation_runs[run.run_id] = run

def get_validation_run(self, run_id: str) -> ValidationRun | None:
    return self._validation_runs.get(run_id)

def save_validation_report(self, report: ValidationReport) -> None:
    self._validation_reports[report.report_id] = report

def get_validation_report(self, report_id: str) -> ValidationReport | None:
    return self._validation_reports.get(report_id)

def append_feedback_event(self, event: FeedbackEvent) -> None:
    self._feedback_events.append(event)

def list_feedback_events(self, observation_ref: str | None = None) -> list[FeedbackEvent]:
    events = self._feedback_events
    if observation_ref:
        events = [e for e in events if e.observation_ref == observation_ref]
    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/model-ledger && python -m pytest tests/test_core/test_observation_backend.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run all tests to verify no regressions**

Run: `cd ~/model-ledger && python -m pytest -v`
Expected: All tests PASS (81 existing + 11 new)

- [ ] **Step 6: Commit**

```bash
cd ~/model-ledger
git add src/model_ledger/backends/memory.py tests/test_core/test_observation_backend.py
git commit -m "feat(backends): add observation and feedback storage to InMemoryBackend"
```

---

### Task 3: FeedbackCorpus Query Interface

**Files:**
- Create: `src/model_ledger/sdk/feedback.py`
- Create: `tests/test_sdk/test_feedback.py`

- [ ] **Step 1: Write failing tests for FeedbackCorpus**

```python
# tests/test_sdk/test_feedback.py
from model_ledger.backends.memory import InMemoryBackend
from model_ledger.core.observations import FeedbackEvent, Observation
from model_ledger.sdk.feedback import FeedbackCorpus


def _make_backend_with_feedback():
    backend = InMemoryBackend()
    # Two observations, one removed, one kept
    obs1 = Observation(
        observation_id="obs-1",
        content="Design weakness",
        pillar="Conceptual Soundness",
        source_type="ai_agent",
        model_version_ref="cCRR/2.0.0",
    )
    obs2 = Observation(
        observation_id="obs-2",
        content="Missing monitoring",
        pillar="Governance Review",
        source_type="ai_agent",
        model_version_ref="cCRR/2.0.0",
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/model-ledger && python -m pytest tests/test_sdk/test_feedback.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'model_ledger.sdk.feedback'`

- [ ] **Step 3: Implement FeedbackCorpus**

```python
# src/model_ledger/sdk/feedback.py
"""FeedbackCorpus — query interface over observation feedback history."""

from __future__ import annotations

from collections import Counter
from typing import Any

from model_ledger.core.observations import FeedbackEvent


class FeedbackCorpus:
    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def query(
        self,
        *,
        verdict: str | None = None,
        reason_code: str | None = None,
        observation_ref: str | None = None,
    ) -> list[FeedbackEvent]:
        events = self._backend.list_feedback_events()
        if verdict:
            events = [e for e in events if e.verdict == verdict]
        if reason_code:
            events = [e for e in events if e.reason_code == reason_code]
        if observation_ref:
            events = [e for e in events if e.observation_ref == observation_ref]
        return events

    def summary_stats(self) -> dict[str, Any]:
        events = self._backend.list_feedback_events()
        return {
            "total": len(events),
            "by_verdict": dict(Counter(e.verdict for e in events)),
            "by_reason_code": dict(Counter(e.reason_code for e in events)),
            "by_stage": dict(Counter(e.stage for e in events)),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/model-ledger && python -m pytest tests/test_sdk/test_feedback.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `cd ~/model-ledger && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd ~/model-ledger
git add src/model_ledger/sdk/feedback.py tests/test_sdk/test_feedback.py
git commit -m "feat(sdk): add FeedbackCorpus query interface"
```

---

### Task 4: OSS Repository Files

**Files:**
- Modify: `CONTRIBUTING.md` (already exists — update with OSS-specific content)
- Create: `CODEOWNERS`
- Create: `.github/ISSUE_TEMPLATE/bug-report.md`
- Create: `.github/ISSUE_TEMPLATE/config.yml`

- [ ] **Step 1: Update CONTRIBUTING.md with Block OSS content**

Note: CONTRIBUTING.md already exists with basic setup instructions. Replace with the Block OSS version below:

```markdown
# Contributing to model-ledger

Thank you for your interest in contributing to model-ledger!

## Development Setup

```bash
# Clone the repository
git clone git@github.com:block/model-ledger.git
cd model-ledger

# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest -v

# Run linter
uv run ruff check .
uv run ruff format --check .
```

## Making Changes

1. Fork the repository and create a branch from `main`.
2. Write tests for your changes (TDD preferred).
3. Run `uv run pytest -v` and ensure all tests pass.
4. Run `uv run ruff check . && uv run ruff format .` for linting.
5. Commit with DCO sign-off: `git commit --signoff`
6. Use conventional commit format for PR titles: `feat(scope): description`

## DCO Sign-Off

All commits must include a DCO (Developer Certificate of Origin) sign-off:

```bash
git commit --signoff -m "feat(sdk): add bulk registration"
```

## Code Style

- Python 3.10+ type hints throughout
- Pydantic 2.x for data models
- ruff for linting and formatting
- pytest for testing

## Questions?

Open a discussion on GitHub or reach out on Discord.
```

- [ ] **Step 2: Create CODEOWNERS**

```
# model-ledger maintainers
* @vigneshn
```

- [ ] **Step 3: Create issue templates**

`.github/ISSUE_TEMPLATE/bug-report.md`:
```markdown
---
name: Bug Report
about: Report a bug in model-ledger
labels: bug
assignees: vigneshn
---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps or code to reproduce the behavior.

**Expected behavior**
What you expected to happen.

**Environment**
- Python version:
- model-ledger version:
- OS:
```

`.github/ISSUE_TEMPLATE/config.yml`:
```yaml
blank_issues_enabled: true
contact_links:
  - name: Questions & Support
    url: https://discord.gg/block-opensource
    about: Ask questions and get help from the community
```

- [ ] **Step 4: Commit**

```bash
cd ~/model-ledger
mkdir -p .github/ISSUE_TEMPLATE
git add CONTRIBUTING.md CODEOWNERS .github/ISSUE_TEMPLATE/
git commit -m "chore: add OSS contribution files (CONTRIBUTING, CODEOWNERS, issue templates)"
```

---

### Task 5: Final Doc Polish & Sync

**Files:**
- Modify: `docs/what-and-why.md` — update test count, verify all code references
- Modify: `docs/technical-design.md` — update test count, verify code matches implementation

- [ ] **Step 1: Update test count in What & Why**

After Tasks 1-3, the test count will be higher than 81. Update `docs/what-and-why.md` to reflect the actual count.

Run: `cd ~/model-ledger && python -m pytest --co -q | tail -1`

Replace the "81 tests" reference with the actual count.

- [ ] **Step 2: Verify Technical Design code examples match implementation**

Read through `docs/technical-design.md` and confirm the Observation/FeedbackEvent code examples match the actual implementation in `src/model_ledger/core/observations.py`.

- [ ] **Step 3: Sync both docs to Google Docs**

```bash
cd /Users/vigneshn/.claude/skills/gdrive

# Clear and rewrite What & Why
cat ~/model-ledger/docs/what-and-why.md | uv run gdrive-cli.py docs insert-markdown 1k9Suspa0Obi0li3TmVfOekUAAckZSp_CTGgdFSA6T6U

# Clear and rewrite Technical Design
cat ~/model-ledger/docs/technical-design.md | uv run gdrive-cli.py docs insert-markdown 1zUq_Hn9E23f-lHOKWOva29SPqNU7tCfMAXi7BZ6mFFA
```

- [ ] **Step 4: Commit doc updates**

```bash
cd ~/model-ledger
git add docs/
git commit -m "docs: update test counts and verify code examples match implementation"
```

---

### Task 6: OSPO Prototype Issue

This is a manual step — file the GitHub issue at `squareup/ospo`.

- [ ] **Step 1: Prepare OSPO issue content**

Use the Prototype track form at:
`https://github.com/squareup/ospo/issues/new?template=ospo-request-new-open-source-prototype-repo.yml`

Fields to fill:
- **Project name:** model-ledger
- **Short description:** A formal, open-source model inventory and governance framework for the AI era. Typed schema, executable compliance profiles, structured observation tracking.
- **License:** Apache-2.0
- **Novel ideas:** Agent-first governance infrastructure; structured feedback loop for validation observations; hierarchical I/P/O model decomposition per SR 11-7.
- **Eng manager notification:** Yes (Krish)

- [ ] **Step 2: File the issue**

Submit the form. Repo should be created immediately per Prototype track.

- [ ] **Step 3: Push code to the new repo**

```bash
cd ~/model-ledger
git remote add origin git@github.com:block/model-ledger.git
git push -u origin main
```

---

## Summary

| Task | What | Tests Added |
|------|------|-------------|
| 1 | Observation & Feedback data models | 6 |
| 2 | InMemoryBackend observation storage | 5 |
| 3 | FeedbackCorpus query interface | 3 |
| 4 | OSS repo files | 0 (config only) |
| 5 | Doc polish & Google Doc sync | 0 (docs only) |
| 6 | OSPO issue & code push | 0 (manual) |

**Total new tests:** 14
**Estimated total after plan:** ~95 tests

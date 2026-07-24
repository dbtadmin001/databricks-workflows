from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

STAGES = ("bronze", "silver", "gold")
SUCCESS = "SUCCEEDED"
HELD = "HELD"
FAILED = "FAILED"
_SHA = re.compile(r"^[0-9a-f]{7,64}$", re.IGNORECASE)


@dataclass(frozen=True)
class ExecutionIdentity:
    source_fingerprint: str
    configuration_hash: str
    code_sha: str


@dataclass(frozen=True)
class StageOutcome:
    status: str = SUCCESS
    comment: str = "Stage completed."


@dataclass(frozen=True)
class PipelineSummary:
    pipeline_run_id: str
    planned: tuple[str, ...]
    skipped: tuple[str, ...]
    completed: tuple[str, ...]
    held_stage: str | None = None


class StageLedger(Protocol):
    def latest_statuses(self, identity: ExecutionIdentity) -> Mapping[str, str]: ...

    def record(
        self,
        identity: ExecutionIdentity,
        pipeline_run_id: str,
        attempt_id: str,
        stage: str,
        status: str,
        sequence: int,
        reason_code: str,
        comment: str,
    ) -> None: ...


def stable_hash(value: Mapping[str, object]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fingerprint_files(paths: Iterable[Path], root: Path | None = None) -> str:
    files = sorted(
        (Path(path).resolve() for path in paths if Path(path).is_file()),
        key=lambda path: path.as_posix(),
    )
    if not files:
        raise ValueError("At least one source file is required for fingerprinting")
    digest = hashlib.sha256()
    base = root.resolve() if root else None
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            name = path.relative_to(base).as_posix() if base else path.name
        except ValueError:
            name = path.name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_code_sha(explicit: str | None = None) -> str:
    candidates = (explicit, os.getenv("CODE_SHA"), os.getenv("GITHUB_SHA"))
    for candidate in candidates:
        if candidate and _SHA.fullmatch(candidate.strip()):
            return candidate.strip().lower()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        result = None
    if result and _SHA.fullmatch(result.stdout.strip()):
        return result.stdout.strip().lower()
    raise ValueError("A Git code SHA is required through --code-sha, CODE_SHA, or GITHUB_SHA")


def stage_plan(
    latest_statuses: Mapping[str, str],
    *,
    from_stage: str = "bronze",
    to_stage: str = "gold",
    force_stages: Iterable[str] = (),
    resume: bool = False,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if from_stage not in STAGES or to_stage not in STAGES:
        raise ValueError(f"Stages must be one of {STAGES}")
    start = STAGES.index(from_stage)
    end = STAGES.index(to_stage)
    if start > end:
        raise ValueError("--from-stage must not come after --to-stage")
    selected = STAGES[start : end + 1]
    forced = set(force_stages)
    unknown = forced - set(STAGES)
    if unknown:
        raise ValueError(f"Unknown forced stages: {sorted(unknown)}")
    outside = forced - set(selected)
    if outside:
        raise ValueError(f"Forced stages are outside the selected range: {sorted(outside)}")
    if not resume:
        return tuple(selected), ()
    first_dirty = next(
        (
            index
            for index, stage in enumerate(selected)
            if latest_statuses.get(stage) != SUCCESS or stage in forced
        ),
        len(selected),
    )
    skipped = tuple(selected[:first_dirty])
    planned = tuple(selected[first_dirty:])
    return planned, skipped


class PipelineRunner:
    def __init__(self, ledger: StageLedger):
        self.ledger = ledger

    def run(
        self,
        identity: ExecutionIdentity,
        stage_functions: Mapping[str, Callable[[], StageOutcome | None]],
        *,
        from_stage: str = "bronze",
        to_stage: str = "gold",
        force_stages: Iterable[str] = (),
        resume: bool = False,
        pipeline_run_id: str | None = None,
    ) -> PipelineSummary:
        latest = self.ledger.latest_statuses(identity) if resume else {}
        planned, skipped = stage_plan(
            latest,
            from_stage=from_stage,
            to_stage=to_stage,
            force_stages=force_stages,
            resume=resume,
        )
        missing = set(planned) - set(stage_functions)
        if missing:
            raise ValueError(f"Missing stage functions: {sorted(missing)}")
        pipeline_run_id = pipeline_run_id or uuid.uuid4().hex
        completed: list[str] = []
        for stage in planned:
            attempt_id = uuid.uuid4().hex
            self.ledger.record(
                identity,
                pipeline_run_id,
                attempt_id,
                stage,
                "RUNNING",
                0,
                "stage_started",
                f"{stage.title()} stage started.",
            )
            try:
                outcome = stage_functions[stage]() or StageOutcome()
                if outcome.status not in {SUCCESS, HELD}:
                    raise ValueError(f"Unsupported stage outcome {outcome.status!r}")
            except Exception as exc:
                self.ledger.record(
                    identity,
                    pipeline_run_id,
                    attempt_id,
                    stage,
                    FAILED,
                    2,
                    type(exc).__name__,
                    f"{stage.title()} execution failed; correct the stage and resume this identity.",
                )
                raise
            self.ledger.record(
                identity,
                pipeline_run_id,
                attempt_id,
                stage,
                outcome.status,
                1,
                "stage_completed" if outcome.status == SUCCESS else "stage_held",
                outcome.comment,
            )
            if outcome.status == HELD:
                return PipelineSummary(
                    pipeline_run_id,
                    planned,
                    skipped,
                    tuple(completed),
                    held_stage=stage,
                )
            completed.append(stage)
        return PipelineSummary(pipeline_run_id, planned, skipped, tuple(completed))

from dataclasses import dataclass
from typing import Any


_ALLOWED_AGENTS = {"director", "architect", "programmer", "qa"}
_BASE_CONTRACT_KEYS = {
    "task_id",
    "assigned_agent",
    "ledger_required",
    "required_artifacts",
    "decision_id",
    "contract_version",
}
_ALLOWED_EXTENSION_KEYS = {"run_id", "objective_spec"}


@dataclass(frozen=True)
class TaskExecutionContract:
    task_id: int
    assigned_agent: str
    ledger_required: bool
    required_artifacts: tuple[str, ...]
    decision_id: int | None = None
    contract_version: int = 1

    def validate(self) -> None:
        if self.task_id <= 0:
            raise ValueError("contract task_id must be positive")
        if self.assigned_agent not in _ALLOWED_AGENTS:
            raise ValueError("contract assigned_agent is invalid")
        if self.ledger_required and self.assigned_agent == "programmer" and self.decision_id is None:
            raise ValueError("contract requires decision_id when ledger_required is true")
        for artifact in self.required_artifacts:
            if not artifact.startswith("projects/sandbox_project/"):
                raise ValueError("contract artifact must remain in sandbox")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "assigned_agent": self.assigned_agent,
            "ledger_required": self.ledger_required,
            "required_artifacts": list(self.required_artifacts),
            "decision_id": self.decision_id,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TaskExecutionContract":
        required = [
            "task_id",
            "assigned_agent",
            "ledger_required",
            "required_artifacts",
        ]
        for key in required:
            if key not in payload:
                raise ValueError(f"contract missing key: {key}")

        unexpected = sorted(set(payload.keys()) - (_BASE_CONTRACT_KEYS | _ALLOWED_EXTENSION_KEYS))
        if unexpected:
            raise ValueError(f"contract contains unsupported key: {unexpected[0]}")

        if "run_id" in payload and payload["run_id"] is not None:
            run_id = str(payload["run_id"]).strip()
            if not run_id:
                raise ValueError("contract run_id cannot be empty")

        if "objective_spec" in payload:
            if str(payload["assigned_agent"]) != "architect":
                raise ValueError("contract objective_spec is only allowed for architect")
            _validate_objective_spec_payload(payload["objective_spec"])

        required_artifacts_raw = payload["required_artifacts"]
        if not isinstance(required_artifacts_raw, list):
            raise ValueError("contract required_artifacts must be list")

        contract = cls(
            task_id=int(payload["task_id"]),
            assigned_agent=str(payload["assigned_agent"]),
            ledger_required=bool(payload["ledger_required"]),
            required_artifacts=tuple(str(item) for item in required_artifacts_raw),
            decision_id=int(payload["decision_id"]) if payload.get("decision_id") is not None else None,
            contract_version=int(payload.get("contract_version", 1)),
        )
        contract.validate()
        return contract


@dataclass(frozen=True)
class ArtifactSpec:
    path: str
    kind: str
    owner_agent: str

    def validate(self) -> None:
        if not self.path.startswith("projects/sandbox_project/"):
            raise ValueError("artifact path must remain in sandbox")
        if self.owner_agent not in _ALLOWED_AGENTS:
            raise ValueError("artifact owner_agent is invalid")
        if self.kind not in {"project", "scene", "script"}:
            raise ValueError("artifact kind must be project|scene|script")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "owner_agent": self.owner_agent,
        }


@dataclass(frozen=True)
class AcceptanceSpec:
    description: str
    checks: tuple[str, ...]

    def validate(self) -> None:
        if not self.description.strip():
            raise ValueError("acceptance description is required")
        if not self.checks:
            raise ValueError("acceptance checks are required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "checks": list(self.checks),
        }


@dataclass(frozen=True)
class ObjectiveSpec:
    objective: str
    objective_type: str
    artifacts: tuple[ArtifactSpec, ...]
    acceptance: AcceptanceSpec
    spec_version: int = 1

    def validate(self) -> None:
        if not self.objective.strip():
            raise ValueError("objective is required")
        if self.objective_type not in {"godot-2d", "general"}:
            raise ValueError("objective_type is invalid")
        if not self.artifacts:
            raise ValueError("at least one artifact is required")
        for artifact in self.artifacts:
            artifact.validate()
        self.acceptance.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "objective_type": self.objective_type,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "acceptance": self.acceptance.to_dict(),
            "spec_version": self.spec_version,
        }


def _validate_objective_spec_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("contract objective_spec must be object")

    required = {"objective", "objective_type", "artifacts", "acceptance", "spec_version"}
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"contract objective_spec missing key: {missing[0]}")

    artifacts_raw = payload["artifacts"]
    if not isinstance(artifacts_raw, list):
        raise ValueError("contract objective_spec artifacts must be list")

    artifacts: list[ArtifactSpec] = []
    for item in artifacts_raw:
        if not isinstance(item, dict):
            raise ValueError("contract objective_spec artifact entry must be object")
        artifact = ArtifactSpec(
            path=str(item.get("path", "")),
            kind=str(item.get("kind", "")),
            owner_agent=str(item.get("owner_agent", "")),
        )
        artifact.validate()
        artifacts.append(artifact)

    acceptance_raw = payload["acceptance"]
    if not isinstance(acceptance_raw, dict):
        raise ValueError("contract objective_spec acceptance must be object")

    checks_raw = acceptance_raw.get("checks")
    if not isinstance(checks_raw, list):
        raise ValueError("contract objective_spec acceptance checks must be list")

    acceptance = AcceptanceSpec(
        description=str(acceptance_raw.get("description", "")).strip(),
        checks=tuple(str(item) for item in checks_raw),
    )

    spec = ObjectiveSpec(
        objective=str(payload["objective"]),
        objective_type=str(payload["objective_type"]),
        artifacts=tuple(artifacts),
        acceptance=acceptance,
        spec_version=int(payload["spec_version"]),
    )
    spec.validate()

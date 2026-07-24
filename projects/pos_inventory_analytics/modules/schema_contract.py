from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class FieldContract:
    data_type: str
    nullable: bool


@dataclass(frozen=True)
class ObservedField:
    name: str
    data_type: str
    nullable: bool


@dataclass(frozen=True)
class LayerContract:
    layer: str
    version: int
    required_fields: Mapping[str, FieldContract]
    additive_columns: Mapping[str, FieldContract]
    declared_renames: Mapping[str, str]

    @property
    def field_order(self) -> tuple[str, ...]:
        return tuple(self.required_fields) + tuple(self.additive_columns)

    def publication_columns(self, observed_names: Iterable[str]) -> tuple[str, ...]:
        observed = set(observed_names)
        return tuple(name for name in self.field_order if name in observed)


@dataclass(frozen=True)
class SchemaDifference:
    severity: str
    code: str
    field: str
    expected: str
    observed: str
    message: str


@dataclass(frozen=True)
class SchemaDiffReport:
    layer: str
    contract_version: int
    differences: tuple[SchemaDifference, ...]

    @property
    def compatible(self) -> bool:
        return not any(item.severity == "ERROR" for item in self.differences)

    def render(self) -> str:
        result = "COMPATIBLE" if self.compatible else "REJECTED"
        lines = [
            f"Schema contract: {self.layer} v{self.contract_version}",
            f"Result: {result}",
            "Differences:",
        ]
        if not self.differences:
            lines.append("- [INFO] NO_SCHEMA_DIFFERENCE: candidate matches the contract.")
        else:
            lines.extend(
                f"- [{item.severity}] {item.code} {item.field}: {item.message} "
                f"(expected={item.expected}; observed={item.observed})"
                for item in self.differences
            )
        return "\n".join(lines)


class SchemaContractError(ValueError):
    def __init__(self, report: SchemaDiffReport):
        super().__init__(report.render())
        self.report = report


def _field_contract(value: Mapping[str, Any], context: str) -> FieldContract:
    data_type = value.get("type")
    nullable = value.get("nullable")
    if not isinstance(data_type, str) or not data_type:
        raise ValueError(f"{context}.type must be a non-empty string")
    if not isinstance(nullable, bool):
        raise ValueError(f"{context}.nullable must be boolean")
    return FieldContract(data_type.lower(), nullable)


def parse_contract(document: Mapping[str, Any], layer: str) -> LayerContract:
    layer_data = document.get("layers", {}).get(layer)
    if not isinstance(layer_data, Mapping):
        raise ValueError(f"Missing schema contract for layer {layer!r}")
    version = layer_data.get("version")
    if not isinstance(version, int) or version < 1:
        raise ValueError(f"Schema contract {layer}.version must be a positive integer")

    def fields(key: str) -> dict[str, FieldContract]:
        raw = layer_data.get(key, {})
        if not isinstance(raw, Mapping):
            raise ValueError(f"Schema contract {layer}.{key} must be an object")
        return {
            name: _field_contract(value, f"{layer}.{key}.{name}") for name, value in raw.items()
        }

    required = fields("required_fields")
    additive = fields("additive_columns")
    overlap = set(required) & set(additive)
    if overlap:
        raise ValueError(f"Fields cannot be both required and additive: {sorted(overlap)}")
    renames = layer_data.get("declared_renames", {})
    if not isinstance(renames, Mapping) or not all(
        isinstance(old, str) and isinstance(new, str) for old, new in renames.items()
    ):
        raise ValueError(f"Schema contract {layer}.declared_renames must map names to names")
    return LayerContract(layer, version, required, additive, dict(renames))


def load_contract(layer: str) -> LayerContract:
    path = files("project_12_pos_inventory_analytics").joinpath("schema_contracts.json")
    return parse_contract(json.loads(path.read_text(encoding="utf-8")), layer)


def contract_set_hash() -> str:
    path = files("project_12_pos_inventory_analytics").joinpath("schema_contracts.json")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observed_fields(struct_type: Any) -> tuple[ObservedField, ...]:
    return tuple(
        ObservedField(field.name, field.dataType.simpleString().lower(), field.nullable)
        for field in struct_type.fields
    )


def _description(field: ObservedField | FieldContract | None) -> str:
    if field is None:
        return "missing"
    return f"{field.data_type}, nullable={str(field.nullable).lower()}"


def compare_schema(
    contract: LayerContract,
    candidate_fields: Iterable[ObservedField],
    previous_fields: Iterable[ObservedField] = (),
) -> SchemaDiffReport:
    candidate = {field.name: field for field in candidate_fields}
    previous = {field.name: field for field in previous_fields}
    differences: list[SchemaDifference] = []
    expected_fields = {**contract.required_fields, **contract.additive_columns}

    missing_required = [name for name in contract.required_fields if name not in candidate]
    undeclared = [name for name in candidate if name not in expected_fields]
    rename_candidates: dict[str, str] = {}
    for missing in missing_required:
        expected = contract.required_fields[missing]
        same_shape = [
            name
            for name in undeclared
            if candidate[name].data_type == expected.data_type
            and candidate[name].nullable == expected.nullable
        ]
        if len(same_shape) == 1:
            rename_candidates[missing] = same_shape[0]

    for name, expected in contract.required_fields.items():
        observed = candidate.get(name)
        if observed is None:
            candidate_name = rename_candidates.get(name)
            code = "UNDECLARED_RENAME" if candidate_name else "MISSING_REQUIRED_FIELD"
            message = (
                f"Required field appears to have been renamed to {candidate_name!r} without "
                "a declared contract rename."
                if candidate_name
                else "Required field is absent from the candidate schema."
            )
            differences.append(
                SchemaDifference(
                    "ERROR",
                    code,
                    name,
                    _description(expected),
                    _description(candidate.get(candidate_name)) if candidate_name else "missing",
                    message,
                )
            )
            continue
        if observed.data_type != expected.data_type:
            differences.append(
                SchemaDifference(
                    "ERROR",
                    "INCOMPATIBLE_DATA_TYPE",
                    name,
                    _description(expected),
                    _description(observed),
                    "Candidate data type differs from the versioned contract.",
                )
            )
        if observed.nullable and not expected.nullable:
            # Only a WIDENING (contract said never-null, candidate can now be
            # null) is a breaking change for consumers. A NARROWING (contract
            # allowed null, candidate happens to never be null) is safe and
            # must not hold the stage -- confirmed live: this symmetric check
            # held Bronze/Silver on every real dev run because Spark infers
            # nullable=false for fields that are always populated in the
            # observed batch, even though the contract declared nullable=true.
            differences.append(
                SchemaDifference(
                    "ERROR",
                    "INVALID_NULLABILITY_CHANGE",
                    name,
                    _description(expected),
                    _description(observed),
                    "Candidate nullability widened beyond the versioned contract.",
                )
            )

    renamed_additions = set(rename_candidates.values())
    for name in undeclared:
        if name in renamed_additions:
            continue
        differences.append(
            SchemaDifference(
                "ERROR",
                "UNDECLARED_ADDITIVE_COLUMN",
                name,
                "not declared",
                _description(candidate[name]),
                "Additional field is not listed in additive_columns.",
            )
        )

    for name, expected in contract.additive_columns.items():
        observed = candidate.get(name)
        if observed is None:
            continue
        if observed.data_type != expected.data_type:
            differences.append(
                SchemaDifference(
                    "ERROR",
                    "INCOMPATIBLE_DATA_TYPE",
                    name,
                    _description(expected),
                    _description(observed),
                    "Configured additive field has an incompatible data type.",
                )
            )
        elif observed.nullable and not expected.nullable:
            differences.append(
                SchemaDifference(
                    "ERROR",
                    "INVALID_NULLABILITY_CHANGE",
                    name,
                    _description(expected),
                    _description(observed),
                    "Configured additive field nullability widened beyond the contract.",
                )
            )
        elif name not in previous:
            differences.append(
                SchemaDifference(
                    "INFO",
                    "ALLOWED_ADDITIVE_COLUMN",
                    name,
                    _description(expected),
                    _description(observed),
                    "Explicitly configured additive field is permitted.",
                )
            )

    removed = set(previous) - set(candidate)
    added = set(candidate) - set(previous)
    for name in sorted(set(previous) & set(candidate)):
        before = previous[name]
        after = candidate[name]
        if before.data_type != after.data_type:
            differences.append(
                SchemaDifference(
                    "ERROR",
                    "INCOMPATIBLE_DATA_TYPE_CHANGE",
                    name,
                    _description(before),
                    _description(after),
                    "Existing field data type cannot change in place.",
                )
            )
        if after.nullable and not before.nullable:
            differences.append(
                SchemaDifference(
                    "ERROR",
                    "INVALID_NULLABILITY_CHANGE",
                    name,
                    _description(before),
                    _description(after),
                    "Existing field nullability widened in place.",
                )
            )
    for old_name in sorted(removed):
        new_name = contract.declared_renames.get(old_name)
        if new_name and new_name in added:
            before = previous[old_name]
            after = candidate[new_name]
            severity = (
                "INFO"
                if (before.data_type, before.nullable) == (after.data_type, after.nullable)
                else "ERROR"
            )
            differences.append(
                SchemaDifference(
                    severity,
                    "DECLARED_RENAME" if severity == "INFO" else "INCOMPATIBLE_RENAME",
                    f"{old_name}->{new_name}",
                    _description(before),
                    _description(after),
                    "Versioned contract explicitly declares this rename."
                    if severity == "INFO"
                    else "Declared rename also changes type or nullability.",
                )
            )
            continue
        matching = [
            name
            for name in added
            if candidate[name].data_type == previous[old_name].data_type
            and candidate[name].nullable == previous[old_name].nullable
        ]
        if len(matching) == 1:
            differences.append(
                SchemaDifference(
                    "ERROR",
                    "UNDECLARED_RENAME",
                    f"{old_name}->{matching[0]}",
                    _description(previous[old_name]),
                    _description(candidate[matching[0]]),
                    "Existing field was removed and a same-shaped field was added without "
                    "a declared rename.",
                )
            )
        else:
            differences.append(
                SchemaDifference(
                    "ERROR",
                    "REMOVED_EXISTING_FIELD",
                    old_name,
                    _description(previous[old_name]),
                    "missing",
                    "Existing field was removed without a compatible declared rename.",
                )
            )

    return SchemaDiffReport(contract.layer, contract.version, tuple(differences))

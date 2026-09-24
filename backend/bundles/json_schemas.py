"""JSON Schemas for the bundle's JSON members, generated from the Pydantic models.

Generated at request time rather than committed: a schema shipped in the same zip as the
data it describes should be derived from the same model, and a committed copy drifts the
moment someone adds a field. ``tests/test_bundle_schemas.py`` compares each generated
schema against a golden snapshot for the current declared version, so a model change
fails loudly and the author has to choose between bumping the minor (additive) or the
major (breaking).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple, Type

from pydantic import BaseModel

from .models import (
    CONTACTS_REFERENCE_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    PREPARE_SEQUENCES_SCHEMA_VERSION,
    BundleManifest,
    PrepareSequencesPayload,
    TargetContactsReference,
)
from ..session_state import SESSION_SCHEMA_VERSION, SessionState

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID_BASE = "https://binderdash.dev/schemas"

BUNDLE_SCHEMAS: Dict[str, Tuple[Type[BaseModel], str]] = {
    "manifest": (BundleManifest, MANIFEST_SCHEMA_VERSION),
    "binderdash_session": (SessionState, SESSION_SCHEMA_VERSION),
    "prepare_sequences": (PrepareSequencesPayload, PREPARE_SEQUENCES_SCHEMA_VERSION),
    "target_contacts_reference": (
        TargetContactsReference,
        CONTACTS_REFERENCE_SCHEMA_VERSION,
    ),
}

DESIGNS_SCHEMA_NAMES: Tuple[str, ...] = (
    "manifest",
    "binderdash_session",
    "target_contacts_reference",
)
PREPARE_SCHEMA_NAMES: Tuple[str, ...] = DESIGNS_SCHEMA_NAMES + ("prepare_sequences",)


def schema_document(name: str) -> Dict[str, Any]:
    model, version = BUNDLE_SCHEMAS[name]
    document: Dict[str, Any] = {
        "$schema": SCHEMA_DIALECT,
        "$id": f"{SCHEMA_ID_BASE}/{name}/{version}.json",
        "x-binderdash-schema-version": version,
    }
    document.update(model.model_json_schema())
    document.setdefault("title", model.__name__)
    return document


def schema_arcname(name: str) -> str:
    return f"schemas/{name}.schema.json"


def schema_names_for_kind(kind: str) -> Tuple[str, ...]:
    return PREPARE_SCHEMA_NAMES if kind == "prepare_sequences" else DESIGNS_SCHEMA_NAMES


def all_schema_names() -> List[str]:
    return list(BUNDLE_SCHEMAS)

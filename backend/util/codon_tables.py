import logging
from typing import Any, Dict, List, Tuple

import python_codon_tables as pct

logger = logging.getLogger(__name__)


class CodonTableNotFoundError(Exception):
    def __init__(self, table_id: str) -> None:
        self.table_id = table_id
        super().__init__(f"Codon table not found: {table_id}")


class CodonTableUpstreamError(Exception):
    pass


def _table_label(table_id: str) -> str:
    parts = table_id.split("_")
    if len(parts) >= 2 and parts[-1].isdigit():
        taxid = parts[-1]
        org = parts[:-1]
        if len(org) >= 2 and len(org[0]) == 1:
            species = " ".join(org[1:])
            return f"{org[0].upper()}. {species} ({taxid})"
        return f"{' '.join(org)} ({taxid})".title()
    return table_id.replace("_", " ").title()


def _resolve_builtin_table_id(requested: str) -> str:
    builtins = pct.get_all_available_codons_tables(replace_U_by_T=True)
    if requested in builtins:
        return requested
    if requested.isdigit():
        suffix = f"_{requested}"
        matches = sorted(k for k in builtins if k.endswith(suffix))
        if len(matches) == 1:
            return matches[0]
    prefix = f"{requested}_"
    matches = sorted(k for k in builtins if k.startswith(prefix))
    if len(matches) == 1:
        return matches[0]
    return requested


def list_builtin_codon_table_options() -> List[Dict[str, str]]:
    tables = pct.get_all_available_codons_tables(replace_U_by_T=True)
    return [{"value": key, "label": _table_label(key)} for key in sorted(tables.keys())]


def _stop_codons_ordered(stop_entry: Dict[str, float]) -> List[str]:
    if not stop_entry:
        return []
    return [c for c, _ in sorted(stop_entry.items(), key=lambda x: (-x[1], x[0]))]


def load_codon_table_detail(table_id: str, *, web_timeout: float = 5.0) -> Tuple[str, str, List[str], Dict[str, Dict[str, float]]]:
    try:
        raw: Dict[str, Any] = pct.get_codons_table(
            table_id, replace_U_by_T=True, web_timeout=web_timeout
        )
    except FileNotFoundError:
        raise CodonTableNotFoundError(table_id) from None
    except RuntimeError as e:
        msg = str(e).lower()
        if "not found" in msg:
            raise CodonTableNotFoundError(table_id) from None
        logger.warning("codon table upstream error for %s: %s", table_id, e)
        raise CodonTableUpstreamError(str(e)) from e
    except Exception as e:
        logger.exception("codon table load failed for %s", table_id)
        raise CodonTableUpstreamError(str(e)) from e

    stop_raw = raw.get("*", {})
    if not isinstance(stop_raw, dict):
        stop_raw = {}
    stop_codons = _stop_codons_ordered({k: float(v) for k, v in stop_raw.items()})

    codons_by_aa: Dict[str, Dict[str, float]] = {}
    for aa, codons in raw.items():
        if aa == "*":
            continue
        if not isinstance(codons, dict):
            continue
        codons_by_aa[str(aa)] = {str(c): float(freq) for c, freq in codons.items()}

    resolved = _resolve_builtin_table_id(table_id)
    label = _table_label(resolved)
    return resolved, label, stop_codons, codons_by_aa

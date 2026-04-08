from typing import Any, Dict, List, Optional


class NoopDesignsRepository:
    def is_enabled(self) -> bool:
        return False

    def init_schema(self) -> None:
        pass

    def get_run_by_group_key(self, run_group_key: str) -> Optional[Dict[str, Any]]:
        return None

    def upsert_run_and_replace_designs(
        self,
        run_group_key: str,
        run_id: str,
        run_dict: Dict[str, Any],
        designs: List[Dict[str, Any]],
    ) -> None:
        pass

    def list_run_records(self) -> List[Dict[str, Any]]:
        return []

    def list_all_design_dicts(self) -> List[Dict[str, Any]]:
        return []

    def update_design_tag(
        self,
        run_id: str,
        design_id: str,
        tag: Optional[str],
        source_path: Optional[str] = None,
    ) -> bool:
        return False

    def update_design_good(
        self,
        run_id: str,
        design_id: str,
        good: Optional[bool],
        source_path: Optional[str] = None,
    ) -> bool:
        return False

    def delete_run(self, run_id: str) -> bool:
        return False

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

    def list_design_dicts_for_run_ids(
        self, run_ids: List[str]
    ) -> List[Dict[str, Any]]:
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

    def update_design_sequence_and_binder_chain(
        self,
        run_id: str,
        design_id: str,
        *,
        source_path: Optional[str] = None,
        sequence: Optional[str] = None,
        binder_chain: Optional[str] = None,
    ) -> bool:
        return False

    def update_design_short_names_bulk(
        self,
        items: List[Dict[str, Any]],
    ) -> int:
        return 0

    def list_data_json_keys_for_runs(self, run_ids: List[str]) -> List[str]:
        return []

    def merge_design_extra_data_bulk(
        self,
        run_id: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        return {
            "matched": 0,
            "updated": 0,
            "skipped_keys": 0,
            "unknown_design_ids": 0,
        }

    def delete_run(self, run_id: str) -> bool:
        return False

    def get_tag_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chain: str,
        target_chains: str,
        distant_from: str,
        sasa_probe_radius: float,
        sasa_n_points: int,
        sasa_threshold: float,
        more_distant_threshold: float,
    ) -> Optional[Dict[str, Any]]:
        return None

    def upsert_tag_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chain: str,
        target_chains: str,
        distant_from: str,
        sasa_probe_radius: float,
        sasa_n_points: int,
        sasa_threshold: float,
        more_distant_threshold: float,
        metrics: Dict[str, Any],
    ) -> None:
        pass

    def get_structural_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chains: str,
        target_chains: str,
    ) -> Optional[Dict[str, Any]]:
        return None

    def upsert_structural_metrics_cache(
        self,
        *,
        run_id: str,
        design_id: str,
        source_path: str,
        structure_filename: str,
        binder_chains: str,
        target_chains: str,
        metrics: Dict[str, Any],
    ) -> None:
        pass

    def record_login(
        self,
        provider: str,
        identifier: str,
        email: Optional[str] = None,
    ) -> None:
        pass

    def create_saved_set(
        self,
        *,
        saved_set_id: str,
        name: str,
        source_run_ids: List[str],
        filter_params: Dict[str, Any],
        result_summary: Dict[str, Any],
    ) -> None:
        pass

    def list_saved_sets(self) -> List[Dict[str, Any]]:
        return []

    def get_saved_set(self, saved_set_id: str) -> Optional[Dict[str, Any]]:
        return None

    def delete_saved_set(self, saved_set_id: str) -> bool:
        return False

    def rename_saved_set(self, saved_set_id: str, name: str) -> bool:
        return False

    def add_saved_set_designs(
        self, saved_set_id: str, designs: List[Dict[str, Any]]
    ) -> None:
        pass

    def list_saved_set_designs(self, saved_set_id: str) -> List[Dict[str, Any]]:
        return []

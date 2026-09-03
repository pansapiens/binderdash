"""
Declarative run folder detection and design-table wiring.

Keep ``primary_score_columns`` aligned with ``frontend/src/config/pipelineDisplay.ts``
(primary score chip / column resolution).
"""

from __future__ import annotations

from typing import Any, Dict, List

# Directories to skip during recursive walk (common to all signatures)
DEFAULT_SKIP_DIRS: List[str] = [".nextflow", "work"]

run_folder_signatures: List[Dict[str, Any]] = [
    {
        "method": "bindcraft",
        "submethod": "nf-binder-design",
        "priority": 1,  # Higher priority = checked first
        "required_files": ["results/bindcraft/final_design_stats.csv"],
        "required_dirs": ["results/bindcraft/accepted"],
        "results_table": "results/bindcraft/final_design_stats.csv",
        "pdb_pattern": "results/bindcraft/accepted/*.pdb",
        "params_files": ["results/params.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        "design_id_columns": ["Design"],
        "primary_score_columns": ["Average_i_pTM"],
        "sort_ascending": False,
        "structure_file_column": None,
        "structure_search_patterns": [
            "{design_id}.pdb",
            "{design_id}_*.pdb",
            "{design_id}*.pdb",
        ],
        # bindcraft_n_traj is per input PDB; total = n_traj × n_targets
        "trajectory_count_params_key": "bindcraft_n_traj",
        "trajectory_count_per_target": True,
        "trajectory_count_file": "results/bindcraft/trajectory_stats.csv",
    },
    {
        "method": "rfd",
        "submethod": "nf-binder-design",
        "priority": 2,
        "required_files": ["results/combined_scores.tsv"],
        "required_dirs": [
            "results/af2_initial_guess",
            "results/proteinmpnn",
            "results/rfdiffusion",
        ],
        "results_table": "results/combined_scores.tsv",
        "pdb_pattern": "results/af2_initial_guess/pdbs/*.pdb",
        "params_files": ["results/params.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        "design_id_columns": ["description"],
        "primary_score_columns": ["pae_interaction"],
        "sort_ascending": True,
        "structure_file_column": None,
        "structure_search_patterns": ["{design_id}.pdb"],
    },
    {
        "method": "bindcraft",
        "submethod": "regular",
        "priority": 3,
        "required_files": ["final_design_stats.csv"],
        "required_dirs": ["Accepted"],
        "results_table": "final_design_stats.csv",
        "pdb_pattern": "Accepted/*.pdb",
        "params_files": ["../settings.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        "design_id_columns": ["Design"],
        "primary_score_columns": ["Average_i_pTM"],
        "sort_ascending": False,
        "structure_file_column": None,
        "structure_search_patterns": [
            "{design_id}.pdb",
            "{design_id}_*.pdb",
            "{design_id}*.pdb",
        ],
    },
    {
        "method": "rfd",
        "submethod": "regular",
        "priority": 4,
        "required_dirs": ["af2_initial_guess"],
        "results_table": "combined_scores.tsv",
        "pdb_pattern": "af2_initial_guess/pdbs/*.pdb",
        "skip_dirs": DEFAULT_SKIP_DIRS,
        "design_id_columns": ["description"],
        "primary_score_columns": ["pae_interaction"],
        "sort_ascending": True,
        "structure_file_column": None,
        "structure_search_patterns": ["{design_id}.pdb"],
    },
    {
        "method": "boltzgen",
        "submethod": "nf-binder-design",
        "priority": 5,
        "required_dirs": ["results/boltzgen/filtered/final_ranked_designs"],
        "required_patterns": [
            "results/boltzgen/filtered/final_ranked_designs/final_designs_metrics_*.csv"
        ],
        "results_table_pattern": "results/boltzgen/filtered/final_ranked_designs/final_designs_metrics_*.csv",
        "structure_pattern": "results/boltzgen/filtered/final_ranked_designs/final_*_designs/*.cif",
        "structure_format": "cif",
        "params_files": ["results/params.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        "design_id_columns": ["id"],
        "primary_score_columns": ["design_to_target_iptm"],
        "sort_ascending": False,
        "structure_file_column": "file_name",
        "structure_search_patterns": [
            "{file_name}",
            "rank*_{file_name}",
        ],
        "trajectory_count_params_key": "num_designs",
        "trajectory_count_file": "results/boltzgen/filtered/final_ranked_designs/all_designs_metrics.csv",
    },
    {
        "method": "rfd3",
        "submethod": "nf-binder-design",
        "priority": 6,
        "required_files": ["results/rfd3/combined_scores.tsv"],
        "required_dirs": [
            "results/rfd3/rosettafold3",
            "results/rfd3/rfdiffusion3",
        ],
        "results_table": "results/rfd3/combined_scores.tsv",
        "structure_pattern": "results/rfd3/rosettafold3/output/*/*.cif",
        "additional_pdb_patterns": [
            "results/rfd3/rosettafold3/output/*/*.cif.gz",
            "results/rfd3/rosettafold3/output/*/*.pdb",
            "results/rfd3/rosettafold3/output/*/*.pdb.gz",
        ],
        "structure_format": "cif",
        "params_files": ["results/params.json"],
        "skip_dirs": DEFAULT_SKIP_DIRS,
        "design_id_columns": ["id"],
        "primary_score_columns": [
            "iptm",
            "pair_pae",
            "rf3_ipsae_min",
            "rf3_rmsd_target_aligned_binder_rmsd_all",
        ],
        "sort_ascending": False,
        "structure_file_column": None,
        "structure_base_dir": "results/rfd3/rosettafold3/output/{design_id}",
        "structure_search_patterns": [
            "{design_id}_model.cif",
            "{design_id}_model.cif.gz",
            "{design_id}_model.pdb",
            "{design_id}_model.pdb.gz",
        ],
    },
]

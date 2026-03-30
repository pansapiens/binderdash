from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# Authentication models
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class ScanRequest(BaseModel):
    folders: List[str]


class RunMetadata(BaseModel):
    run_id: str
    project_id: str
    path: str
    method: str  # e.g. bindcraft, rfd, boltzgen, rfd3
    results_table: Optional[str] = None
    pdb_files: List[str] = []
    metadata: Dict[str, Any] = {}


class PdbTarItem(BaseModel):
    run_id: str
    filename: str


class PdbTarRequest(BaseModel):
    items: List[PdbTarItem]


class DesignGoodUpdate(BaseModel):
    run_id: str
    design_id: str
    good: Optional[bool]
    source_path: Optional[str] = None

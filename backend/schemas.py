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
    method: str  # "bindcraft" or "rfd"
    results_table: Optional[str] = None
    pdb_files: List[str] = []
    metadata: Dict[str, Any] = {}


class PdbTarItem(BaseModel):
    run_id: str
    filename: str


class PdbTarRequest(BaseModel):
    items: List[PdbTarItem]

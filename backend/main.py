from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import pandas as pd
import numpy as np
import uuid
import io
import re
import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import secrets

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class RawSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    run_base_dirs: str = ""
    allowed_users: str = ""
    local_users: str = ""
    secret_key: str = ""
    cors_allowed_origins: str = ""
    disable_authentication: str = ""


class LocalUser(BaseModel):
    username: str
    password_hash: str


class AppSettings(BaseModel):
    run_base_dirs: List[str] = []
    allowed_users: List[str] = []
    local_users: List[LocalUser] = []
    disable_authentication: bool = False


# Authentication models
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Authentication configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
COOKIE_NAME = "binderdash_session"
CSRF_COOKIE_NAME = "binderdash_csrf"


class ScanRequest(BaseModel):
    folders: List[str]


class RunMetadata(BaseModel):
    run_id: str
    project_id: str
    path: str
    protocol: str  # "bindcraft" or "rfd"
    results_table: Optional[str] = None
    pdb_files: List[str] = []
    metadata: Dict[str, Any] = {}


def parse_local_users(local_users_str: str) -> List[LocalUser]:
    """Parse LOCAL_USERS string into list of LocalUser objects."""
    if not local_users_str:
        return []

    users = []
    for item in local_users_str.split(","):
        item = item.strip()
        if ":" in item:
            username, password_hash = item.split(":", 1)
            users.append(
                LocalUser(
                    username=username.strip(), password_hash=password_hash.strip()
                )
            )
        else:
            logger.warning(f"Invalid LOCAL_USERS format (missing colon): {item}")

    return users


# Authentication utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def authenticate_user(username: str, password: str) -> Optional[LocalUser]:
    """Authenticate a user against local users."""
    for user in settings.local_users:
        if user.username == username and verify_password(password, user.password_hash):
            return user
    return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def set_auth_cookie(
    response: Response, token: str, expires_delta: Optional[timedelta] = None
):
    """Set secure HttpOnly authentication cookie."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        expires=expire,  # Use datetime object directly
        httponly=True,  # Prevent XSS attacks
        secure=False,  # Set to False for HTTP testing
        samesite="lax",  # CSRF protection
        path="/",
    )


def clear_auth_cookie(response: Response):
    """Clear authentication cookie."""
    response.delete_cookie(
        key=COOKIE_NAME, path="/", httponly=True, secure=False, samesite="lax"
    )


def get_token_from_cookie(request: Request) -> Optional[str]:
    """Extract JWT token from HttpOnly cookie."""
    return request.cookies.get(COOKIE_NAME)


def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str):
    """Set CSRF token cookie."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # CSRF tokens need to be accessible to JavaScript
        secure=False,
        samesite="lax",
        path="/",
    )


def clear_csrf_cookie(response: Response):
    """Clear CSRF token cookie."""
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/", secure=False, samesite="lax")


async def get_current_user(request: Request):
    """Get the current authenticated user from JWT token in cookie."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Get token from cookie
    token = get_token_from_cookie(request)
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # Find the user in local users
    user = None
    for local_user in settings.local_users:
        if local_user.username == token_data.username:
            user = local_user
            break

    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: LocalUser = Depends(get_current_user)):
    """Get the current active user."""
    return current_user


async def get_current_user_optional(request: Request):
    """Get the current user if authentication is enabled, otherwise return None."""
    if settings.disable_authentication:
        return None  # Authentication disabled

    if not settings.local_users:
        return None  # No authentication required

    # Get token from cookie
    token = get_token_from_cookie(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await get_current_user(request)


async def get_current_user_optional_with_query(
    request: Request,
    token: Optional[str] = None,
):
    """
    Get the current user if authentication is enabled, supporting both
    cookie and query parameter auth (for backward compatibility with PDB files).
    """
    if settings.disable_authentication:
        return None  # Authentication disabled

    if not settings.local_users:
        return None  # No authentication required

    # Try cookie first, then query parameter token (for backward compatibility)
    cookie_token = get_token_from_cookie(request)
    if cookie_token:
        try:
            return await get_current_user(request)
        except Exception:
            pass

    # Try query parameter token (for backward compatibility with PDB files)
    if token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            token_data = TokenData(username=username)

            # Find the user in local users
            user = None
            for local_user in settings.local_users:
                if local_user.username == token_data.username:
                    user = local_user
                    break

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return user
        except JWTError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


raw_settings = RawSettings()
settings = AppSettings(
    run_base_dirs=(
        [item.strip() for item in raw_settings.run_base_dirs.split(",")]
        if raw_settings.run_base_dirs
        else []
    ),
    allowed_users=(
        [item.strip() for item in raw_settings.allowed_users.split(",")]
        if raw_settings.allowed_users
        else []
    ),
    local_users=parse_local_users(raw_settings.local_users),
    disable_authentication=raw_settings.disable_authentication.lower() == "true",
)

# Set up secret key
SECRET_KEY = raw_settings.secret_key or secrets.token_urlsafe(32)

# Set up CORS allowed origins
CORS_ALLOWED_ORIGINS = (
    [item.strip() for item in raw_settings.cors_allowed_origins.split(",")]
    if raw_settings.cors_allowed_origins
    else ["*"]
)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# CSRF Protection Middleware
@app.middleware("http")
async def csrf_protection(request: Request, call_next):
    """CSRF protection middleware for state-changing operations."""
    # Skip CSRF check for GET, HEAD, OPTIONS requests
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        response = await call_next(request)
        return response

    # Skip CSRF check for auth endpoints (login and logout don't need CSRF)
    if request.url.path in ["/api/auth/login", "/api/auth/logout", "/api/auth/status"]:
        response = await call_next(request)
        return response

    # Skip CSRF check if authentication is disabled
    if settings.disable_authentication or not settings.local_users:
        response = await call_next(request)
        return response

    # Check for CSRF token in header
    csrf_token = request.headers.get("X-CSRF-Token")
    if not csrf_token:
        return Response(
            content="CSRF token missing",
            status_code=403,
            headers={"Content-Type": "text/plain"},
        )

    # Verify CSRF token matches cookie
    cookie_csrf_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_csrf_token or csrf_token != cookie_csrf_token:
        return Response(
            content="CSRF token mismatch",
            status_code=403,
            headers={"Content-Type": "text/plain"},
        )

    response = await call_next(request)
    return response


# Mount the frontend static files
app.mount("/assets", StaticFiles(directory="backend/static/assets"), name="assets")
app.mount("/static", StaticFiles(directory="backend/static"), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/favicon.ico")
async def get_favicon():
    """Serve the favicon."""
    return FileResponse("backend/static/favicon.ico")


# In-memory cache for run metadata
run_cache: Dict[str, Dict[str, Any]] = {}

# In-memory cache for designs
designs_cache: List[Dict[str, Any]] = []


def guess_project_id(path: Path) -> str:
    """
    Guess the project ID based on the path, avoiding disallowed names.
    First finds the run name, then looks for a valid project name below it in the tree.

    Args:
        path: Path to the run directory

    Returns:
        Guessed project ID
    """
    # First, find the run name using the existing function
    run_name = guess_run_name(path)

    # Regex patterns for disallowed names
    disallowed_patterns = [
        r"^runs$",  # exact match for runs
        r"^results.*$",  # results, results_1, results_final, etc.
        r"^batch.*$",  # batch, batch_1, batch_final, etc.
        r"^bindcraft$",  # exact match for bindcraft
        r"^rfd$",  # exact match for rfd
        r"^\d+$",  # numeric-only names
    ]

    # Start from the current directory and work up the path
    current_path = path
    found_run_name = False

    while current_path != current_path.parent:  # Stop at root
        name = current_path.name

        # Check if we've found the run name
        if name == run_name:
            found_run_name = True
            # Move up one level to start looking for project ID below the run name
            current_path = current_path.parent
            continue

        # Only start looking for project ID after we've found the run name
        if found_run_name:
            # Check if name matches any disallowed pattern
            is_disallowed = any(
                re.match(pattern, name) for pattern in disallowed_patterns
            )

            if not is_disallowed:
                return name

        # Move up one level
        current_path = current_path.parent

    # If we can't find a good name, return empty string
    return ""


def guess_run_name(path: Path) -> str:
    """
    Guess the run name based on the path, avoiding disallowed names.

    Args:
        path: Path to the run directory

    Returns:
        Guessed run name
    """
    # Regex patterns for disallowed names
    disallowed_patterns = [
        r"^results.*$",  # results, results_1, results_final, etc.
        r"^bindcraft$",  # exact match for bindcraft
        r"^batches$",  # exact match for batches
        r"^\d+$",  # numeric-only names
    ]

    # Start from the current directory and work up the path
    current_path = path

    while current_path != current_path.parent:  # Stop at root
        name = current_path.name

        # Check if name matches any disallowed pattern
        is_disallowed = any(re.match(pattern, name) for pattern in disallowed_patterns)

        if not is_disallowed:
            return name

        # Move up one level
        current_path = current_path.parent

    # If we can't find a good name, use the original directory name
    return path.name


def is_bindcraft_results(path: Path) -> bool:
    """Check if a directory contains BindCraft results (final_design_stats.csv and Accepted/ folder)."""
    if not path.is_dir():
        return False
    stats_file = path / "final_design_stats.csv"
    accepted_folder = path / "Accepted"
    return stats_file.is_file() and accepted_folder.is_dir()


def is_rfd_results(path: Path) -> bool:
    """Check if a directory contains RFD results (combined_scores.tsv or .cs files)."""
    if not path.is_dir():
        return False

    # Check for combined_scores.tsv first
    combined_file = path / "combined_scores.tsv"
    if combined_file.is_file():
        return True

    # Check for .cs files in af2_initial_guess/scores/
    cs_files = list((path / "af2_initial_guess" / "scores").glob("*.cs"))
    if cs_files:
        return True

    # Check for .cs files in af2_initial_guess/ (deprecated location)
    cs_files = list((path / "af2_initial_guess").glob("*.cs"))
    return len(cs_files) > 0


def find_runs_recursive(root_path: Path) -> List[Dict[str, Any]]:
    """Recursively find all valid run directories within root_path."""
    runs = []

    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=True):
        current_dir = Path(dirpath)

        # Skip 'work' directories
        if current_dir.name == "work":
            dirnames[:] = []  # Stop recursion into work directories
            continue

        # Check if this directory is a valid run
        protocol = None
        results_table = None
        pdb_files = []

        if is_bindcraft_results(current_dir):
            protocol = "bindcraft"
            results_table = "final_design_stats.csv"

            # Find PDB files in Accepted/ directory
            accepted_dir = current_dir / "Accepted"
            if accepted_dir.is_dir():
                pdb_files = [str(p) for p in accepted_dir.glob("*.pdb")]

        elif is_rfd_results(current_dir):
            protocol = "rfd"

            # Determine results table path
            combined_file = current_dir / "combined_scores.tsv"
            if combined_file.is_file():
                results_table = "combined_scores.tsv"

            # Find PDB files in af2_initial_guess/pdbs/
            pdbs_dir = current_dir / "af2_initial_guess" / "pdbs"
            if pdbs_dir.is_dir():
                pdb_files = [str(p) for p in pdbs_dir.glob("*.pdb")]

        if protocol:
            # Create unique run ID
            run_id = str(uuid.uuid4())

            # Guess project ID and run name using the new functions
            guessed_project_id = guess_project_id(current_dir)
            guessed_name = guess_run_name(current_dir)

            runs.append(
                {
                    "run_id": run_id,
                    "project_id": guessed_project_id,
                    "path": str(current_dir),
                    "protocol": protocol,
                    "results_table": results_table,
                    "pdb_files": pdb_files,
                    "metadata": {
                        "name": guessed_name,
                        "original_name": current_dir.name,
                        "parent_path": str(current_dir.parent),
                        "pdb_count": len(pdb_files),
                    },
                }
            )

            # Stop recursion into this directory to avoid nested runs
            dirnames[:] = []

    return runs


def get_run_metadata(run_id: str) -> Optional[Dict[str, Any]]:
    """Get run metadata from cache."""
    return run_cache.get(run_id)


def load_run_table(run_metadata: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """Load and parse the results table for a run, handling merged runs."""
    try:
        # Check if this is a merged run
        merged_paths = run_metadata.get("merged_paths", [run_metadata["path"]])
        results_table = run_metadata.get("results_table")

        if not results_table:
            return None

        all_dfs = []

        for run_path in merged_paths:
            path = Path(run_path)
            table_path = path / results_table

            if not table_path.exists():
                logger.warning(f"Results table not found: {table_path}")
                continue

            try:
                # Load based on file extension
                if table_path.suffix.lower() == ".csv":
                    df = pd.read_csv(table_path)
                elif table_path.suffix.lower() == ".tsv":
                    df = pd.read_csv(table_path, sep="\t")
                else:
                    logger.warning(f"Unsupported table format: {table_path}")
                    continue

                # Add a column to identify which path this data came from
                df["source_path"] = str(path)
                all_dfs.append(df)

            except Exception as e:
                logger.error(f"Error loading table from {table_path}: {str(e)}")
                continue

        if not all_dfs:
            logger.warning(
                f"No valid tables found for run: {run_metadata.get('path', 'unknown')}"
            )
            return None

        # Combine all dataframes
        if len(all_dfs) == 1:
            return all_dfs[0]
        else:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            logger.info(
                f"Combined {len(all_dfs)} tables for merged run, total rows: {len(combined_df)}"
            )
            return combined_df

    except Exception as e:
        logger.error(f"Error loading run table: {str(e)}")
        return None


def parse_designs_from_run(run_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse designs from a run's results table."""
    try:
        df = load_run_table(run_metadata)
        if df is None or df.empty:
            return []

        designs = []
        protocol = run_metadata["protocol"]
        run_path = run_metadata["path"]
        run_name = run_metadata["metadata"]["name"]

        # Determine the design ID column and primary score column based on protocol
        if protocol == "bindcraft":
            design_id_col = "Design" if "Design" in df.columns else None
            primary_score_col = (
                "Average_i_pTM" if "Average_i_pTM" in df.columns else None
            )
            # Sort by primary score descending (higher is better for i_pTM)
            sort_ascending = False
        elif protocol == "rfd":
            design_id_col = "description" if "description" in df.columns else None
            primary_score_col = (
                "pae_interaction" if "pae_interaction" in df.columns else None
            )
            # Sort by primary score ascending (lower is better for pae_interaction)
            sort_ascending = True
        else:
            # Unknown protocol, try to guess columns
            design_id_col = None
            primary_score_col = None
            sort_ascending = True

        # Find design ID column if not found
        if not design_id_col:
            for col in df.columns:
                if col.lower() in ["design", "description", "name", "id"]:
                    design_id_col = col
                    break

        # Find primary score column if not found
        if not primary_score_col:
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                primary_score_col = numeric_cols[0]

        # Sort by primary score if available
        if primary_score_col and primary_score_col in df.columns:
            df = df.sort_values(
                primary_score_col, ascending=sort_ascending
            ).reset_index(drop=True)

        # Create design objects
        for index, row in df.iterrows():
            design_id = (
                str(row.get(design_id_col, f"design_{index}"))
                if design_id_col
                else f"design_{index}"
            )

            # Note: Score columns are now handled as regular columns in the frontend

            # Find PDB file for this design
            pdb_file = None
            if protocol == "bindcraft":
                # For bindcraft, look for PDB in Accepted/ directory
                accepted_dir = Path(run_path) / "Accepted"
                if accepted_dir.exists():
                    # Try exact match first
                    exact_pdb = accepted_dir / f"{design_id}.pdb"
                    if exact_pdb.exists():
                        pdb_file = str(exact_pdb)
                    else:
                        # Try pattern matching
                        potential_pdbs = list(accepted_dir.glob(f"{design_id}_*.pdb"))
                        if potential_pdbs:
                            pdb_file = str(potential_pdbs[0])
                        else:
                            # Last resort: any PDB starting with design_id
                            potential_pdbs = list(
                                accepted_dir.glob(f"{design_id}*.pdb")
                            )
                            if potential_pdbs:
                                pdb_file = str(potential_pdbs[0])

            elif protocol == "rfd":
                # For RFD, look for PDB in af2_initial_guess/pdbs/
                pdbs_dir = Path(run_path) / "af2_initial_guess" / "pdbs"
                if pdbs_dir.exists():
                    pdb_path = pdbs_dir / f"{design_id}.pdb"
                    if pdb_path.exists():
                        pdb_file = str(pdb_path)

            # Create design object with all available columns
            design = {
                "design_id": design_id,
                "run_id": run_metadata["run_id"],
                "project_id": run_metadata.get("project_id", ""),
                "run_name": run_name,
                "protocol": protocol,
                "run_path": run_path,
                "pdb_file": pdb_file,
                # Include all other columns from the source table
                **{
                    col: row[col]
                    for col in df.columns
                    if col != design_id_col
                    and not (
                        pd.isna(row[col]) if hasattr(pd, "isna") else row[col] is None
                    )
                },
            }

            designs.append(design)

        return designs

    except Exception as e:
        logger.error(
            f"Error parsing designs from run {run_metadata['run_id']}: {str(e)}"
        )
        return []


def refresh_designs_cache():
    """Refresh the designs cache by parsing all cached runs."""
    global designs_cache

    try:
        designs_cache.clear()

        for run in run_cache.values():
            run_designs = parse_designs_from_run(run)
            designs_cache.extend(run_designs)

            # Sort all designs by score (if available)
        designs_with_score = []
        designs_without_score = []

        for design in designs_cache:
            has_score = False
            if design["protocol"] == "rfd" and "pae_interaction" in design:
                has_score = True
            elif design["protocol"] == "bindcraft" and "Average_i_pTM" in design:
                has_score = True

            if has_score:
                designs_with_score.append(design)
            else:
                designs_without_score.append(design)

        # Sort by score, handling different protocols
        def sort_key(design):
            if design["protocol"] == "rfd":
                score = design.get("pae_interaction")
                if score is None:
                    return float("inf")  # Put designs without scores at the end
                return score  # Lower is better for pae_interaction
            else:  # bindcraft
                score = design.get("Average_i_pTM")
                if score is None:
                    return float("inf")  # Put designs without scores at the end
                return -score  # Higher is better for i_pTM, so invert

        designs_with_score.sort(key=sort_key)

        # Combine sorted designs with those without scores
        designs_cache = designs_with_score + designs_without_score

        logger.info(
            f"Refreshed designs cache: {len(designs_cache)} designs from {len(run_cache)} runs"
        )

    except Exception as e:
        logger.error(f"Error refreshing designs cache: {str(e)}")
        designs_cache = []


@app.get("/")
async def serve_frontend():
    """Serve the frontend index.html file."""
    return FileResponse("backend/static/index.html")


# Authentication endpoints
@app.post("/api/auth/login")
async def login(login_request: LoginRequest, response: Response):
    """Authenticate user and set secure HttpOnly cookie."""
    user = authenticate_user(login_request.username, login_request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Set secure HttpOnly cookie
    set_auth_cookie(response, access_token, access_token_expires)

    # Generate and set CSRF token
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)

    return {
        "message": "Login successful",
        "user": {"username": user.username},
        "csrf_token": csrf_token,
    }


@app.post("/api/auth/logout")
async def logout(response: Response):
    """Logout user and clear authentication cookies."""
    clear_auth_cookie(response)
    clear_csrf_cookie(response)
    return {"message": "Logout successful"}


@app.get("/api/auth/me")
async def read_users_me(current_user: LocalUser = Depends(get_current_active_user)):
    """Get current user information."""
    return {"username": current_user.username}


@app.get("/api/auth/status")
async def auth_status():
    """Check if authentication is enabled."""
    return {
        "auth_enabled": not settings.disable_authentication
        and len(settings.local_users) > 0,
        "disable_authentication": settings.disable_authentication,
        "local_users_count": len(settings.local_users),
    }


@app.get("/api/tree")
async def get_tree(
    path: str = "",
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    Return folder structure for the file browser.

    Args:
        path: Optional path parameter to get children of a specific directory

    Returns:
        List of folder objects with name, path, and has_children flag
    """
    logger.info(
        f"get_tree called with path: '{path}', run_base_dirs: {settings.run_base_dirs}"
    )
    try:
        if not path:
            # Return base directories
            folders = []
            for base_dir in settings.run_base_dirs:
                if os.path.exists(base_dir) and os.path.isdir(base_dir):
                    folders.append(
                        {
                            "name": os.path.basename(base_dir),
                            "path": base_dir,
                            "has_children": True,
                        }
                    )

            # If no base directories are configured, provide a fallback
            if not folders:
                logger.warning("No base directories configured in RUN_BASE_DIRS")
                # For development, allow browsing from current working directory
                current_dir = os.getcwd()
                if os.path.exists(current_dir) and os.path.isdir(current_dir):
                    folders.append(
                        {
                            "name": "Current Directory",
                            "path": current_dir,
                            "has_children": True,
                        }
                    )

            return {"folders": folders}
        else:
            # Return children of the specified path
            if not os.path.exists(path) or not os.path.isdir(path):
                raise ValueError(f"Path does not exist or is not a directory: {path}")

            # Validate path is within allowed base directories (only if base directories are configured)
            if settings.run_base_dirs:
                is_allowed = any(
                    path.startswith(base_dir) for base_dir in settings.run_base_dirs
                )
                if not is_allowed:
                    raise ValueError(
                        f"Path not within allowed base directories: {path}"
                    )
            else:
                # If no base directories configured, allow any path for development
                logger.warning(
                    f"No base directories configured, allowing access to: {path}"
                )

            folders = []
            logger.info(f"Listing contents of directory: {path}")
            try:
                items = os.listdir(path)
                logger.info(
                    f"Found {len(items)} items in {path}: {items[:10]}..."
                )  # Log first 10 items
                for item in items:
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path) or os.path.islink(item_path):
                        # Check if directory or symlink has subdirectories
                        has_children = False
                        try:
                            if os.path.islink(item_path):
                                # For symlinks, check the target
                                target_path = os.path.realpath(item_path)
                                if os.path.isdir(target_path):
                                    has_children = any(
                                        os.path.isdir(
                                            os.path.join(target_path, subitem)
                                        )
                                        for subitem in os.listdir(target_path)
                                    )
                            else:
                                # For regular directories
                                has_children = any(
                                    os.path.isdir(os.path.join(item_path, subitem))
                                    for subitem in os.listdir(item_path)
                                )
                        except (PermissionError, OSError):
                            # If we can't access the directory, assume it has children
                            has_children = True

                        folders.append(
                            {
                                "name": item,
                                "path": item_path,
                                "has_children": has_children,
                            }
                        )
            except PermissionError:
                logger.warning(f"Permission denied accessing directory: {path}")
                return {"folders": []}

            return {"folders": folders}

    except Exception as e:
        logger.error(f"Error in get_tree: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/runs/scan")
async def scan_runs(
    request: ScanRequest,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    Scan selected folders for valid run directories.

    Args:
        request: ScanRequest containing list of folder paths to scan

    Returns:
        List of run metadata objects
    """
    try:
        runs = []

        for folder_path in request.folders:
            # Validate path is within allowed base directories
            is_allowed = any(
                folder_path.startswith(base_dir) for base_dir in settings.run_base_dirs
            )
            if not is_allowed:
                logger.warning(
                    f"Skipping path not within allowed base directories: {folder_path}"
                )
                continue

            path = Path(folder_path)
            if not path.exists() or not path.is_dir():
                logger.warning(
                    f"Skipping non-existent or non-directory path: {folder_path}"
                )
                continue

            # Find runs in this folder
            folder_runs = find_runs_recursive(path)
            runs.extend(folder_runs)

            logger.info(f"Found {len(folder_runs)} runs in {folder_path}")

        # Cache the run metadata
        for run in runs:
            run_cache[run["run_id"]] = run

        # Refresh designs cache with new runs
        refresh_designs_cache()

        return {"runs": runs}

    except Exception as e:
        logger.error(f"Error in scan_runs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}/table")
async def get_run_table(
    run_id: str, current_user: Optional[LocalUser] = Depends(get_current_user_optional)
):
    """
    Get the results table data for a specific run.

    Args:
        run_id: Unique identifier for the run

    Returns:
        Table data as JSON
    """
    try:
        run_metadata = get_run_metadata(run_id)
        if not run_metadata:
            raise HTTPException(status_code=404, detail="Run not found")

        df = load_run_table(run_metadata)
        if df is None:
            raise HTTPException(
                status_code=404, detail="Results table not found or could not be loaded"
            )

        # Convert DataFrame to JSON, handling NaN and infinite values
        # Replace NaN and infinite values with None (which becomes null in JSON)
        df_clean = df.replace({np.nan: None, np.inf: None, -np.inf: None})

        return {
            "columns": df.columns.tolist(),
            "data": df_clean.to_dict(orient="records"),
            "total_rows": len(df),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_run_table: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs/{run_id}/files/pdb/{filename}")
async def get_pdb_file(
    run_id: str,
    filename: str,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional_with_query),
):
    """
    Stream PDB file for a specific run.

    Args:
        run_id: Unique identifier for the run
        filename: Name of the PDB file

    Returns:
        PDB file content
    """
    try:
        run_metadata = get_run_metadata(run_id)
        if not run_metadata:
            raise HTTPException(status_code=404, detail="Run not found")

        # Validate filename is in the run's PDB files
        pdb_files = run_metadata.get("pdb_files", [])
        if not any(Path(pdb_file).name == filename for pdb_file in pdb_files):
            raise HTTPException(status_code=404, detail="PDB file not found in run")

        # Find the full path to the PDB file
        pdb_path = None
        for pdb_file in pdb_files:
            if Path(pdb_file).name == filename:
                pdb_path = Path(pdb_file)
                break

        if not pdb_path or not pdb_path.exists():
            raise HTTPException(status_code=404, detail="PDB file not found on disk")

        # Stream the file
        return FileResponse(
            str(pdb_path), media_type="chemical/x-pdb", filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_pdb_file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def merge_runs(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge runs with the same project_id and run name into single logical runs."""
    merged_runs = {}

    for run in runs:
        # Create a key for grouping runs
        project_id = run.get("project_id", "unknown")
        run_name = run.get("metadata", {}).get("name", "unknown")
        group_key = f"{project_id}/{run_name}"

        if group_key not in merged_runs:
            # First run with this key - use it as the base
            merged_runs[group_key] = run.copy()
            merged_runs[group_key]["merged_paths"] = [run["path"]]
            merged_runs[group_key]["merged_pdb_files"] = run.get("pdb_files", []).copy()
        else:
            # Merge with existing run
            existing = merged_runs[group_key]
            existing["merged_paths"].append(run["path"])
            existing["merged_pdb_files"].extend(run.get("pdb_files", []))

            # Update metadata to reflect merged state
            existing["metadata"]["merged_count"] = len(existing["merged_paths"])
            existing["metadata"]["total_pdb_count"] = len(existing["merged_pdb_files"])

    # Convert back to list and clean up the merged data
    result = []
    for run in merged_runs.values():
        # Keep merged_paths for data loading, but clean up temporary fields
        run.pop("merged_pdb_files", None)
        result.append(run)

    return result


@app.get("/api/runs")
async def list_runs(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    List all cached runs, merging runs with the same project_id and run name.

    Returns:
        List of merged run metadata objects
    """
    try:
        all_runs = list(run_cache.values())
        merged_runs = merge_runs(all_runs)
        return {"runs": merged_runs}
    except Exception as e:
        logger.error(f"Error in list_runs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/runs/{run_id}")
async def delete_run(
    run_id: str,
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    Remove a run from the cache.

    Args:
        run_id: Unique identifier for the run

    Returns:
        Success message
    """
    if run_id in run_cache:
        del run_cache[run_id]
        return {"message": "Run removed from cache"}
    else:
        raise HTTPException(status_code=404, detail="Run not found")


@app.delete("/api/runs")
async def clear_runs(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    Clear all runs from the cache.

    Returns:
        Success message
    """
    run_cache.clear()
    return {"message": "All runs cleared from cache"}


@app.get("/api/designs")
async def list_designs(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    List all designs from all cached runs.

    Returns:
        List of design objects
    """
    try:
        # Refresh designs cache if it's empty
        if not designs_cache:
            refresh_designs_cache()

        return {"designs": designs_cache}

    except Exception as e:
        logger.error(f"Error in list_designs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/designs")
async def clear_designs(
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    Clear all designs from the cache.

    Returns:
        Success message
    """
    try:
        designs_cache.clear()
        return {"message": "All designs cleared from cache"}

    except Exception as e:
        logger.error(f"Error in clear_designs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def get_default_plot_columns(df: pd.DataFrame, protocol: str) -> Dict[str, str]:
    """Get default column selections for plots based on protocol and available columns."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    defaults = {"x": "", "y": ""}

    if protocol == "bindcraft":
        # BindCraft defaults
        if "Average_pLDDT" in numeric_cols:
            defaults["x"] = "Average_pLDDT"
        elif "mean_plddt" in numeric_cols:
            defaults["x"] = "mean_plddt"
        elif "plddt" in numeric_cols:
            defaults["x"] = "plddt"

        if "Average_i_pTM" in numeric_cols:
            defaults["y"] = "Average_i_pTM"
        elif "ipTM" in numeric_cols:
            defaults["y"] = "ipTM"
    elif protocol == "rfd":
        # RFD defaults
        if "plddt_binder" in numeric_cols:
            defaults["x"] = "plddt_binder"
        elif "plddt" in numeric_cols:
            defaults["x"] = "plddt"

        if "pae_interaction" in numeric_cols:
            defaults["y"] = "pae_interaction"
        elif "pae_binder" in numeric_cols:
            defaults["y"] = "pae_binder"

    # Fallback to first available numeric columns
    if not defaults["x"] and numeric_cols:
        defaults["x"] = numeric_cols[0]
    if not defaults["y"] and len(numeric_cols) > 1:
        defaults["y"] = numeric_cols[1]
    elif not defaults["y"] and numeric_cols:
        defaults["y"] = numeric_cols[0]

    return defaults


def create_scatter_plot_spec(
    df: pd.DataFrame, x_col: str, y_col: str, title: str = "Scatter Plot"
) -> Dict:
    """Create a Vega-Lite specification for a scatter plot."""
    # Convert DataFrame to the format Vega-Lite expects
    data_values = df[[x_col, y_col]].to_dict(orient="records")

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": data_values},
        "mark": {"type": "circle", "size": 60, "opacity": 0.7},
        "encoding": {
            "x": {
                "field": x_col,
                "type": "quantitative",
                "scale": {"zero": False},
                "title": x_col,
            },
            "y": {
                "field": y_col,
                "type": "quantitative",
                "scale": {"zero": False},
                "title": y_col,
            },
            "tooltip": [
                {"field": x_col, "type": "quantitative", "format": ".3f"},
                {"field": y_col, "type": "quantitative", "format": ".3f"},
            ],
        },
        "width": 400,
        "height": 300,
    }

    return spec


def create_histogram_spec(
    df: pd.DataFrame, col: str, title: str = "Distribution"
) -> Dict:
    """Create a Vega-Lite specification for a histogram/density plot."""
    data_values = df[[col]].to_dict(orient="records")

    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title,
        "data": {"values": data_values},
        "layer": [
            {
                "mark": {"type": "bar", "opacity": 0.7, "color": "#667eea"},
                "encoding": {
                    "x": {
                        "field": col,
                        "type": "quantitative",
                        "bin": {"maxbins": 30},
                        "title": col,
                    },
                    "y": {
                        "aggregate": "count",
                        "type": "quantitative",
                        "title": "Count",
                    },
                    "tooltip": [
                        {
                            "field": col,
                            "type": "quantitative",
                            "bin": True,
                            "title": f"{col} (binned)",
                        },
                        {
                            "aggregate": "count",
                            "type": "quantitative",
                            "title": "Count",
                        },
                    ],
                },
            }
        ],
        "width": 400,
        "height": 300,
    }

    return spec


@app.post("/api/runs/plots/columns")
async def get_plot_columns_multiple(
    request: Dict[str, Any],
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    Get available columns for plotting from multiple runs.

    Args:
        request: Dict containing "run_ids" list

    Returns:
        Available numeric columns and suggested defaults from combined data
    """
    try:
        run_ids = request.get("run_ids", [])
        if not run_ids:
            raise HTTPException(status_code=400, detail="No run IDs provided")

        all_dfs = []
        protocols = set()

        for run_id in run_ids:
            run_metadata = get_run_metadata(run_id)
            if not run_metadata:
                logger.warning(f"Run not found: {run_id}")
                continue

            df = load_run_table(run_metadata)
            if df is None:
                logger.warning(f"Results table not found for run: {run_id}")
                continue

            all_dfs.append(df)
            protocols.add(run_metadata.get("protocol", ""))

        if not all_dfs:
            raise HTTPException(
                status_code=404,
                detail="No valid data found for any of the specified runs",
            )

        # Combine all dataframes
        combined_df = pd.concat(all_dfs, ignore_index=True)

        # Get numeric columns
        numeric_cols = combined_df.select_dtypes(include=[np.number]).columns.tolist()

        # Get default columns based on the most common protocol
        most_common_protocol = (
            max(protocols, key=list(protocols).count) if protocols else ""
        )
        defaults = get_default_plot_columns(combined_df, most_common_protocol)

        return {
            "numeric_columns": numeric_cols,
            "defaults": defaults,
            "total_rows": len(combined_df),
            "run_count": len(run_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_plot_columns_multiple: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/runs/plots/scatter")
async def get_scatter_plot_multiple(
    request: Dict[str, Any],
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    Get raw data for a scatter plot from multiple runs.

    Args:
        request: Dict containing "run_ids", "x_col", and "y_col"

    Returns:
        Raw data for scatter plot with combined data from multiple runs
    """
    try:
        run_ids = request.get("run_ids", [])
        x_col = request.get("x_col")
        y_col = request.get("y_col")

        if not run_ids:
            raise HTTPException(status_code=400, detail="No run IDs provided")
        if not x_col or not y_col:
            raise HTTPException(status_code=400, detail="x_col and y_col are required")

        all_dfs = []

        for run_id in run_ids:
            run_metadata = get_run_metadata(run_id)
            if not run_metadata:
                logger.warning(f"Run not found: {run_id}")
                continue

            df = load_run_table(run_metadata)
            if df is None:
                logger.warning(f"Results table not found for run: {run_id}")
                continue

            all_dfs.append(df)

        if not all_dfs:
            raise HTTPException(
                status_code=404,
                detail="No valid data found for any of the specified runs",
            )

        # Combine all dataframes
        combined_df = pd.concat(all_dfs, ignore_index=True)

        # Validate columns exist and are numeric
        numeric_cols = combined_df.select_dtypes(include=[np.number]).columns.tolist()
        if x_col not in numeric_cols:
            raise HTTPException(
                status_code=400, detail=f"Column '{x_col}' not found or not numeric"
            )
        if y_col not in numeric_cols:
            raise HTTPException(
                status_code=400, detail=f"Column '{y_col}' not found or not numeric"
            )

        # Remove any infinite or null values
        clean_df = (
            combined_df[[x_col, y_col]].replace([np.inf, -np.inf], np.nan).dropna()
        )

        if len(clean_df) == 0:
            raise HTTPException(
                status_code=400, detail="No valid data points for selected columns"
            )

        # Convert to the format expected by Vega-Lite
        data_values = clean_df.to_dict(orient="records")

        return {
            "data": data_values,
            "data_points": len(clean_df),
            "total_rows": len(combined_df),
            "run_count": len(run_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_scatter_plot_multiple: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/runs/plots/histogram")
async def get_histogram_plot_multiple(
    request: Dict[str, Any],
    current_user: Optional[LocalUser] = Depends(get_current_user_optional),
):
    """
    Get raw data for a histogram/distribution plot from multiple runs.

    Args:
        request: Dict containing "run_ids" and "col"

    Returns:
        Raw data for histogram with combined data from multiple runs
    """
    try:
        run_ids = request.get("run_ids", [])
        col = request.get("col")

        if not run_ids:
            raise HTTPException(status_code=400, detail="No run IDs provided")
        if not col:
            raise HTTPException(status_code=400, detail="col is required")

        all_dfs = []

        for run_id in run_ids:
            run_metadata = get_run_metadata(run_id)
            if not run_metadata:
                logger.warning(f"Run not found: {run_id}")
                continue

            df = load_run_table(run_metadata)
            if df is None:
                logger.warning(f"Results table not found for run: {run_id}")
                continue

            all_dfs.append(df)

        if not all_dfs:
            raise HTTPException(
                status_code=404,
                detail="No valid data found for any of the specified runs",
            )

        # Combine all dataframes
        combined_df = pd.concat(all_dfs, ignore_index=True)

        # Validate column exists and is numeric
        numeric_cols = combined_df.select_dtypes(include=[np.number]).columns.tolist()
        if col not in numeric_cols:
            raise HTTPException(
                status_code=400, detail=f"Column '{col}' not found or not numeric"
            )

        # Remove any infinite or null values
        clean_df = combined_df[[col]].replace([np.inf, -np.inf], np.nan).dropna()

        if len(clean_df) == 0:
            raise HTTPException(
                status_code=400, detail="No valid data points for selected column"
            )

        # Convert to the format expected by Vega-Lite
        data_values = clean_df.to_dict(orient="records")

        return {
            "data": data_values,
            "data_points": len(clean_df),
            "total_rows": len(combined_df),
            "run_count": len(run_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_histogram_plot_multiple: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

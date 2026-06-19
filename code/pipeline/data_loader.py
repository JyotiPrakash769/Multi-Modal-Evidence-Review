from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = ROOT_DIR / "dataset"

CLAIMS_CSV = DATASET_DIR / "claims.csv"
SAMPLE_CLAIMS_CSV = DATASET_DIR / "sample_claims.csv"
USER_HISTORY_CSV = DATASET_DIR / "user_history.csv"
EVIDENCE_REQS_CSV = DATASET_DIR / "evidence_requirements.csv"


def image_id_from_path(image_path: str) -> str:
    return Path(image_path).stem


def split_image_paths(image_paths: str) -> list[str]:
    if not image_paths or pd.isna(image_paths):
        return []
    return [p.strip() for p in str(image_paths).split(";") if p.strip()]


def load_claims(input_path: str | Path = CLAIMS_CSV) -> pd.DataFrame:
    df = pd.read_csv(input_path)
    return df


def load_sample_claims() -> pd.DataFrame:
    return load_claims(SAMPLE_CLAIMS_CSV)


def load_user_history() -> pd.DataFrame:
    return pd.read_csv(USER_HISTORY_CSV)


def load_evidence_requirements() -> pd.DataFrame:
    return pd.read_csv(EVIDENCE_REQS_CSV)


def enrich_claim_row(row: dict) -> dict:
    image_paths_raw = row.get("image_paths", "")
    row["image_paths_list"] = split_image_paths(image_paths_raw)
    row["image_ids"] = [image_id_from_path(p) for p in row["image_paths_list"]]
    return row

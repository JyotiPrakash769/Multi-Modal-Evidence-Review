import pandas as pd

from .data_loader import load_evidence_requirements


def lookup_evidence(claim_object: str) -> list[str]:
    df = load_evidence_requirements()
    mask = (df["claim_object"] == claim_object) | (df["claim_object"] == "all")
    matching = df[mask]
    return matching["minimum_image_evidence"].tolist()

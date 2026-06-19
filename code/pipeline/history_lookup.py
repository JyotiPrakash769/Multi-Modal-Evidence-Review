import pandas as pd

from .data_loader import load_user_history


def lookup_history(user_id: str) -> tuple[str, bool]:
    df = load_user_history()
    match = df[df["user_id"] == user_id]
    if match.empty:
        summary = "No prior claim history for this user."
        return summary, False

    row = match.iloc[0]
    past = int(row["past_claim_count"])
    accepted = int(row["accept_claim"])
    manual = int(row["manual_review_claim"])
    rejected = int(row["rejected_claim"])
    last90 = int(row["last_90_days_claim_count"])
    flags = str(row["history_flags"])
    hist_summary = str(row["history_summary"])

    context = (
        f"Past claims: {past} ({accepted} accepted, {manual} manual review, {rejected} rejected). "
        f"Last 90 days: {last90}. "
        f"History flags: {flags}. "
        f"Summary: {hist_summary}"
    )

    is_risky = rejected > 0 or manual > 0 or flags.lower() != "none"

    return context, is_risky

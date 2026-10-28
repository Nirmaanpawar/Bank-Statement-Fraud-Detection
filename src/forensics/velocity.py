"""
Forensic Velocity, Threshold Avoidance (PMLA / Rule 114B Heuristic), and Round Amount Analysis.
Calibrated for Indian Banking Regulatory Environment.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


@dataclass
class FlaggedTransaction:
    txn_id: int
    date: str
    description: str
    amount: float
    reason: str
    severity: str  # 'low', 'medium', 'high', 'critical'


@dataclass
class VelocityAnalysisResult:
    structuring_count: int
    burst_count: int
    round_amount_count: int
    total_flagged: int
    flagged_transactions: List[FlaggedTransaction] = field(default_factory=list)
    structuring_score: float = 0.0
    velocity_score: float = 0.0
    round_score: float = 0.0
    composite_score: float = 0.0
    summary_message: str = ""


def detect_velocity_and_structuring(
    df: pd.DataFrame,
    structuring_min: float = 45000.0,
    structuring_max: float = 49999.0,
    burst_window_minutes: int = 120,
    burst_threshold: int = 4,
    round_multiple: float = 5000.0
) -> VelocityAnalysisResult:
    """
    Detects potential threshold avoidance (Rule 114B PAN requirement heuristic),
    high-velocity transactional bursts, and excessive round amount clusters.
    
    Note: Threshold proximity is treated as an analytical risk heuristic indicating
    need for KYC / source-of-funds verification, not as definitive proof of intent.
    """
    if df.empty:
        return VelocityAnalysisResult(
            structuring_count=0,
            burst_count=0,
            round_amount_count=0,
            total_flagged=0,
            summary_message="No transactions to analyze."
        )

    df_proc = df.copy()
    if 'date' in df_proc.columns:
        df_proc['date_dt'] = pd.to_datetime(df_proc['date'], errors='coerce')
    else:
        df_proc['date_dt'] = pd.date_range(end=pd.Timestamp.now(), periods=len(df_proc), freq='h')

    # Sort chronologically
    df_proc = df_proc.sort_values(by='date_dt').reset_index(drop=True)

    flagged: List[FlaggedTransaction] = []
    
    # 1. Potential Threshold Avoidance Heuristic (Rule 114B PAN requirement: ₹50,000)
    # Identifies transactions clustered closely below ₹50,000 (e.g., ₹45,000 to ₹49,999)
    structuring_mask = (df_proc['amount'] >= structuring_min) & (df_proc['amount'] <= structuring_max)
    structuring_rows = df_proc[structuring_mask]
    structuring_count = len(structuring_rows)
    
    for _, row in structuring_rows.iterrows():
        flagged.append(FlaggedTransaction(
            txn_id=int(row.get('txn_id', 0)),
            date=str(row['date']),
            description=str(row.get('description', '')),
            amount=float(row['amount']),
            reason=(
                f"Analytical Heuristic: Amount ₹{row['amount']:,.2f} is clustered immediately below "
                f"the ₹50,000 PAN quoting threshold (Rule 114B / PMLA KYC guidelines). Source verification advised."
            ),
            severity="high" if structuring_count >= 2 else "medium"
        ))

    # 2. Velocity Burst Detection (e.g. rapid UPI/IMPS transfers within short window)
    burst_count = 0
    df_time = df_proc.set_index('date_dt')
    try:
        rolling_counts = df_time['amount'].rolling(f"{burst_window_minutes}min").count()
        burst_indices = df_proc.index[rolling_counts.values >= burst_threshold].tolist()
        burst_count = len(burst_indices)
        
        for idx in burst_indices:
            row = df_proc.iloc[idx]
            flagged.append(FlaggedTransaction(
                txn_id=int(row.get('txn_id', 0)),
                date=str(row['date']),
                description=str(row.get('description', '')),
                amount=float(row['amount']),
                reason=f"High-Velocity Burst: {burst_threshold}+ transactions within {burst_window_minutes}min window.",
                severity="medium"
            ))
    except Exception:
        # Fallback if timestamps are day-only
        daily_counts = df_proc.groupby(df_proc['date_dt'].dt.date)['amount'].transform('count')
        burst_indices = df_proc.index[daily_counts >= (burst_threshold * 2)].tolist()
        burst_count = len(burst_indices)
        for idx in burst_indices:
            row = df_proc.iloc[idx]
            flagged.append(FlaggedTransaction(
                txn_id=int(row.get('txn_id', 0)),
                date=str(row['date']),
                description=str(row.get('description', '')),
                amount=float(row['amount']),
                reason="Daily Velocity Spike: Exceeds standard daily transaction frequency.",
                severity="low"
            ))

    # 3. Round Number Anomaly Detection
    # In Indian banking, repeated round sums like ₹10,000, ₹25,000, ₹50,000 without odd paisa/cents
    round_mask = (df_proc['amount'] >= 10000.0) & (df_proc['amount'] % round_multiple == 0)
    round_rows = df_proc[round_mask]
    round_amount_count = len(round_rows)
    round_ratio = round_amount_count / len(df_proc) if len(df_proc) > 0 else 0
    
    if round_ratio > 0.25 and round_amount_count >= 3:
        for _, row in round_rows.iterrows():
            flagged.append(FlaggedTransaction(
                txn_id=int(row.get('txn_id', 0)),
                date=str(row['date']),
                description=str(row.get('description', '')),
                amount=float(row['amount']),
                reason=f"Recurring Round Amount: Exact integer multiple ₹{row['amount']:,.2f}.",
                severity="low"
            ))

    # De-duplicate flagged items per txn_id
    seen_ids = set()
    unique_flagged = []
    for f in flagged:
        key = (f.txn_id, f.reason)
        if key not in seen_ids:
            seen_ids.add(key)
            unique_flagged.append(f)

    # Scoring (0 - 100)
    structuring_score = min(100.0, structuring_count * 35.0)
    velocity_score = min(100.0, (burst_count / max(1, len(df_proc))) * 200.0)
    round_score = min(100.0, round_ratio * 120.0) if round_amount_count >= 3 else 0.0

    composite_score = round(min(100.0, (structuring_score * 0.55) + (velocity_score * 0.3) + (round_score * 0.15)), 2)

    summary = (
        f"Detected {structuring_count} threshold-proximity transaction(s), {burst_count} velocity burst(s), "
        f"and {round_amount_count} recurring round amount(s)."
    )

    return VelocityAnalysisResult(
        structuring_count=structuring_count,
        burst_count=burst_count,
        round_amount_count=round_amount_count,
        total_flagged=len(unique_flagged),
        flagged_transactions=unique_flagged,
        structuring_score=round(structuring_score, 2),
        velocity_score=round(velocity_score, 2),
        round_score=round(round_score, 2),
        composite_score=composite_score,
        summary_message=summary
    )

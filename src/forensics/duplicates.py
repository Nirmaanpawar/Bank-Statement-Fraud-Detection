"""
Duplicate and Replay Transaction Detection Module.
Detects identical and near-identical transactions within short time windows.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
import pandas as pd


@dataclass
class DuplicateGroup:
    group_id: int
    amount: float
    description: str
    transaction_ids: List[int]
    dates: List[str]
    count: int
    duplicate_type: str  # 'exact' or 'near'
    total_impact: float


@dataclass
class DuplicateAnalysisResult:
    has_duplicates: bool
    duplicate_group_count: int
    duplicate_txn_count: int
    total_duplicated_amount: float
    duplicate_groups: List[DuplicateGroup] = field(default_factory=list)
    fraud_score: float = 0.0
    summary_message: str = ""


def detect_duplicates(
    df: pd.DataFrame,
    window_hours: int = 48
) -> DuplicateAnalysisResult:
    """
    Identifies duplicate transactions (exact match on date, desc, amount,
    or near-match within `window_hours` with same amount and description).
    """
    if df.empty or len(df) < 2:
        return DuplicateAnalysisResult(
            has_duplicates=False,
            duplicate_group_count=0,
            duplicate_txn_count=0,
            total_duplicated_amount=0.0,
            summary_message="No transactions available to evaluate duplicates."
        )

    df_proc = df.copy()
    if 'date' in df_proc.columns:
        df_proc['date_dt'] = pd.to_datetime(df_proc['date'], errors='coerce')
    else:
        df_proc['date_dt'] = pd.date_range(end=pd.Timestamp.now(), periods=len(df_proc), freq='h')

    df_proc['clean_desc'] = df_proc['description'].astype(str).str.strip().str.lower()
    df_proc['rounded_amt'] = df_proc['amount'].round(2)
    
    # 1. Exact duplicates: exact same rounded_amt, clean_desc, and date
    exact_dups = df_proc[df_proc.duplicated(subset=['date', 'clean_desc', 'rounded_amt'], keep=False)]
    
    groups: List[DuplicateGroup] = []
    processed_indices = set()
    group_counter = 1
    
    # Group exact duplicates
    if not exact_dups.empty:
        for (d, desc, amt), sub_df in exact_dups.groupby(['date', 'clean_desc', 'rounded_amt']):
            txn_ids = sub_df.get('txn_id', sub_df.index + 1).tolist()
            dates = [str(x) for x in sub_df['date'].tolist()]
            total_imp = float(amt) * (len(sub_df) - 1)
            groups.append(DuplicateGroup(
                group_id=group_counter,
                amount=float(amt),
                description=str(sub_df['description'].iloc[0]),
                transaction_ids=[int(x) for x in txn_ids],
                dates=dates,
                count=len(sub_df),
                duplicate_type="Exact Match",
                total_impact=round(total_imp, 2)
            ))
            group_counter += 1
            processed_indices.update(sub_df.index)

    # 2. Near duplicates: same amount and description within window_hours (not already covered)
    remaining_df = df_proc[~df_proc.index.isin(processed_indices)].sort_values('date_dt')
    if not remaining_df.empty:
        for (desc, amt), sub_df in remaining_df.groupby(['clean_desc', 'rounded_amt']):
            if len(sub_df) > 1 and amt > 10.0:  # Ignore tiny fees
                # Check time differences
                sub_df = sub_df.sort_values('date_dt')
                time_diffs = sub_df['date_dt'].diff().dt.total_seconds() / 3600.0
                
                # If any successive transaction is within window_hours
                clustered = []
                current_cluster = [sub_df.iloc[0]]
                for i in range(1, len(sub_df)):
                    diff_h = time_diffs.iloc[i]
                    if diff_h <= window_hours:
                        current_cluster.append(sub_df.iloc[i])
                    else:
                        if len(current_cluster) > 1:
                            clustered.append(current_cluster)
                        current_cluster = [sub_df.iloc[i]]
                if len(current_cluster) > 1:
                    clustered.append(current_cluster)

                for cl in clustered:
                    cl_df = pd.DataFrame(cl)
                    txn_ids = cl_df.get('txn_id', cl_df.index + 1).tolist()
                    dates = [str(x) for x in cl_df['date'].tolist()]
                    total_imp = float(amt) * (len(cl_df) - 1)
                    groups.append(DuplicateGroup(
                        group_id=group_counter,
                        amount=float(amt),
                        description=str(cl_df['description'].iloc[0]),
                        transaction_ids=[int(x) for x in txn_ids],
                        dates=dates,
                        count=len(cl_df),
                        duplicate_type="Near Match (<48h)",
                        total_impact=round(total_imp, 2)
                    ))
                    group_counter += 1

    total_dup_txns = sum(g.count for g in groups)
    total_dup_amt = sum(g.total_impact for g in groups)
    
    # Duplicate score
    dup_ratio = total_dup_txns / len(df_proc) if len(df_proc) > 0 else 0
    fraud_score = min(100.0, (len(groups) * 15.0) + (dup_ratio * 100.0))

    summary = (
        f"Found {len(groups)} duplicate cluster(s) involving {total_dup_txns} transactions "
        f"totaling ₹{total_dup_amt:,.2f} in potentially redundant or replayed transactions."
        if groups else "No suspicious duplicate or replayed transactions identified."
    )

    return DuplicateAnalysisResult(
        has_duplicates=len(groups) > 0,
        duplicate_group_count=len(groups),
        duplicate_txn_count=total_dup_txns,
        total_duplicated_amount=round(total_dup_amt, 2),
        duplicate_groups=groups,
        fraud_score=round(fraud_score, 2),
        summary_message=summary
    )

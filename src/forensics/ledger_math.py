"""
Forensic Ledger Mathematical Integrity Auditor.
Validates row-by-row running balance equations and opening/closing reconciliations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


@dataclass
class DiscrepancyRow:
    row_index: int
    txn_id: int
    date: str
    description: str
    reported_balance: float
    expected_balance: float
    discrepancy: float
    details: str


@dataclass
class LedgerAuditResult:
    is_tampered: bool
    tampered_row_count: int
    total_rows: int
    tamper_ratio: float
    discrepancies: List[DiscrepancyRow] = field(default_factory=list)
    reconciliation_valid: bool = True
    opening_balance: float = 0.0
    closing_balance_reported: float = 0.0
    closing_balance_calculated: float = 0.0
    closing_discrepancy: float = 0.0
    total_deposits: float = 0.0
    total_withdrawals: float = 0.0
    math_fraud_score: float = 0.0  # 0 to 100
    summary_message: str = ""


def audit_ledger_math(
    df: pd.DataFrame,
    opening_balance: Optional[float] = None,
    tolerance: float = 0.01
) -> LedgerAuditResult:
    """
    Audits the mathematical consistency of transactions.
    
    Rule 1 (Chain rule):
    Balance[t] = Balance[t-1] + Deposit[t] - Withdrawal[t]
    
    Rule 2 (Reconciliation rule):
    Opening_Balance + Sum(Deposits) - Sum(Withdrawals) = Closing_Balance
    """
    if df.empty:
        return LedgerAuditResult(
            is_tampered=False,
            tampered_row_count=0,
            total_rows=0,
            tamper_ratio=0.0,
            summary_message="No transactions found to audit."
        )

    df_audit = df.copy()
    total_rows = len(df_audit)
    discrepancies: List[DiscrepancyRow] = []

    # Ensure required columns exist
    for col in ['deposit', 'withdrawal', 'balance']:
        if col not in df_audit.columns:
            raise KeyError(f"Missing required column '{col}' for ledger math audit.")

    # Convert numeric fields
    deposits = df_audit['deposit'].fillna(0.0).astype(float).values
    withdrawals = df_audit['withdrawal'].fillna(0.0).astype(float).values
    balances = df_audit['balance'].fillna(0.0).astype(float).values
    
    total_dep = float(np.sum(deposits))
    total_wdr = float(np.sum(withdrawals))
    
    # Infer or verify initial balance
    # If opening balance not provided, infer opening balance from row 0:
    # row 0 balance = opening + deposit[0] - withdrawal[0] => opening = balance[0] - deposit[0] + withdrawal[0]
    if opening_balance is None:
        inferred_opening = balances[0] - deposits[0] + withdrawals[0]
        eff_opening = inferred_opening
    else:
        eff_opening = float(opening_balance)

    # Audit all rows step-by-step (from row 0 to total_rows - 1)
    current_expected = eff_opening
    for i in range(total_rows):
        current_expected = current_expected + deposits[i] - withdrawals[i]
        diff = abs(balances[i] - current_expected)
        
        # Check row-to-row chain
        if diff > tolerance:
            row_dict = df_audit.iloc[i]
            # Check if discrepancy is local (only this row altered) or cumulative
            if i > 0:
                prev_reported = balances[i-1]
                local_expected = prev_reported + deposits[i] - withdrawals[i]
                local_diff = abs(balances[i] - local_expected)
            else:
                local_diff = diff

            discrepancies.append(DiscrepancyRow(
                row_index=i,
                txn_id=int(row_dict.get('txn_id', i + 1)),
                date=str(row_dict.get('date', 'Unknown')),
                description=str(row_dict.get('description', '')),
                reported_balance=float(balances[i]),
                expected_balance=float(round(current_expected, 2)),
                discrepancy=float(round(diff, 2)),
                details=(
                    f"Balance altered: Reported ₹{balances[i]:.2f} vs Expected ₹{current_expected:.2f} "
                    f"(Delta: ₹{balances[i] - current_expected:+.2f})"
                )
            ))
            # In forensic accounting, if someone forged a balance on a row,
            # we also re-align to reported if we want to detect isolated row alterations vs cascading drift
            current_expected = balances[i]

    # Overall closing balance reconciliation
    reported_closing = float(balances[-1])
    calculated_closing = eff_opening + total_dep - total_wdr
    closing_discrepancy = abs(reported_closing - calculated_closing)
    reconciliation_valid = closing_discrepancy <= tolerance

    tampered_count = len(discrepancies)
    tamper_ratio = tampered_count / total_rows if total_rows > 0 else 0.0

    # Calculate Math Fraud Score (0 - 100)
    if tampered_count == 0 and reconciliation_valid:
        math_fraud_score = 0.0
        summary_msg = "Passed: All running balances and reconciliation equations match with zero discrepancies."
    else:
        # Mathematical fraud is high confidence proof of statement manipulation
        base_score = 50.0 if not reconciliation_valid else 30.0
        incremental = min(50.0, tamper_ratio * 100.0 * 1.5)
        math_fraud_score = min(100.0, base_score + incremental)
        summary_msg = (
            f"FAILED: Found {tampered_count} mathematical balance discrepanc{'ies' if tampered_count > 1 else 'y'}. "
            f"Closing reconciliation delta: ₹{closing_discrepancy:,.2f}."
        )

    return LedgerAuditResult(
        is_tampered=tampered_count > 0 or not reconciliation_valid,
        tampered_row_count=tampered_count,
        total_rows=total_rows,
        tamper_ratio=round(tamper_ratio, 4),
        discrepancies=discrepancies,
        reconciliation_valid=reconciliation_valid,
        opening_balance=round(eff_opening, 2),
        closing_balance_reported=round(reported_closing, 2),
        closing_balance_calculated=round(calculated_closing, 2),
        closing_discrepancy=round(closing_discrepancy, 2),
        total_deposits=round(total_dep, 2),
        total_withdrawals=round(total_wdr, 2),
        math_fraud_score=round(math_fraud_score, 2),
        summary_message=summary_msg
    )

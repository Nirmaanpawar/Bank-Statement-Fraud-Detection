"""
Standardized Data Models for Bank Statements and Transactions
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import pandas as pd


@dataclass
class Transaction:
    txn_id: int
    date: datetime
    description: str
    amount: float
    txn_type: str  # 'credit' (deposit) or 'debit' (withdrawal)
    balance: float
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def deposit(self) -> float:
        return self.amount if self.txn_type == "credit" else 0.0

    @property
    def withdrawal(self) -> float:
        return self.amount if self.txn_type == "debit" else 0.0


@dataclass
class StatementMetadata:
    bank_name: str = "Unknown Bank"
    account_number: str = "XXXX-XXXX-XXXX"
    account_holder: str = "Valued Customer"
    statement_period_start: Optional[str] = None
    statement_period_end: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    currency: str = "USD"
    page_count: int = 1


@dataclass
class ParsedStatement:
    metadata: StatementMetadata
    transactions: List[Transaction]
    df: pd.DataFrame
    parsing_notes: List[str] = field(default_factory=list)
    
    @property
    def transaction_count(self) -> int:
        return len(self.transactions)

    @property
    def total_deposits(self) -> float:
        return sum(t.deposit for t in self.transactions)

    @property
    def total_withdrawals(self) -> float:
        return sum(t.withdrawal for t in self.transactions)

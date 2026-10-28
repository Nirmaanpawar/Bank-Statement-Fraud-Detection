"""
Tests for Ledger Running Balance and Reconciliation Audit.
"""

import unittest
import pandas as pd
from src.forensics.ledger_math import audit_ledger_math


class TestLedgerMath(unittest.TestCase):
    def test_clean_ledger(self):
        # Initial: 1000
        # Row 0: +500 => 1500
        # Row 1: -200 => 1300
        # Row 2: +100 => 1400
        data = {
            'txn_id': [1, 2, 3],
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'description': ['Deposit', 'ATM', 'Transfer'],
            'deposit': [500.0, 0.0, 100.0],
            'withdrawal': [0.0, 200.0, 0.0],
            'balance': [1500.0, 1300.0, 1400.0]
        }
        df = pd.DataFrame(data)
        res = audit_ledger_math(df, opening_balance=1000.0)
        self.assertFalse(res.is_tampered)
        self.assertEqual(res.tampered_row_count, 0)
        self.assertTrue(res.reconciliation_valid)
        self.assertEqual(res.math_fraud_score, 0.0)

    def test_tampered_balance(self):
        # Tamper row 1 balance to 2500 instead of 1300
        data = {
            'txn_id': [1, 2, 3],
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'description': ['Deposit', 'ATM', 'Transfer'],
            'deposit': [500.0, 0.0, 100.0],
            'withdrawal': [0.0, 200.0, 0.0],
            'balance': [1500.0, 2500.0, 1400.0]
        }
        df = pd.DataFrame(data)
        res = audit_ledger_math(df, opening_balance=1000.0)
        self.assertTrue(res.is_tampered)
        self.assertGreater(res.tampered_row_count, 0)
        self.assertGreater(res.math_fraud_score, 0.0)
        self.assertIn(1, [d.row_index for d in res.discrepancies])


if __name__ == '__main__':
    unittest.main()

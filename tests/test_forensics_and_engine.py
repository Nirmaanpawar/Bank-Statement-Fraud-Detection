"""
Unit and integration tests for Benford, Velocity, and Engine.
"""

import unittest
import numpy as np
import pandas as pd
from src.forensics.benford import analyze_benford_law
from src.forensics.velocity import detect_velocity_and_structuring
from src.parsers.csv_parser import parse_csv_or_excel
from src.parsers.pdf_parser import parse_pdf_statement
from src.engine import FraudDetectionEngine


class TestForensicsAndEngine(unittest.TestCase):
    def test_benford_uniform_tampered(self):
        # Generate artificial numbers starting heavily with 8 and 9
        artificial_amounts = pd.Series([float(f"8{i}.50") for i in range(10, 50)] + [float(f"9{i}.20") for i in range(10, 50)])
        res = analyze_benford_law(artificial_amounts)
        self.assertTrue(res.is_anomaly)
        self.assertGreater(res.fraud_score, 40.0)

    def test_structuring_detection(self):
        df = pd.DataFrame({
            'txn_id': [1, 2, 3],
            'date': ['2024-01-01 10:00', '2024-01-02 11:00', '2024-01-03 14:00'],
            'description': ['Deposit A', 'Deposit B', 'Store'],
            'amount': [48500.0, 49200.0, 450.0],
            'deposit': [48500.0, 49200.0, 0.0],
            'withdrawal': [0.0, 0.0, 450.0],
            'balance': [50000.0, 99200.0, 98750.0]
        })
        res = detect_velocity_and_structuring(df)
        self.assertEqual(res.structuring_count, 2)
        self.assertGreater(res.structuring_score, 50.0)

    def test_end_to_end_engine_csv(self):
        # Test clean sample statement
        statement = parse_csv_or_excel('data/sample_statements/statement_clean.csv')
        engine = FraudDetectionEngine()
        verdict = engine.analyze(statement)
        self.assertEqual(verdict.risk_level, "LOW")
        self.assertLess(verdict.overall_risk_score, 25.0)

    def test_end_to_end_tampered_statement(self):
        # Test math tampered statement
        statement = parse_csv_or_excel('data/sample_statements/statement_math_tampered.csv')
        engine = FraudDetectionEngine()
        verdict = engine.analyze(statement)
        self.assertEqual(verdict.risk_level, "CRITICAL")
        self.assertGreaterEqual(verdict.overall_risk_score, 75.0)
        self.assertTrue(verdict.ledger_audit.is_tampered)

    def test_end_to_end_pdf_parsing(self):
        # Test parsing generated PDF
        statement = parse_pdf_statement('data/sample_statements/statement_clean.pdf')
        self.assertGreater(len(statement.transactions), 0)
        engine = FraudDetectionEngine()
        verdict = engine.analyze(statement)
        self.assertIsNotNone(verdict.verdict)


if __name__ == '__main__':
    unittest.main()

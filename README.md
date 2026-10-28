# 🛡️ End-to-End Forensic Bank Statement Fraud Detection

A production-grade forensic accounting and machine learning system for detecting document tampering, balance alterations, regulatory structuring (smurfing), and anomalous transactions in bank statements.

---

## 🌟 Key Capabilities

1. **Forensic Ledger Math Auditor**:
   - Validates the fundamental ledger equation at every row:
     $$\text{Balance}_t = \text{Balance}_{t-1} + \text{Deposit}_t - \text{Withdrawal}_t$$
   - Audits global opening vs. closing reconciliation:
     $$\text{Opening Balance} + \sum \text{Deposits} - \sum \text{Withdrawals} = \text{Closing Balance}$$
   - Pinpoints exact altered rows, manipulated balances, and closing deltas.

2. **Benford's Law Forensic Accounting Test**:
   - Evaluates the first-digit probability distribution:
     $$P(d) = \log_{10}\left(1 + \frac{1}{d}\right), \quad d \in \{1, \dots, 9\}$$
   - Computes Chi-square goodness-of-fit ($\chi^2$), p-value, and sample-size-calibrated Mean Absolute Deviation (MAD) to detect fabricated transaction amounts.

3. **Threshold Proximity (Rule 114B / PMLA) & Velocity Scanner**:
   - Evaluates analytical heuristics for regulatory threshold avoidance:
     - Under **Income Tax Rule 114B**, cash transactions of **₹50,000 or more** mandate quoting of PAN. High-frequency deposits in the **₹45,000 – ₹49,999 band** are flagged for KYC and source-of-funds verification.
     - Monitors high-value transactions relative to **PMLA Rule 3 CTR threshold (₹10,00,000 / 10 Lakhs)**.
   - Identifies rapid transaction bursts (UPI/IMPS churning) within short rolling windows.
   - Detects abnormal clustering of recurring round sums (₹10,000, ₹25,000, ₹50,000 multiples).

4. **Duplicate & Replay Detection**:
   - Detects identical and near-identical transactions within short time windows (48 hours) to prevent double-billing and replay attacks.

5. **Machine Learning Anomaly Detection**:
   - Unsupervised **Isolation Forest** coupled with robust statistical feature engineering (Z-scores, balance drainage ratios, rolling moving averages, day-of-week signals).
   - Generates multi-dimensional anomaly scores and human-explainable drivers.

6. **Interactive Streamlit Dashboard & Reporting**:
   - Upload PDF, CSV, or Excel bank statements or test with 5 pre-loaded scenarios.
   - Interactive Plotly visualizations for balance trajectories, Benford distributions, and anomaly landscapes.
   - One-click export of formal **Forensic PDF Audit Certificates**, structured **JSON reports**, and annotated CSVs.

---

## 🏗️ Project Architecture

```
End-to-End Bank Statement Fraud Detection/
├── data/
│   └── sample_statements/        # Pre-generated sample statements (Clean, Math Tampered, Structuring, etc.)
├── src/
│   ├── __init__.py
│   ├── config.py                 # Configuration parameters, thresholds, and weights
│   ├── engine.py                 # Master FraudDetectionEngine orchestrating all modules
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── csv_parser.py         # CSV & Excel statement parsing with column normalization
│   │   ├── pdf_parser.py         # Table and text extraction from PDF bank statements
│   │   └── statement_model.py    # Dataclasses for Transactions, Metadata, and Statements
│   ├── forensics/
│   │   ├── __init__.py
│   │   ├── ledger_math.py        # Row-by-row balance equation validation & reconciliation
│   │   ├── benford.py            # First-digit distribution and Chi-Square goodness-of-fit
│   │   ├── velocity.py           # Structuring (smurfing), rapid bursts, round numbers
│   │   └── duplicates.py         # Exact and near-duplicate transaction matching
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── feature_engineering.py# Statistical, behavioral, and drainage feature transforms
│   │   └── anomaly_detector.py   # Isolation Forest model and explainable anomaly scoring
│   ├── generator/
│   │   ├── __init__.py
│   │   └── synthetic_data.py     # Realistic bank statement & PDF generator
│   └── reports/
│       ├── __init__.py
│       └── report_generator.py   # Formal PDF Certificate & JSON export
├── tests/
│   ├── test_ledger_math.py       # Ledger math unit tests
│   └── test_forensics_and_engine.py # Benford, Velocity, CSV/PDF integration tests
├── app.py                        # Streamlit web application
├── run_app.sh                    # One-command dashboard launcher
├── requirements.txt              # Project dependencies
└── README.md                     # Documentation
```

---

## 🚀 Quick Start

### 1. Setup Virtual Environment & Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Run Tests

Verify all forensic rules and machine learning models:

```bash
python -m unittest discover tests
```

### 3. Launch the Interactive Dashboard

```bash
./run_app.sh
# OR
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

---

## 🧪 Built-In Test Scenarios

The system includes pre-configured test scenarios ready for instant evaluation:

| Scenario | Primary Pattern Tested | Expected Verdict |
| :--- | :--- | :--- |
| **Clean Legitimate Statement** | All ledger equations and Benford distributions match | `APPROVED (Low Risk)` |
| **Direct Ledger Math Tampering** | Artificially inflated balances (+₹1.5L, +₹1L) without ledger backing | `REJECTED (Critical Risk)` |
| **Rule 114B Threshold Proximity** | 4 cash deposits between ₹48,000 and ₹49,200 (PAN avoidance heuristic) | `SUSPICIOUS (High Risk)` |
| **Duplicate & Replay Frauds** | Clustered identical charges within 75 minutes | `MANUAL REVIEW (Moderate Risk)` |
| **Benford's Law Violation** | 65% of amounts fabricated, clustering heavily on 7, 8, and 9 | `SUSPICIOUS (High Risk)` |

---

## 📑 Generated Reports

Under the **Export PDF / JSON** tab in the dashboard, you can download:
1. **Forensic PDF Certificate**: A formal underwriter-ready certificate detailing account details, scorecard breakdown, detected discrepancies, and actionable recommendations.
2. **Machine-Readable JSON**: Complete audit verdict with full metadata for integration with credit underwriting pipelines.
3. **Scored CSV**: Full ledger with row-by-row flags (`is_math_tampered`, `is_structuring`, `ml_anomaly_score`, etc.).

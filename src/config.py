"""
Configuration settings, risk weights, and thresholds for Fraud Detection.
Calibrated for Indian Banking & Anti-Money Laundering (PMLA / FIU-IND) standards.
"""

from dataclasses import dataclass, field
from typing import Dict

@dataclass
class FraudDetectionConfig:
    # --- Ledger Math Verification ---
    tolerance: float = 0.01  # Decimal roundoff tolerance in INR (₹)
    
    # --- Velocity & Structuring (Indian Regulatory Standards) ---
    # Rule 114B (Income Tax Rules) mandates PAN for cash transactions >= ₹50,000.
    # Analytical heuristic: Flag deposits clustered immediately below PAN threshold (₹45,000 - ₹49,999).
    structuring_threshold_low: float = 45000.0   # Analytical lower bound
    structuring_threshold_high: float = 49999.0  # Just below ₹50,000 PAN requirement
    
    # High-Value PMLA CTR (Cash Transaction Report) Threshold (Rule 3 PMLA): ₹10,00,000 (10 Lakhs)
    pmla_ctr_threshold: float = 1000000.0
    
    burst_window_minutes: int = 120  # Time window for rapid successive bursts
    burst_count_threshold: int = 4   # Transactions within burst window considered suspicious
    
    # --- Round Number Anomalies ---
    round_amount_multiple: float = 5000.0  # Common round amount multiple in INR
    
    # --- Benford's Law ---
    benford_min_sample_size: int = 30  # Minimum transaction count for reliable Benford test
    benford_alpha: float = 0.05        # P-value cutoff for Chi-square anomaly
    
    # --- ML Anomaly Model ---
    contamination_rate: float = 0.05   # Expected anomaly proportion for Isolation Forest
    random_state: int = 42
    
    # --- Currency Configuration ---
    currency_symbol: str = "₹"
    currency_code: str = "INR"
    
    # --- Overall Risk Score Weights (Sum to 100) ---
    weights: Dict[str, float] = field(default_factory=lambda: {
        "ledger_math_tampering": 40.0,      # Direct balance alteration is proof of document tampering
        "structuring_smurfing": 20.0,       # Rule 114B / PMLA threshold avoidance heuristic
        "velocity_burst": 10.0,             # Rapid velocity bursts (UPI/IMPS churning)
        "duplicate_replay": 10.0,           # Suspicious duplicate debits/credits
        "benford_deviation": 10.0,          # First-digit distribution violation (fabricated figures)
        "ml_anomaly_outliers": 10.0         # Statistical & Isolation Forest outliers
    })
    
    # --- Risk Category Thresholds ---
    risk_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "low": 20.0,
        "medium": 50.0,
        "high": 75.0,
        # Above 75 is CRITICAL
    })

DEFAULT_CONFIG = FraudDetectionConfig()

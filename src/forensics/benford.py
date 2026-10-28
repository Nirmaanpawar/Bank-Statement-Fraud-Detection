"""
Benford's Law Forensic Accounting Module.
Analyzes the distribution of leading digits in transaction amounts to detect fabricated entries.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
import numpy as np
import pandas as pd
from scipy.stats import chisquare


BENFORD_EXPECTED_PROBS = {
    1: 0.30103,
    2: 0.17609,
    3: 0.12494,
    4: 0.09691,
    5: 0.07918,
    6: 0.06695,
    7: 0.05799,
    8: 0.05115,
    9: 0.04576
}


@dataclass
class DigitDistribution:
    digit: int
    observed_count: int
    observed_pct: float
    expected_pct: float
    deviation_pct: float


@dataclass
class BenfordAnalysisResult:
    sample_size: int
    is_applicable: bool
    chi2_stat: float
    p_value: float
    mad: float  # Mean Absolute Deviation
    conformity_level: str  # 'Close conformity', 'Acceptable', 'Marginally acceptable', 'Nonconformity'
    is_anomaly: bool
    fraud_score: float  # 0 to 100
    distribution: List[DigitDistribution] = field(default_factory=list)
    summary_message: str = ""


def get_first_digit(num: float) -> int:
    """Extract leading non-zero digit."""
    s = f"{abs(num):.6f}".lstrip('0').replace('.', '')
    for char in s:
        if char in '123456789':
            return int(char)
    return 0


def analyze_benford_law(
    amounts: pd.Series,
    min_sample_size: int = 30,
    alpha: float = 0.05
) -> BenfordAnalysisResult:
    """
    Performs Benford's Law analysis on transaction amounts.
    """
    valid_amounts = amounts.dropna()
    valid_amounts = valid_amounts[valid_amounts > 0.1]
    
    n = len(valid_amounts)
    if n < 10:
        return BenfordAnalysisResult(
            sample_size=n,
            is_applicable=False,
            chi2_stat=0.0,
            p_value=1.0,
            mad=0.0,
            conformity_level="Insufficient Data",
            is_anomaly=False,
            fraud_score=0.0,
            summary_message="Insufficient transactions (< 10) to perform Benford's Law analysis."
        )

    # Extract first digits
    digits = [get_first_digit(val) for val in valid_amounts]
    digits = [d for d in digits if 1 <= d <= 9]
    n_digits = len(digits)
    
    if n_digits == 0:
        return BenfordAnalysisResult(
            sample_size=0,
            is_applicable=False,
            chi2_stat=0.0,
            p_value=1.0,
            mad=0.0,
            conformity_level="Insufficient Data",
            is_anomaly=False,
            fraud_score=0.0,
            summary_message="No valid leading digits found."
        )

    counts = {d: 0 for d in range(1, 10)}
    for d in digits:
        counts[d] += 1
        
    observed_counts = np.array([counts[d] for d in range(1, 10)], dtype=float)
    expected_probs = np.array([BENFORD_EXPECTED_PROBS[d] for d in range(1, 10)], dtype=float)
    expected_counts = expected_probs * n_digits
    
    # Avoid zero expected counts for chi2
    expected_counts = np.maximum(expected_counts, 1e-6)
    
    # Chi-square Goodness of Fit Test
    chi2_stat, p_val = chisquare(observed_counts, f_exp=expected_counts)
    
    # Mean Absolute Deviation (MAD)
    obs_probs = observed_counts / n_digits
    mad = float(np.mean(np.abs(obs_probs - expected_probs)))
    
    # Conformity classification (Sample-size adjusted Nigrini criteria)
    # When sample size is modest (<100), random sampling variance causes natural MAD fluctuation.
    # Chi-square p-value tests if the observed deviation is statistically significant.
    mad_cutoff = max(0.025, 0.45 / np.sqrt(n_digits))
    
    if p_val >= alpha:
        # Statistically consistent with Benford distribution
        if mad <= 0.015:
            conformity = "Close conformity"
            fraud_score = 0.0
        else:
            conformity = "Acceptable conformity"
            fraud_score = 10.0
        is_anomaly = False
    else:
        # Statistically significant deviation
        if mad >= mad_cutoff or n_digits >= min_sample_size:
            conformity = "Nonconformity (Suspect Data)"
            is_anomaly = True
            fraud_score = min(100.0, 50.0 + (mad - 0.015) * 1500.0)
        else:
            conformity = "Marginally acceptable"
            is_anomaly = False
            fraud_score = 25.0

    # Build distribution list
    dist_list = []
    for d in range(1, 10):
        obs_c = counts[d]
        obs_p = (obs_c / n_digits) * 100.0
        exp_p = BENFORD_EXPECTED_PROBS[d] * 100.0
        dev_p = obs_p - exp_p
        dist_list.append(DigitDistribution(
            digit=d,
            observed_count=obs_c,
            observed_pct=round(obs_p, 2),
            expected_pct=round(exp_p, 2),
            deviation_pct=round(dev_p, 2)
        ))

    summary = (
        f"Benford's Law Result: {conformity} (MAD: {mad:.4f}, Chi² p-value: {p_val:.4e}). "
        f"{'Elevated risk of artificial or fabricated amount patterns detected.' if is_anomaly else 'Transaction leading digits conform to natural economic distributions.'}"
    )

    return BenfordAnalysisResult(
        sample_size=n_digits,
        is_applicable=n_digits >= min_sample_size,
        chi2_stat=round(float(chi2_stat), 3),
        p_value=round(float(p_val), 5),
        mad=round(mad, 5),
        conformity_level=conformity,
        is_anomaly=is_anomaly,
        fraud_score=round(fraud_score, 2),
        distribution=dist_list,
        summary_message=summary
    )

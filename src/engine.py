"""
Master Fraud Detection Engine.
Orchestrates Forensic Ledger Math, Benford's Law, Velocity/Structuring, Duplicates, and ML Models.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import pandas as pd

from .config import FraudDetectionConfig, DEFAULT_CONFIG
from .parsers.statement_model import ParsedStatement
from .forensics.ledger_math import audit_ledger_math, LedgerAuditResult
from .forensics.benford import analyze_benford_law, BenfordAnalysisResult
from .forensics.velocity import detect_velocity_and_structuring, VelocityAnalysisResult
from .forensics.duplicates import detect_duplicates, DuplicateAnalysisResult
from .ml.anomaly_detector import AnomalyDetector, AnomalyDetectionResult


@dataclass
class FraudAuditVerdict:
    overall_risk_score: float  # 0.0 to 100.0
    risk_level: str  # 'LOW', 'MODERATE', 'HIGH', 'CRITICAL'
    verdict: str  # 'APPROVED', 'MANUAL_REVIEW', 'SUSPICIOUS', 'REJECTED_FRAUD'
    summary_findings: List[str]
    recommendations: List[str]
    
    # Sub-module results
    ledger_audit: LedgerAuditResult
    benford_audit: BenfordAnalysisResult
    velocity_audit: VelocityAnalysisResult
    duplicate_audit: DuplicateAnalysisResult
    ml_audit: AnomalyDetectionResult
    
    # Component Scores
    score_breakdown: Dict[str, float]
    
    # Fully annotated transaction DataFrame
    annotated_df: pd.DataFrame


class FraudDetectionEngine:
    def __init__(self, config: Optional[FraudDetectionConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.ml_detector = AnomalyDetector(
            contamination=self.config.contamination_rate,
            random_state=self.config.random_state
        )

    def analyze(self, statement: ParsedStatement) -> FraudAuditVerdict:
        """
        Executes full forensic and machine learning audit on the parsed statement.
        """
        df = statement.df.copy()
        
        # 1. Forensic Ledger Math Audit
        ledger_res = audit_ledger_math(
            df=df,
            opening_balance=statement.metadata.opening_balance,
            tolerance=self.config.tolerance
        )

        # 2. Benford's Law Analysis
        benford_res = analyze_benford_law(
            amounts=df['amount'],
            min_sample_size=self.config.benford_min_sample_size,
            alpha=self.config.benford_alpha
        )

        # 3. Velocity & Structuring (Smurfing) Analysis
        velocity_res = detect_velocity_and_structuring(
            df=df,
            structuring_min=self.config.structuring_threshold_low,
            structuring_max=self.config.structuring_threshold_high,
            burst_window_minutes=self.config.burst_window_minutes,
            burst_threshold=self.config.burst_count_threshold,
            round_multiple=self.config.round_amount_multiple
        )

        # 4. Duplicate & Replay Detection
        duplicate_res = detect_duplicates(
            df=df,
            window_hours=48
        )

        # 5. ML Anomaly Detection (Isolation Forest)
        ml_res = self.ml_detector.fit_predict(df)

        # Build Annotated DataFrame with per-row fraud flags
        annotated_df = ml_res.df_scored.copy()
        
        # Mark math tampered rows
        tampered_indices = {d.row_index: d.details for d in ledger_res.discrepancies}
        annotated_df['is_math_tampered'] = [i in tampered_indices for i in range(len(annotated_df))]
        
        # Mark velocity & structuring
        structuring_txns = {f.txn_id for f in velocity_res.flagged_transactions if any(k in f.reason for k in ["Rule 114B", "Threshold", "Structuring"])}
        burst_txns = {f.txn_id for f in velocity_res.flagged_transactions if "Velocity" in f.reason}
        annotated_df['is_structuring'] = annotated_df['txn_id'].isin(structuring_txns)
        annotated_df['is_burst'] = annotated_df['txn_id'].isin(burst_txns)

        # Mark duplicates
        dup_txns = set()
        for g in duplicate_res.duplicate_groups:
            dup_txns.update(g.transaction_ids)
        annotated_df['is_duplicate'] = annotated_df['txn_id'].isin(dup_txns)

        # Compile row flags
        all_row_flags = []
        for i in range(len(annotated_df)):
            flags = []
            if i in tampered_indices:
                flags.append("Math Alteration")
            if annotated_df.iloc[i]['is_structuring']:
                flags.append("Threshold Proximity (Rule 114B)")
            if annotated_df.iloc[i]['is_burst']:
                flags.append("Velocity Burst")
            if annotated_df.iloc[i]['is_duplicate']:
                flags.append("Duplicate / Replay")
            if annotated_df.iloc[i]['ml_label'] == "Highly Anomalous":
                flags.append("ML Outlier")
            all_row_flags.append(", ".join(flags) if flags else "Clean")
            
        annotated_df['fraud_flags'] = all_row_flags

        # Compute Weighted Composite Score
        weights = self.config.weights
        w_total = sum(weights.values())
        
        math_contrib = (ledger_res.math_fraud_score * weights["ledger_math_tampering"]) / w_total
        struct_contrib = (velocity_res.structuring_score * weights["structuring_smurfing"]) / w_total
        burst_contrib = (velocity_res.velocity_score * weights["velocity_burst"]) / w_total
        dup_contrib = (duplicate_res.fraud_score * weights["duplicate_replay"]) / w_total
        benford_contrib = (benford_res.fraud_score * weights["benford_deviation"]) / w_total
        ml_contrib = (ml_res.ml_fraud_score * weights["ml_anomaly_outliers"]) / w_total

        overall_score = round(math_contrib + struct_contrib + burst_contrib + dup_contrib + benford_contrib + ml_contrib, 2)
        overall_score = min(100.0, max(0.0, overall_score))

        # Risk Classification
        if overall_score <= self.config.risk_thresholds["low"]:
            risk_level = "LOW"
            verdict = "APPROVED (Legitimate Statement)"
        elif overall_score <= self.config.risk_thresholds["medium"]:
            risk_level = "MODERATE"
            verdict = "MANUAL REVIEW RECOMMENDED"
        elif overall_score <= self.config.risk_thresholds["high"]:
            risk_level = "HIGH"
            verdict = "SUSPICIOUS (Likely Alterations / High Risk)"
        else:
            risk_level = "CRITICAL"
            verdict = "REJECTED (Severe Fraud / Tampering Detected)"

        # Override to CRITICAL if ledger math is explicitly tampered
        if ledger_res.is_tampered and overall_score < 75.0:
            overall_score = max(75.0, overall_score)
            risk_level = "CRITICAL"
            verdict = "REJECTED (Direct Ledger Math Alteration)"

        # Findings
        findings = []
        if ledger_res.is_tampered:
            findings.append(f"CRITICAL: Ledger balance tampering identified on {ledger_res.tampered_row_count} row(s). Closing balance mismatch of ₹{ledger_res.closing_discrepancy:,.2f}.")
        else:
            findings.append("Ledger Math: All running balances and reconciliations match perfectly.")

        if velocity_res.structuring_count > 0:
            findings.append(f"PMLA / Rule 114B Heuristic Alert: {velocity_res.structuring_count} transaction(s) clustered immediately below ₹50,000 PAN quoting threshold (₹45,000 - ₹49,999). Source verification advised.")

        if velocity_res.burst_count > 0:
            findings.append(f"Velocity Alert: {velocity_res.burst_count} rapid-burst transaction(s) detected.")

        if duplicate_res.has_duplicates:
            findings.append(f"Duplicate Alert: {duplicate_res.duplicate_group_count} duplicate cluster(s) totaling ₹{duplicate_res.total_duplicated_amount:,.2f}.")

        if benford_res.is_applicable and benford_res.is_anomaly:
            findings.append(f"Benford's Law Deviation: Nonconformity in leading digits (MAD: {benford_res.mad:.4f}, p-val: {benford_res.p_value:.3f}), indicating fabricated amounts.")

        if ml_res.anomalous_count > 0:
            findings.append(f"ML Outlier Model: Flagged {ml_res.anomalous_count} transactions with extreme multidimensional behavioral divergence.")

        # Recommendations (Indian Underwriting Context)
        recommendations = []
        if risk_level in ["CRITICAL", "HIGH"]:
            recommendations.append("Halt credit / loan underwriting processing immediately.")
            recommendations.append("Request electronic verification via RBI Account Aggregator (AA / Sahamati) or net-banking e-statement.")
            recommendations.append("Verify customer Permanent Account Number (PAN) via NSDL / Income Tax portal against account holder name.")
            recommendations.append("If threshold proximity transactions lack bonafide business rationale, escalate to Principal Officer for internal PMLA compliance review.")
        elif risk_level == "MODERATE":
            recommendations.append("Request secondary documentation: Income Tax Return (ITR-V), Form 16 / GST returns, and salary slips.")
            recommendations.append("Cross-reference reported balances against CIBIL / Experian credit bureau liabilities.")
        else:
            recommendations.append("Document satisfies all automated forensic integrity checks.")
            recommendations.append("Safe to proceed to automated credit appraisal.")

        score_breakdown = {
            "Ledger Math Tampering": round(ledger_res.math_fraud_score, 1),
            "Threshold Avoidance (Rule 114B)": round(velocity_res.structuring_score, 1),
            "Velocity Bursts": round(velocity_res.velocity_score, 1),
            "Duplicates & Replays": round(duplicate_res.fraud_score, 1),
            "Benford's Law Deviation": round(benford_res.fraud_score, 1),
            "ML Anomaly Outliers": round(ml_res.ml_fraud_score, 1)
        }

        return FraudAuditVerdict(
            overall_risk_score=overall_score,
            risk_level=risk_level,
            verdict=verdict,
            summary_findings=findings,
            recommendations=recommendations,
            ledger_audit=ledger_res,
            benford_audit=benford_res,
            velocity_audit=velocity_res,
            duplicate_audit=duplicate_res,
            ml_audit=ml_res,
            score_breakdown=score_breakdown,
            annotated_df=annotated_df
        )

"""
Machine Learning Anomaly Detection using Isolation Forest & Statistical Ensemble.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from .feature_engineering import extract_features


@dataclass
class AnomalyItem:
    txn_id: int
    date: str
    description: str
    amount: float
    balance: float
    anomaly_score: float
    anomaly_label: str
    top_reasons: List[str]


@dataclass
class AnomalyDetectionResult:
    anomalous_count: int
    suspicious_count: int
    total_count: int
    ml_fraud_score: float  # 0 to 100
    df_scored: pd.DataFrame
    anomalies: List[AnomalyItem] = field(default_factory=list)
    summary_message: str = ""


class AnomalyDetector:
    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.scaler = RobustScaler()
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=100
        )

    def fit_predict(self, df: pd.DataFrame) -> AnomalyDetectionResult:
        """
        Trains model on current statement features and detects transaction anomalies.
        """
        if df.empty:
            return AnomalyDetectionResult(
                anomalous_count=0,
                suspicious_count=0,
                total_count=0,
                ml_fraud_score=0.0,
                df_scored=df,
                summary_message="No transaction records available."
            )

        n = len(df)
        feats, feature_names = extract_features(df)
        X = feats.values
        
        # Scaling
        X_scaled = self.scaler.fit_transform(X)

        if n >= 10:
            # Fit Isolation Forest
            self.model.fit(X_scaled)
            # decision_function returns negative for outliers, positive for inliers
            raw_scores = self.model.decision_function(X_scaled)
            # Invert and normalize to [0, 1] range: higher score = more anomalous
            min_s, max_s = raw_scores.min(), raw_scores.max()
            if max_s > min_s:
                norm_scores = 1.0 - ((raw_scores - min_s) / (max_s - min_s))
            else:
                norm_scores = np.zeros(n)
        else:
            # Fallback for very short statements: use amount Z-score & drainage ratio
            z_scores = np.abs(feats['amount_zscore'].values)
            drainage = feats['balance_ratio'].values
            raw = (z_scores * 0.6) + (drainage * 0.4)
            norm_scores = np.clip(raw / 3.0, 0.0, 1.0)

        # Classify labels
        # Score > 0.8: Highly Anomalous
        # Score 0.6 - 0.8: Suspicious
        # Score < 0.6: Normal
        labels = []
        for s in norm_scores:
            if s >= 0.80:
                labels.append("Highly Anomalous")
            elif s >= 0.60:
                labels.append("Suspicious")
            else:
                labels.append("Normal")

        df_scored = df.copy()
        df_scored['ml_anomaly_score'] = np.round(norm_scores * 100.0, 2)
        df_scored['ml_label'] = labels

        # Generate reasons for top anomalies
        anomaly_list: List[AnomalyItem] = []
        for idx in range(n):
            if labels[idx] in ["Highly Anomalous", "Suspicious"]:
                row = df.iloc[idx]
                score = round(float(norm_scores[idx] * 100.0), 2)
                
                # Check contributing features
                reasons = []
                amt = float(row.get('amount', 0.0))
                z = feats.iloc[idx]['amount_zscore']
                drain = feats.iloc[idx]['balance_ratio']
                is_round = feats.iloc[idx]['is_round_1000']
                time_gap = feats.iloc[idx]['time_diff_hours']
                
                if z >= 2.5:
                    reasons.append(f"Amount (${amt:,.2f}) is statistically extreme (+{z:.1f} standard deviations)")
                if drain >= 0.70:
                    reasons.append(f"Depletes {drain*100:.0f}% of total account balance in a single transaction")
                if is_round == 1.0 and amt >= 2000.0:
                    reasons.append(f"Unusually large round-number withdrawal (${amt:,.2f})")
                if time_gap < 0.2:
                    reasons.append("Occurred within minutes of preceding transaction")
                if not reasons:
                    reasons.append("High multi-dimensional feature divergence from baseline behavior")

                anomaly_list.append(AnomalyItem(
                    txn_id=int(row.get('txn_id', idx + 1)),
                    date=str(row.get('date', '')),
                    description=str(row.get('description', '')),
                    amount=amt,
                    balance=float(row.get('balance', 0.0)),
                    anomaly_score=score,
                    anomaly_label=labels[idx],
                    top_reasons=reasons
                ))

        # Sort anomalies by score descending
        anomaly_list.sort(key=lambda x: x.anomaly_score, reverse=True)

        highly_count = sum(1 for l in labels if l == "Highly Anomalous")
        suspicious_count = sum(1 for l in labels if l == "Suspicious")
        
        # Overall ML Fraud Score (0 - 100)
        anomaly_ratio = (highly_count * 1.0 + suspicious_count * 0.4) / max(1, n)
        ml_score = min(100.0, anomaly_ratio * 100.0 * 2.5)

        summary = (
            f"ML Anomaly Model flagged {highly_count} highly anomalous and {suspicious_count} suspicious "
            f"transactions out of {n} total transactions."
        )

        return AnomalyDetectionResult(
            anomalous_count=highly_count,
            suspicious_count=suspicious_count,
            total_count=n,
            ml_fraud_score=round(ml_score, 2),
            df_scored=df_scored,
            anomalies=anomaly_list,
            summary_message=summary
        )

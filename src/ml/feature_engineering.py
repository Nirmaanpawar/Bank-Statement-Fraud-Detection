"""
Feature Engineering for Bank Statement Anomaly and Outlier Detection.
Extracts statistical, behavioral, temporal, and account drainage signals.
"""

from typing import Tuple, List
import pandas as pd
import numpy as np


FEATURE_NAMES = [
    'amount',
    'log_amount',
    'amount_zscore',
    'amount_to_median_ratio',
    'balance_ratio',
    'rolling_mean_ratio',
    'time_diff_hours',
    'is_weekend',
    'hour_of_day',
    'is_round_100',
    'is_round_1000',
    'is_credit'
]


def extract_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Transforms standardized transaction records into an ML feature matrix.
    """
    if df.empty:
        return pd.DataFrame(columns=FEATURE_NAMES), FEATURE_NAMES

    feats = pd.DataFrame(index=df.index)
    
    # 1. Base amounts
    amounts = df['amount'].fillna(0.0).astype(float)
    feats['amount'] = amounts
    feats['log_amount'] = np.log1p(np.maximum(0.0, amounts))
    
    # Statistical amount metrics
    mean_amt = amounts.mean() if len(amounts) > 0 else 1.0
    std_amt = amounts.std() if len(amounts) > 1 and amounts.std() > 0 else 1.0
    median_amt = amounts.median() if len(amounts) > 0 and amounts.median() > 0 else 1.0
    
    feats['amount_zscore'] = (amounts - mean_amt) / std_amt
    feats['amount_to_median_ratio'] = amounts / median_amt
    
    # 2. Balance Drainage Ratio (Amount / Prior Balance)
    balances = df['balance'].fillna(0.0).astype(float)
    prev_balances = balances.shift(1).fillna(balances.iloc[0] if len(balances) > 0 else 1.0)
    # Avoid zero division
    denom = np.where(np.abs(prev_balances) < 1.0, 1.0, np.abs(prev_balances))
    feats['balance_ratio'] = np.clip(amounts / denom, 0.0, 10.0)
    
    # 3. Rolling Window Ratio
    rolling_3 = amounts.rolling(window=3, min_periods=1).mean()
    rolling_safe = np.where(rolling_3 == 0, 1.0, rolling_3)
    feats['rolling_mean_ratio'] = np.clip(amounts / rolling_safe, 0.0, 10.0)
    
    # 4. Temporal Features
    if 'date' in df.columns:
        dates = pd.to_datetime(df['date'], errors='coerce')
        # If dates are missing or invalid, generate dummy series
        if dates.isna().all():
            dates = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='h')
        else:
            dates = dates.ffill().bfill()
    else:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='h')
        
    feats['is_weekend'] = dates.dt.dayofweek.isin([5, 6]).astype(float)
    feats['hour_of_day'] = dates.dt.hour.astype(float)
    
    # Time delta between successive transactions
    time_deltas = dates.diff().dt.total_seconds().fillna(3600.0) / 3600.0
    feats['time_diff_hours'] = np.clip(time_deltas, 0.0, 168.0) # Cap at 1 week
    
    # 5. Round Number Flags
    feats['is_round_100'] = ((amounts >= 100.0) & (amounts % 100 == 0)).astype(float)
    feats['is_round_1000'] = ((amounts >= 1000.0) & (amounts % 1000 == 0)).astype(float)
    
    # 6. Transaction Type Flag (Credit = 1, Debit = 0)
    if 'txn_type' in df.columns:
        feats['is_credit'] = (df['txn_type'].astype(str).str.lower().isin(['credit', 'deposit'])).astype(float)
    else:
        feats['is_credit'] = 0.0

    # Ensure no NaN or infinite values
    feats = feats.fillna(0.0).replace([np.inf, -np.inf], 0.0)
    
    return feats, FEATURE_NAMES

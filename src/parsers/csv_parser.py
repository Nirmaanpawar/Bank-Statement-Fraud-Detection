"""
Parser for CSV and Excel Bank Statements with intelligent column normalization.
"""

import io
import re
from typing import Union, BinaryIO, Optional, Dict
import pandas as pd
import numpy as np

from .statement_model import Transaction, StatementMetadata, ParsedStatement


def clean_currency_str(val) -> float:
    """Clean currency strings like '$ 1,234.50', '(50.00)', or '-$200' into a float."""
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ('nan', 'none', '-', 'null', ''):
        return 0.0
        
    is_negative = False
    if val_str.startswith('(') and val_str.endswith(')'):
        is_negative = True
        val_str = val_str[1:-1]
    elif val_str.startswith('-'):
        is_negative = True
        val_str = val_str[1:]
    elif val_str.endswith('dr') or val_str.endswith('DR'):
        is_negative = True
        val_str = val_str[:-2]
        
    # Remove currency symbols and formatting commas
    cleaned = re.sub(r'[^\d.]', '', val_str)
    try:
        num = float(cleaned)
        return -num if is_negative else num
    except (ValueError, TypeError):
        return 0.0


def map_column_names(columns: list) -> Dict[str, Optional[str]]:
    """
    Intelligently map statement columns to standard keys:
    - date_col
    - desc_col
    - deposit_col
    - withdrawal_col
    - amount_col
    - type_col
    - balance_col
    """
    mapping = {
        'date_col': None,
        'desc_col': None,
        'deposit_col': None,
        'withdrawal_col': None,
        'amount_col': None,
        'type_col': None,
        'balance_col': None
    }
    
    normalized_cols = {col: str(col).strip().lower().replace('_', ' ').replace('-', ' ') for col in columns}
    
    for original, norm in normalized_cols.items():
        # Description first to prevent 'cr' inside 'description' matching deposit
        if mapping['desc_col'] is None and any(k in norm for k in ['description', 'narration', 'particulars', 'details', 'memo', 'remark', 'payee', 'merchant']):
            mapping['desc_col'] = original
        elif mapping['date_col'] is None and any(k in norm for k in ['date', 'txn date', 'posting date', 'value date', 'time']):
            mapping['date_col'] = original
        elif mapping['balance_col'] is None and any(k in norm for k in ['balance', 'running balance', 'closing balance', 'ledger balance', 'current balance']):
            mapping['balance_col'] = original
        elif mapping['deposit_col'] is None and (any(k in norm for k in ['deposit', 'credit', 'paid in', 'money in', 'received']) or re.search(r'\bcr\b', norm)):
            mapping['deposit_col'] = original
        elif mapping['withdrawal_col'] is None and (any(k in norm for k in ['withdrawal', 'debit', 'paid out', 'money out', 'spent']) or re.search(r'\bdr\b', norm)):
            mapping['withdrawal_col'] = original
        elif mapping['type_col'] is None and any(k in norm for k in ['type', 'txn type', 'cr/dr', 'transaction type']):
            mapping['type_col'] = original
        elif mapping['amount_col'] is None and norm in ['amount', 'txn amount', 'total', 'transaction amount']:
            mapping['amount_col'] = original

    # Secondary fallback for description if not found (exclude id/txn columns)
    if mapping['desc_col'] is None:
        for original, norm in normalized_cols.items():
            if original not in mapping.values() and not any(k in norm for k in ['id', 'txn id', 'index', 'num', 'ref', 'code', 'date', 'bal']):
                mapping['desc_col'] = original
                break

    return mapping


def parse_csv_or_excel(
    file_or_path: Union[str, BinaryIO, io.BytesIO],
    file_type: str = "csv",
    custom_mapping: Optional[Dict[str, str]] = None
) -> ParsedStatement:
    """
    Parses a CSV or Excel bank statement and returns a structured ParsedStatement.
    """
    notes = []
    
    # Read tabular data
    if file_type.lower() in ("xlsx", "xls"):
        df_raw = pd.read_excel(file_or_path)
    else:
        # Try comma, semicolon, tab
        try:
            df_raw = pd.read_csv(file_or_path)
        except Exception:
            if hasattr(file_or_path, 'seek'):
                file_or_path.seek(0)
            df_raw = pd.read_csv(file_or_path, sep=';')
            
    df_raw = df_raw.dropna(how='all').reset_index(drop=True)
    
    mapping = map_column_names(df_raw.columns.tolist())
    if custom_mapping:
        mapping.update(custom_mapping)
        
    date_col = mapping['date_col']
    desc_col = mapping['desc_col']
    balance_col = mapping['balance_col']
    deposit_col = mapping['deposit_col']
    withdrawal_col = mapping['withdrawal_col']
    amount_col = mapping['amount_col']
    type_col = mapping['type_col']
    
    if not date_col:
        raise ValueError("Could not automatically identify Date column. Please verify the CSV header.")
    if not balance_col:
        raise ValueError("Could not automatically identify Balance column. Balance is required for ledger math forensics.")
        
    records = []
    cleaned_rows = []
    
    for idx, row in df_raw.iterrows():
        # Parse Date
        date_raw = row[date_col]
        try:
            parsed_date = pd.to_datetime(date_raw, errors='coerce')
            if pd.isna(parsed_date):
                parsed_date = pd.Timestamp.now()
        except Exception:
            parsed_date = pd.Timestamp.now()
            
        desc = str(row[desc_col]) if desc_col and not pd.isna(row[desc_col]) else f"Transaction {idx+1}"
        balance = clean_currency_str(row[balance_col])
        
        # Determine deposit, withdrawal, amount and type
        deposit = 0.0
        withdrawal = 0.0
        
        if deposit_col and withdrawal_col:
            deposit = max(0.0, clean_currency_str(row[deposit_col]))
            withdrawal = max(0.0, clean_currency_str(row[withdrawal_col]))
            if deposit > 0:
                amount = deposit
                txn_type = "credit"
            else:
                amount = withdrawal
                txn_type = "debit"
        elif amount_col:
            amt_val = clean_currency_str(row[amount_col])
            if type_col and not pd.isna(row[type_col]):
                t_str = str(row[type_col]).lower()
                if any(k in t_str for k in ['credit', 'cr', 'deposit', '+']):
                    txn_type = "credit"
                    amount = abs(amt_val)
                    deposit = amount
                else:
                    txn_type = "debit"
                    amount = abs(amt_val)
                    withdrawal = amount
            else:
                if amt_val < 0:
                    txn_type = "debit"
                    amount = abs(amt_val)
                    withdrawal = amount
                else:
                    txn_type = "credit"
                    amount = amt_val
                    deposit = amount
        else:
            notes.append(f"Row {idx+1}: Could not determine amount columns. Defaulting to 0.")
            amount = 0.0
            txn_type = "debit"

        txn = Transaction(
            txn_id=idx + 1,
            date=parsed_date.to_pydatetime() if hasattr(parsed_date, 'to_pydatetime') else parsed_date,
            description=desc,
            amount=amount,
            txn_type=txn_type,
            balance=balance,
            raw_data=row.to_dict()
        )
        records.append(txn)
        
        cleaned_rows.append({
            'txn_id': txn.txn_id,
            'date': txn.date,
            'description': txn.description,
            'amount': txn.amount,
            'txn_type': txn.txn_type,
            'deposit': deposit,
            'withdrawal': withdrawal,
            'balance': txn.balance
        })

    std_df = pd.DataFrame(cleaned_rows)
    
    # Metadata derivation: calculate initial balance prior to first transaction
    opening_bal = (records[0].balance - records[0].deposit + records[0].withdrawal) if records else 0.0
    closing_bal = records[-1].balance if records else 0.0
    start_date = str(std_df['date'].min()) if not std_df.empty else None
    end_date = str(std_df['date'].max()) if not std_df.empty else None
    
    metadata = StatementMetadata(
        bank_name="Imported Ledger",
        account_number="ACC-" + str(abs(hash(str(file_or_path))))[:8],
        statement_period_start=start_date,
        statement_period_end=end_date,
        opening_balance=opening_bal,
        closing_balance=closing_bal
    )
    
    return ParsedStatement(
        metadata=metadata,
        transactions=records,
        df=std_df,
        parsing_notes=notes
    )

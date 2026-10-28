"""
PDF Bank Statement Parser using pdfplumber and pypdf.
Extracts table data, header metadata, and text-based line items.
"""

import io
import re
from typing import Union, BinaryIO, List, Dict, Any, Optional
import pandas as pd
import pdfplumber
from pypdf import PdfReader

from .statement_model import Transaction, StatementMetadata, ParsedStatement
from .csv_parser import clean_currency_str, map_column_names


def extract_pdf_metadata(file_or_path: Union[str, BinaryIO, io.BytesIO]) -> StatementMetadata:
    """Extract metadata (account number, period, bank) from PDF text header."""
    meta = StatementMetadata()
    try:
        reader = PdfReader(file_or_path)
        meta.page_count = len(reader.pages)
        full_first_page_text = reader.pages[0].extract_text() if len(reader.pages) > 0 else ""
        
        # Detect Bank Name
        bank_keywords = ["Chase", "Bank of America", "Wells Fargo", "Citibank", "HSBC", "Barclays", "PNC", "TD Bank", "Standard Chartered", "HDFC Bank", "ICICI Bank", "State Bank"]
        for b in bank_keywords:
            if re.search(r'\b' + re.escape(b) + r'\b', full_first_page_text, re.IGNORECASE):
                meta.bank_name = b
                break
                
        # Account Number
        acct_match = re.search(r'(?:Account|Acct|A/C)\s*(?:Number|No\.?|#)?\s*[:\-]?\s*([X\*\d\-]{6,20})', full_first_page_text, re.IGNORECASE)
        if acct_match:
            meta.account_number = acct_match.group(1)
            
        # Opening / Closing Balance regex
        op_match = re.search(r'(?:Opening|Beginning|Previous)\s+Balance\s*[:\-]?\s*[\$€£₹]?\s*([\d,]+\.\d{2})', full_first_page_text, re.IGNORECASE)
        if op_match:
            meta.opening_balance = clean_currency_str(op_match.group(1))
            
        cl_match = re.search(r'(?:Closing|Ending|New)\s+Balance\s*[:\-]?\s*[\$€£₹]?\s*([\d,]+\.\d{2})', full_first_page_text, re.IGNORECASE)
        if cl_match:
            meta.closing_balance = clean_currency_str(cl_match.group(1))
            
    except Exception:
        pass
    return meta


def parse_pdf_statement(file_or_path: Union[str, BinaryIO, io.BytesIO]) -> ParsedStatement:
    """
    Parses a PDF bank statement into a structured ParsedStatement.
    Extracts tabular transactions across all pages.
    """
    metadata = extract_pdf_metadata(file_or_path)
    
    # Reset stream if bytes
    if hasattr(file_or_path, 'seek'):
        file_or_path.seek(0)
        
    extracted_rows: List[Dict[str, Any]] = []
    notes: List[str] = []
    
    with pdfplumber.open(file_or_path) as pdf:
        metadata.page_count = len(pdf.pages)
        raw_tables = []
        
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if tables:
                for t in tables:
                    if len(t) >= 2: # At least header + 1 row
                        raw_tables.append(t)
                        
        if raw_tables:
            # Process tables
            for table in raw_tables:
                header = [str(col).replace('\n', ' ').strip() if col else f"col_{i}" for i, col in enumerate(table[0])]
                mapping = map_column_names(header)
                
                # Check if this table has transaction fields (Date & Balance)
                if not (mapping['date_col'] and mapping['balance_col']):
                    continue
                    
                df_page = pd.DataFrame(table[1:], columns=header)
                
                for _, row in df_page.iterrows():
                    d_val = row.get(mapping['date_col'])
                    b_val = row.get(mapping['balance_col'])
                    if not d_val or not b_val:
                        continue
                        
                    date_parsed = pd.to_datetime(str(d_val).replace('\n', ' '), errors='coerce')
                    if pd.isna(date_parsed):
                        continue
                        
                    desc = str(row.get(mapping['desc_col'], "Transaction")).replace('\n', ' ') if mapping['desc_col'] else "Transaction"
                    bal = clean_currency_str(b_val)
                    
                    dep = 0.0
                    wdr = 0.0
                    if mapping['deposit_col'] and mapping['withdrawal_col']:
                        dep = max(0.0, clean_currency_str(row.get(mapping['deposit_col'])))
                        wdr = max(0.0, clean_currency_str(row.get(mapping['withdrawal_col'])))
                        amt = dep if dep > 0 else wdr
                        t_type = "credit" if dep > 0 else "debit"
                    elif mapping['amount_col']:
                        val = clean_currency_str(row.get(mapping['amount_col']))
                        amt = abs(val)
                        t_type = "credit" if val > 0 else "debit"
                        if t_type == "credit":
                            dep = amt
                        else:
                            wdr = amt
                    else:
                        amt = 0.0
                        t_type = "debit"
                        
                    extracted_rows.append({
                        'date': date_parsed,
                        'description': desc,
                        'amount': amt,
                        'txn_type': t_type,
                        'deposit': dep,
                        'withdrawal': wdr,
                        'balance': bal,
                        'raw_data': row.to_dict()
                    })

    if not extracted_rows:
        notes.append("Standard table extraction yielded no structured rows. Running text pattern fallback.")
        # Fallback text regex parsing
        if hasattr(file_or_path, 'seek'):
            file_or_path.seek(0)
            
        with pdfplumber.open(file_or_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = text.split("\n")
                for line in lines:
                    # Match: Date Description Amount Balance
                    # e.g.: 2024-01-15 Supermarket Grocery -$45.20 $1240.50
                    # or: 01/15/2024 Payroll Direct Deposit 2500.00 3740.50
                    m = re.match(r'^(\d{2,4}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\s+(.+?)\s+([\-\+]?\$?[\d,]+\.\d{2})\s+(\$?[\d,]+\.\d{2})$', line.strip())
                    if m:
                        d_str, desc, amt_str, bal_str = m.groups()
                        date_parsed = pd.to_datetime(d_str, errors='coerce')
                        if pd.isna(date_parsed):
                            continue
                        amt_val = clean_currency_str(amt_str)
                        bal_val = clean_currency_str(bal_str)
                        t_type = "debit" if amt_val < 0 or '-' in amt_str else "credit"
                        amt_abs = abs(amt_val)
                        extracted_rows.append({
                            'date': date_parsed,
                            'description': desc.strip(),
                            'amount': amt_abs,
                            'txn_type': t_type,
                            'deposit': amt_abs if t_type == "credit" else 0.0,
                            'withdrawal': amt_abs if t_type == "debit" else 0.0,
                            'balance': bal_val,
                            'raw_data': {'line': line}
                        })

    transactions: List[Transaction] = []
    table_records = []
    
    for idx, r in enumerate(extracted_rows):
        txn = Transaction(
            txn_id=idx + 1,
            date=r['date'].to_pydatetime() if hasattr(r['date'], 'to_pydatetime') else r['date'],
            description=r['description'],
            amount=r['amount'],
            txn_type=r['txn_type'],
            balance=r['balance'],
            raw_data=r['raw_data']
        )
        transactions.append(txn)
        table_records.append({
            'txn_id': txn.txn_id,
            'date': txn.date,
            'description': txn.description,
            'amount': txn.amount,
            'txn_type': txn.txn_type,
            'deposit': r['deposit'],
            'withdrawal': r['withdrawal'],
            'balance': txn.balance
        })

    df = pd.DataFrame(table_records)
    if metadata.opening_balance is None and transactions:
        metadata.opening_balance = transactions[0].balance - transactions[0].deposit + transactions[0].withdrawal
    if metadata.closing_balance is None and transactions:
        metadata.closing_balance = transactions[-1].balance
        
    return ParsedStatement(
        metadata=metadata,
        transactions=transactions,
        df=df,
        parsing_notes=notes
    )

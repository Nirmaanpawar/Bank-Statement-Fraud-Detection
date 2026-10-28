"""
Synthetic Bank Statement Generator calibrated for Indian Banking.
Generates realistic Indian bank statements (SBI, HDFC, ICICI) with configurable fraud injection:
- Clean / Legitimate
- Tampered Running Balances
- Rule 114B / PMLA Threshold Avoidance (Cash deposits ₹45,000 - ₹49,999)
- Duplicate / Replay Frauds
- Benford's Law Violators (Fabricated Figures)
Generates both CSV files and realistic PDF statements formatted with IFSC, PAN, and INR (₹).
"""

import os
import random
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any, Optional
import pandas as pd
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


EXPENSE_DESCRIPTIONS = [
    "UPI/Swiggy/FoodOrder", "UPI/Zomato/Restaurant", "Reliance Retail Superstore",
    "D-Mart Hypermarket", "Indian Oil Fuel Pump", "Uber India Mobility",
    "Amazon Pay India", "Flipkart Internet Pvt Ltd", "Airtel Postpaid Bill",
    "Tata Power Electricity", "Apollo Pharmacy Healthcare", "Zerodha Broking Deposit",
    "BookMyShow Entertainment", "IRCTC Rail E-Ticket", "MakeMyTrip India Flight",
    "Blinkit Grocery Express", "Cult.fit Fitness Pass", "Netflix India Subscription"
]

INCOME_DESCRIPTIONS = [
    "NEFT/Salary/Tech Mahindra Ltd", "RTGS/Consulting Settlement",
    "IMPS/Client Payout/Acme", "UPI/Received from Amit Sharma",
    "Dividend/TCS Ltd Distribution", "NACH/Mutual Fund SIP Redemption"
]


def generate_synthetic_statement(
    scenario: str = "clean",
    num_transactions: int = 40,
    initial_balance: float = 250000.0,
    start_date: Optional[datetime] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Generates synthetic transaction dataframe and metadata for Indian banking scenarios.
    """
    if start_date is None:
        start_date = datetime.now() - timedelta(days=45)

    random.seed(42)
    np.random.seed(42)

    current_balance = float(initial_balance)
    opening_balance = float(initial_balance)
    current_time = start_date

    records = []

    for i in range(1, num_transactions + 1):
        time_jump_hours = random.choices([4, 12, 24, 48, 72], weights=[0.2, 0.4, 0.25, 0.1, 0.05])[0]
        current_time += timedelta(hours=time_jump_hours, minutes=random.randint(0, 59))

        is_deposit = random.random() < 0.15

        if is_deposit:
            desc = random.choice(INCOME_DESCRIPTIONS)
            amt = round(float(np.random.lognormal(mean=10.5, sigma=0.5)), 2) # ~₹35,000 - ₹95,000
            amt = max(5000.0, amt)
            dep = amt
            wdr = 0.0
            t_type = "credit"
            current_balance += dep
        else:
            desc = random.choice(EXPENSE_DESCRIPTIONS)
            amt = round(float(np.random.lognormal(mean=7.2, sigma=0.8)), 2) # ~₹500 - ₹5,000
            amt = max(50.0, amt)
            dep = 0.0
            wdr = amt
            t_type = "debit"
            current_balance -= wdr

        records.append({
            'txn_id': i,
            'date': current_time.strftime('%Y-%m-%d %H:%M'),
            'description': desc,
            'amount': round(amt, 2),
            'txn_type': t_type,
            'deposit': round(dep, 2),
            'withdrawal': round(wdr, 2),
            'balance': round(current_balance, 2)
        })

    df = pd.DataFrame(records)
    scenario_notes = []

    if scenario == "math_tampered":
        idx_tamper_1 = min(18, len(df) - 1)
        idx_tamper_2 = min(32, len(df) - 1)
        
        # Inject +₹1,50,000 and +₹1,00,000 balance inflation
        df.at[idx_tamper_1, 'balance'] = round(df.at[idx_tamper_1, 'balance'] + 150000.0, 2)
        df.at[idx_tamper_2, 'balance'] = round(df.at[idx_tamper_2, 'balance'] + 100000.0, 2)
        scenario_notes.append("Injected +₹1,50,000 and +₹1,00,000 balance inflation on specific rows without ledger adjustment.")

    elif scenario == "structuring":
        # Indian Structuring Pattern: Multiple cash deposits just below ₹50,000 PAN threshold
        struct_amounts = [48500.00, 49200.00, 49000.00, 48000.00]
        for s_idx, s_amt in enumerate(struct_amounts):
            target_idx = 8 + (s_idx * 6)
            if target_idx < len(df):
                df.at[target_idx, 'description'] = f"CDM Cash Deposit Branch #{random.randint(100, 999)}"
                df.at[target_idx, 'txn_type'] = "credit"
                df.at[target_idx, 'deposit'] = s_amt
                df.at[target_idx, 'withdrawal'] = 0.0
                df.at[target_idx, 'amount'] = s_amt
                
        # Recompute subsequent balances
        bal = opening_balance
        for i in range(len(df)):
            bal = bal + df.at[i, 'deposit'] - df.at[i, 'withdrawal']
            df.at[i, 'balance'] = round(bal, 2)
        scenario_notes.append("Injected 4 cash deposits between ₹48,000 and ₹49,200 to test Rule 114B PAN threshold avoidance heuristic.")

    elif scenario == "duplicates":
        for dup_target in [10, 22]:
            if dup_target < len(df) - 1:
                dup_row = df.iloc[dup_target].copy()
                dup_date = pd.to_datetime(dup_row['date']) + timedelta(hours=1, minutes=15)
                df.at[dup_target + 1, 'description'] = dup_row['description']
                df.at[dup_target + 1, 'amount'] = dup_row['amount']
                df.at[dup_target + 1, 'deposit'] = dup_row['deposit']
                df.at[dup_target + 1, 'withdrawal'] = dup_row['withdrawal']
                df.at[dup_target + 1, 'txn_type'] = dup_row['txn_type']
                df.at[dup_target + 1, 'date'] = dup_date.strftime('%Y-%m-%d %H:%M')
                
        bal = opening_balance
        for i in range(len(df)):
            bal = bal + df.at[i, 'deposit'] - df.at[i, 'withdrawal']
            df.at[i, 'balance'] = round(bal, 2)
        scenario_notes.append("Injected duplicate debit transactions within 75 minutes of each other.")

    elif scenario == "benford_tampered":
        # Override 65% of amounts with fabricated numbers starting with 7, 8, and 9
        for i in range(len(df)):
            if random.random() < 0.65:
                lead_digit = random.choice([7, 8, 9])
                fake_amt = float(f"{lead_digit}{random.randint(10, 99)}{random.randint(10, 99)}.{random.randint(10, 99)}")
                df.at[i, 'amount'] = fake_amt
                if df.at[i, 'txn_type'] == 'credit':
                    df.at[i, 'deposit'] = fake_amt
                else:
                    df.at[i, 'withdrawal'] = fake_amt
                    
        bal = opening_balance
        for i in range(len(df)):
            bal = bal + df.at[i, 'deposit'] - df.at[i, 'withdrawal']
            df.at[i, 'balance'] = round(bal, 2)
        scenario_notes.append("Overwrote 65% of transaction amounts with fabricated digits clustering on 7, 8, and 9.")

    meta = {
        'scenario': scenario,
        'bank_name': "State Bank of India",
        'branch_name': "Nariman Point Branch, Mumbai",
        'ifsc_code': "SBIN0001234",
        'account_number': "38291044582",
        'account_holder': "Rajesh K. Sharma",
        'pan_number': "ABCPS1234F",
        'opening_balance': opening_balance,
        'closing_balance': float(df.iloc[-1]['balance']) if not df.empty else opening_balance,
        'total_deposits': float(df['deposit'].sum()),
        'total_withdrawals': float(df['withdrawal'].sum()),
        'currency': "INR",
        'notes': scenario_notes
    }

    return df, meta


def generate_pdf_statement(df: pd.DataFrame, meta: Dict[str, Any], output_path: str):
    """
    Renders an Indian bank statement PDF with IFSC, Branch, and PAN details.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'BankTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#003366')
    )
    subtitle_style = ParagraphStyle(
        'BankSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#4a5568')
    )
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#003366')
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10
    )
    header_cell_style = ParagraphStyle(
        'HeaderCellText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    story = []

    # Bank Header
    story.append(Paragraph(f"<b>{meta.get('bank_name', 'State Bank of India')}</b>", title_style))
    story.append(Paragraph(f"Branch: {meta.get('branch_name', 'Mumbai Main')} | IFSC: {meta.get('ifsc_code', 'SBIN0001234')} | MICR: 400002001", subtitle_style))
    story.append(Spacer(1, 12))

    # Account Summary Block
    summary_data = [
        [
            Paragraph(f"<b>Account Holder:</b> {meta.get('account_holder', 'Rajesh K. Sharma')}", subtitle_style),
            Paragraph(f"<b>Statement Period:</b> {df.iloc[0]['date'][:10]} to {df.iloc[-1]['date'][:10]}", subtitle_style)
        ],
        [
            Paragraph(f"<b>Account Number:</b> {meta.get('account_number', '38291044582')}", subtitle_style),
            Paragraph(f"<b>Opening Balance:</b> ₹{meta.get('opening_balance', 0.0):,.2f}", subtitle_style)
        ],
        [
            Paragraph(f"<b>PAN:</b> {meta.get('pan_number', 'ABCPS1234F')}", subtitle_style),
            Paragraph(f"<b>Closing Balance:</b> ₹{meta.get('closing_balance', 0.0):,.2f}", subtitle_style)
        ],
        [
            Paragraph(f"<b>Total Deposits (+):</b> ₹{meta.get('total_deposits', 0.0):,.2f}", subtitle_style),
            Paragraph(f"<b>Total Withdrawals (-):</b> ₹{meta.get('total_withdrawals', 0.0):,.2f}", subtitle_style)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[270, 270])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # Transaction Table
    story.append(Paragraph("<b>ACCOUNT STATEMENT TRANSACTIONS (INR)</b>", section_style))
    story.append(Spacer(1, 6))

    table_data = [[
        Paragraph("Date", header_cell_style),
        Paragraph("Narration / Description", header_cell_style),
        Paragraph("Withdrawal (Dr)", header_cell_style),
        Paragraph("Deposit (Cr)", header_cell_style),
        Paragraph("Balance (INR)", header_cell_style)
    ]]

    for _, row in df.iterrows():
        w_str = f"₹{row['withdrawal']:,.2f}" if row['withdrawal'] > 0 else "-"
        d_str = f"₹{row['deposit']:,.2f}" if row['deposit'] > 0 else "-"
        table_data.append([
            Paragraph(str(row['date'])[:10], cell_style),
            Paragraph(str(row['description'])[:32], cell_style),
            Paragraph(w_str, cell_style),
            Paragraph(d_str, cell_style),
            Paragraph(f"₹{row['balance']:,.2f}", cell_style)
        ])

    txn_table = Table(table_data, colWidths=[65, 215, 80, 80, 100], repeatRows=1)
    txn_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(txn_table)

    doc.build(story)


def generate_all_sample_files(target_dir: str):
    """
    Generates all sample bank statement CSVs and PDFs in target_dir.
    """
    os.makedirs(target_dir, exist_ok=True)
    scenarios = ["clean", "math_tampered", "structuring", "duplicates", "benford_tampered"]
    
    file_registry = []
    for sc in scenarios:
        df, meta = generate_synthetic_statement(scenario=sc, num_transactions=40)
        
        csv_path = os.path.join(target_dir, f"statement_{sc}.csv")
        pdf_path = os.path.join(target_dir, f"statement_{sc}.pdf")
        
        df.to_csv(csv_path, index=False)
        generate_pdf_statement(df, meta, pdf_path)
        
        file_registry.append({
            'scenario': sc,
            'csv_path': csv_path,
            'pdf_path': pdf_path,
            'rows': len(df)
        })
        
    return file_registry

"""
Forensic Report Generator: JSON and PDF Export.
Produces comprehensive audit certifications for underwriting and compliance.
"""

import json
from datetime import datetime
from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from ..engine import FraudAuditVerdict
from ..parsers.statement_model import StatementMetadata


def generate_json_report(verdict: FraudAuditVerdict, metadata: StatementMetadata) -> Dict[str, Any]:
    """
    Serializes full audit verdict and metadata into a JSON-compliant dict.
    """
    report = {
        "report_id": f"AUDIT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "generated_at": datetime.now().isoformat(),
        "account_metadata": {
            "bank_name": metadata.bank_name,
            "account_number": metadata.account_number,
            "account_holder": metadata.account_holder,
            "opening_balance": metadata.opening_balance,
            "closing_balance": metadata.closing_balance,
            "statement_period": f"{metadata.statement_period_start or 'N/A'} to {metadata.statement_period_end or 'N/A'}"
        },
        "verdict": {
            "overall_risk_score": verdict.overall_risk_score,
            "risk_level": verdict.risk_level,
            "status": verdict.verdict,
            "score_breakdown": verdict.score_breakdown
        },
        "forensic_audit_modules": {
            "ledger_math": {
                "is_tampered": verdict.ledger_audit.is_tampered,
                "tampered_rows_count": verdict.ledger_audit.tampered_row_count,
                "reconciliation_valid": verdict.ledger_audit.reconciliation_valid,
                "closing_discrepancy": verdict.ledger_audit.closing_discrepancy,
                "discrepancies": [
                    {
                        "row": d.row_index,
                        "txn_id": d.txn_id,
                        "date": d.date,
                        "description": d.description,
                        "reported_balance": d.reported_balance,
                        "expected_balance": d.expected_balance,
                        "discrepancy": d.discrepancy,
                        "details": d.details
                    }
                    for d in verdict.ledger_audit.discrepancies
                ]
            },
            "benford_law": {
                "applicable": verdict.benford_audit.is_applicable,
                "conformity_level": verdict.benford_audit.conformity_level,
                "chi2_stat": verdict.benford_audit.chi2_stat,
                "p_value": verdict.benford_audit.p_value,
                "mad": verdict.benford_audit.mad,
                "is_anomaly": verdict.benford_audit.is_anomaly
            },
            "velocity_and_structuring": {
                "structuring_count": verdict.velocity_audit.structuring_count,
                "burst_count": verdict.velocity_audit.burst_count,
                "round_amount_count": verdict.velocity_audit.round_amount_count,
                "total_flagged": verdict.velocity_audit.total_flagged
            },
            "duplicate_transactions": {
                "has_duplicates": verdict.duplicate_audit.has_duplicates,
                "duplicate_group_count": verdict.duplicate_audit.duplicate_group_count,
                "total_duplicated_amount": verdict.duplicate_audit.total_duplicated_amount
            },
            "machine_learning_outliers": {
                "anomalous_count": verdict.ml_audit.anomalous_count,
                "suspicious_count": verdict.ml_audit.suspicious_count,
                "ml_fraud_score": verdict.ml_audit.ml_fraud_score
            }
        },
        "key_findings": verdict.summary_findings,
        "recommendations": verdict.recommendations
    }
    return report


def generate_pdf_report(verdict: FraudAuditVerdict, metadata: StatementMetadata, output_path: str):
    """
    Renders a formal Forensic Fraud Audit Certificate as a downloadable PDF.
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
    
    header_style = ParagraphStyle(
        'AuditHeader',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f2b48')
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12
    )
    body_text = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12
    )
    alert_text = ParagraphStyle(
        'AlertText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.white
    )

    story = []

    # Title & Certification Header
    story.append(Paragraph("<b>FORENSIC BANK STATEMENT AUDIT CERTIFICATE</b>", header_style))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y - %H:%M:%S UTC')} | Forensic Engine v1.0", body_text))
    story.append(Spacer(1, 10))

    # Risk Badge Banner
    risk_color_map = {
        'LOW': colors.HexColor('#276749'),        # Green
        'MODERATE': colors.HexColor('#d69e2e'),   # Gold / Orange
        'HIGH': colors.HexColor('#c53030'),       # Red
        'CRITICAL': colors.HexColor('#742a2a')    # Dark Crimson
    }
    badge_bg = risk_color_map.get(verdict.risk_level, colors.HexColor('#c53030'))
    
    banner_data = [[
        Paragraph(f"RISK RATING: <b>{verdict.risk_level}</b> | OVERALL FRAUD SCORE: <b>{verdict.overall_risk_score} / 100</b>", alert_text),
        Paragraph(f"VERDICT: <b>{verdict.verdict}</b>", alert_text)
    ]]
    banner_table = Table(banner_data, colWidths=[320, 220])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), badge_bg),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 14))

    # Statement Metadata Overview
    meta_data = [
        [
            Paragraph(f"<b>Issuing Bank:</b> {metadata.bank_name}", body_text),
            Paragraph(f"<b>Account Holder:</b> {metadata.account_holder}", body_text)
        ],
        [
            Paragraph(f"<b>Account Number:</b> {metadata.account_number}", body_text),
            Paragraph(f"<b>Period:</b> {metadata.statement_period_start or 'N/A'} to {metadata.statement_period_end or 'N/A'}", body_text)
        ],
        [
            Paragraph(f"<b>Opening Balance:</b> ₹{metadata.opening_balance or 0.0:,.2f}", body_text),
            Paragraph(f"<b>Closing Balance:</b> ₹{metadata.closing_balance or 0.0:,.2f}", body_text)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#edf2f7')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Scorecard Breakdown Table
    story.append(Paragraph("<b>1. FORENSIC SCORECARD BREAKDOWN</b>", body_bold))
    story.append(Spacer(1, 4))
    
    score_rows = [[Paragraph("Audit Component", body_bold), Paragraph("Score (0-100)", body_bold), Paragraph("Status", body_bold)]]
    for comp, sc in verdict.score_breakdown.items():
        st_text = "PASS" if sc < 25 else ("REVIEW" if sc < 60 else "FAIL")
        score_rows.append([
            Paragraph(comp, body_text),
            Paragraph(f"{sc:.1f}", body_text),
            Paragraph(st_text, body_bold)
        ])
    sc_table = Table(score_rows, colWidths=[240, 150, 150])
    sc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(sc_table)
    story.append(Spacer(1, 12))

    # Ledger Math Verification
    story.append(Paragraph("<b>2. LEDGER RUNNING BALANCE AUDIT</b>", body_bold))
    story.append(Spacer(1, 4))
    if verdict.ledger_audit.is_tampered:
        math_summary = f"<font color='#c53030'><b>FAILED:</b> {verdict.ledger_audit.tampered_row_count} balance discrepancy rows found. Closing balance reconciliation mismatch of ₹{verdict.ledger_audit.closing_discrepancy:,.2f}.</font>"
    else:
        math_summary = "<font color='#276749'><b>PASSED:</b> All running balance equations and opening/closing reconciliations verified 100% consistent.</font>"
    story.append(Paragraph(math_summary, body_text))
    story.append(Spacer(1, 10))

    # Key Findings
    story.append(Paragraph("<b>3. EXECUTIVE FORENSIC FINDINGS</b>", body_bold))
    story.append(Spacer(1, 4))
    for f in verdict.summary_findings:
        story.append(Paragraph(f"• {f}", body_text))
    story.append(Spacer(1, 10))

    # Underwriter Recommendations
    story.append(Paragraph("<b>4. UNDERWRITING & COMPLIANCE ACTION PLAN</b>", body_bold))
    story.append(Spacer(1, 4))
    for r in verdict.recommendations:
        story.append(Paragraph(f"• <b>{r}</b>", body_text))
    story.append(Spacer(1, 15))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#a0aec0')))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Automated Forensic Accounting Audit. Certified against Indian PMLA / FIU-IND guidelines, Rule 114B heuristics, and ledger integrity standards.", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, textColor=colors.gray)))

    doc.build(story)

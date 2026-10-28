"""
End-to-End Bank Statement Fraud Detection Dashboard.
Built with Streamlit, Plotly, Scikit-Learn, ReportLab, and Forensic Accounting Analytics.
"""

import os
import io
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from src.config import FraudDetectionConfig, DEFAULT_CONFIG
from src.parsers.csv_parser import parse_csv_or_excel
from src.parsers.pdf_parser import parse_pdf_statement
from src.parsers.statement_model import ParsedStatement
from src.engine import FraudDetectionEngine, FraudAuditVerdict
from src.reports.report_generator import generate_json_report, generate_pdf_report
from src.generator.synthetic_data import generate_synthetic_statement


st.set_page_config(
    page_title="Forensic Ledger - Bank Statement Fraud Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #64748b;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .risk-banner {
        padding: 16px 20px;
        border-radius: 8px;
        color: white;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 18px;
        font-weight: 600;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)


def load_statement(uploaded_file, sample_scenario=None) -> ParsedStatement:
    """Loads and parses statement from upload or synthetic sample."""
    if sample_scenario:
        # Load from synthetic generator or sample directory
        sample_path = f"data/sample_statements/statement_{sample_scenario}.csv"
        if os.path.exists(sample_path):
            return parse_csv_or_excel(sample_path)
        else:
            df, meta = generate_synthetic_statement(scenario=sample_scenario, num_transactions=40)
            tmp_csv = io.StringIO()
            df.to_csv(tmp_csv, index=False)
            tmp_csv.seek(0)
            return parse_csv_or_excel(tmp_csv)

    if uploaded_file is not None:
        file_bytes = io.BytesIO(uploaded_file.read())
        fname = uploaded_file.name.lower()
        if fname.endswith(".pdf"):
            return parse_pdf_statement(file_bytes)
        elif fname.endswith(".xlsx") or fname.endswith(".xls"):
            return parse_csv_or_excel(file_bytes, file_type="xlsx")
        else:
            return parse_csv_or_excel(file_bytes, file_type="csv")
    return None


# Sidebar
st.sidebar.image("https://img.icons8.com/color/96/shield.png", width=64)
st.sidebar.title("Forensic Ledger")
st.sidebar.markdown("**Bank Statement Fraud & Anomaly Audit**")
st.sidebar.divider()

data_source = st.sidebar.radio(
    "Data Input Method",
    ["🧪 Test Pre-Loaded Scenarios", "📁 Upload Bank Statement"],
    index=0
)

uploaded_file = None
selected_scenario = None

if data_source == "🧪 Test Pre-Loaded Scenarios":
    scenario_options = {
        "Clean Legitimate Statement": "clean",
        "Direct Ledger Math Tampering": "math_tampered",
        "Rule 114B PAN Threshold Proximity (₹45k - ₹49.9k)": "structuring",
        "Duplicate & Replay Transactions": "duplicates",
        "Benford's Law Violation (Fabricated Data)": "benford_tampered"
    }
    choice = st.sidebar.selectbox("Select Scenario", list(scenario_options.keys()))
    selected_scenario = scenario_options[choice]
else:
    uploaded_file = st.sidebar.file_uploader(
        "Upload PDF, CSV, or Excel Statement",
        type=["pdf", "csv", "xlsx", "xls"]
    )

with st.sidebar.expander("⚙️ Forensic Engine Parameters"):
    param_struct_low = st.number_input("Threshold Proximity Min (₹)", value=45000.0, step=1000.0)
    param_struct_high = st.number_input("Threshold Proximity Max (₹)", value=49999.0, step=500.0)
    param_contamination = st.slider("ML Contamination Rate", 0.01, 0.15, 0.05, 0.01)
    param_tolerance = st.number_input("Ledger Math Tolerance (₹)", value=0.01, step=0.01)

config = FraudDetectionConfig(
    structuring_threshold_low=param_struct_low,
    structuring_threshold_high=param_struct_high,
    contamination_rate=param_contamination,
    tolerance=param_tolerance
)

engine = FraudDetectionEngine(config=config)

# Main Title Area
st.markdown('<div class="main-title">🛡️ Forensic Bank Statement Fraud Detection</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Automated forensic ledger auditing, regulatory structuring detection, Benford\'s Law distribution, and ML anomaly discovery.</div>', unsafe_allow_html=True)

# Parse Statement
statement = None
try:
    if data_source == "🧪 Test Pre-Loaded Scenarios":
        statement = load_statement(None, sample_scenario=selected_scenario)
    elif uploaded_file is not None:
        statement = load_statement(uploaded_file)
except Exception as e:
    st.error(f"Error parsing statement: {str(e)}")

if statement is None:
    st.info("👈 Please select a pre-loaded test scenario or upload a bank statement from the sidebar to start the forensic audit.")
else:
    # Run Forensic Engine
    with st.spinner("Executing forensic ledger audit & ML anomaly scans..."):
        verdict = engine.analyze(statement)

    # Risk Color Palette
    risk_colors = {
        "LOW": ("#10b981", "#ecfdf5", "✅ APPROVED (Legitimate Statement)"),
        "MODERATE": ("#f59e0b", "#fffbeb", "⚠️ MANUAL REVIEW RECOMMENDED"),
        "HIGH": ("#ef4444", "#fef2f2", "🚨 SUSPICIOUS (Likely Fraud / Alterations)"),
        "CRITICAL": ("#991b1b", "#fef2f2", "⛔ REJECTED (Direct Ledger Math Alteration)")
    }
    primary_color, bg_color, header_text = risk_colors.get(verdict.risk_level, ("#ef4444", "#fef2f2", "FLAGGED"))

    # Banner
    st.markdown(f"""
    <div style="background-color: {primary_color}; padding: 18px 24px; border-radius: 10px; color: white; display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
        <div>
            <div style="font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; opacity: 0.9;">Audit Verdict</div>
            <div style="font-size: 1.6rem; font-weight: 800;">{header_text}</div>
            <div style="font-size: 0.95rem; margin-top: 4px; opacity: 0.95;">Account: {statement.metadata.account_number} | Bank: {statement.metadata.bank_name}</div>
        </div>
        <div style="text-align: right; background: rgba(255, 255, 255, 0.2); padding: 10px 18px; border-radius: 8px;">
            <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Overall Fraud Score</div>
            <div style="font-size: 2.2rem; font-weight: 900;">{verdict.overall_risk_score:.1f} <span style="font-size: 1rem; font-weight: 400;">/ 100</span></div>
            <div style="font-size: 0.85rem; font-weight: 700;">{verdict.risk_level} RISK</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Top Metric Columns
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            label="Ledger Math Status",
            value="PASSED" if not verdict.ledger_audit.is_tampered else "FAILED",
            delta=f"{verdict.ledger_audit.tampered_row_count} Altered Rows" if verdict.ledger_audit.is_tampered else "100% Consistent",
            delta_color="normal" if not verdict.ledger_audit.is_tampered else "inverse"
        )
    with col2:
        st.metric(
            label="Threshold Alerts",
            value=verdict.velocity_audit.structuring_count,
            delta="Rule 114B Heuristic" if verdict.velocity_audit.structuring_count > 0 else "None",
            delta_color="inverse" if verdict.velocity_audit.structuring_count > 0 else "off"
        )
    with col3:
        st.metric(
            label="Benford Conformity",
            value=verdict.benford_audit.conformity_level.split()[0],
            delta=f"MAD: {verdict.benford_audit.mad:.4f}",
            delta_color="inverse" if verdict.benford_audit.is_anomaly else "off"
        )
    with col4:
        st.metric(
            label="Duplicates / Replays",
            value=verdict.duplicate_audit.duplicate_group_count,
            delta=f"₹{verdict.duplicate_audit.total_duplicated_amount:,.2f}" if verdict.duplicate_audit.duplicate_group_count > 0 else "None",
            delta_color="inverse" if verdict.duplicate_audit.duplicate_group_count > 0 else "off"
        )
    with col5:
        st.metric(
            label="ML Outliers (IForest)",
            value=verdict.ml_audit.anomalous_count,
            delta=f"{verdict.ml_audit.suspicious_count} Suspicious",
            delta_color="inverse" if verdict.ml_audit.anomalous_count > 0 else "off"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Scorecard & Findings",
        "🔍 Ledger Math Forensics",
        "📈 Benford's Law Analysis",
        "⚡ Velocity & Threshold Proximity",
        "🤖 ML Anomaly Models",
        "📋 Full Transaction Ledger",
        "📑 Export PDF / JSON"
    ])

    # TAB 1: Scorecard & Executive Findings
    with tab1:
        col_sc1, col_sc2 = st.columns([1.2, 1])
        with col_sc1:
            st.subheader("Forensic Risk Scorecard Breakdown")
            df_sc = pd.DataFrame([
                {"Component": k, "Score": v}
                for k, v in verdict.score_breakdown.items()
            ])
            fig_bar = px.bar(
                df_sc,
                x="Score",
                y="Component",
                orientation="h",
                text="Score",
                color="Score",
                color_continuous_scale=["#10b981", "#f59e0b", "#ef4444"],
                range_color=[0, 100],
                title="Weighted Risk Contributions by Forensic Module"
            )
            fig_bar.update_layout(xaxis=dict(range=[0, 100]), height=340, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_sc2:
            st.subheader("Account Reconciliation Verification")
            st.write(f"**Account Holder:** {statement.metadata.account_holder}")
            st.write(f"**Total Transactions:** {len(statement.transactions)}")
            
            recon_df = pd.DataFrame({
                "Metric": [
                    "Reported Opening Balance",
                    "Total Deposits (+)",
                    "Total Withdrawals (-)",
                    "Calculated Closing Balance",
                    "Reported Closing Balance",
                    "Reconciliation Delta"
                ],
                "Amount (₹)": [
                    f"₹{verdict.ledger_audit.opening_balance:,.2f}",
                    f"₹{verdict.ledger_audit.total_deposits:,.2f}",
                    f"₹{verdict.ledger_audit.total_withdrawals:,.2f}",
                    f"₹{verdict.ledger_audit.closing_balance_calculated:,.2f}",
                    f"₹{verdict.ledger_audit.closing_balance_reported:,.2f}",
                    f"₹{verdict.ledger_audit.closing_discrepancy:,.2f}"
                ]
            })
            st.dataframe(recon_df, use_container_width=True, hide_index=True)

        st.divider()
        col_find, col_rec = st.columns(2)
        with col_find:
            st.subheader("🔍 Key Forensic Findings")
            for f in verdict.summary_findings:
                if "CRITICAL" in f or "FAILED" in f or "Alert" in f:
                    st.error(f)
                else:
                    st.success(f)

        with col_rec:
            st.subheader("📋 Underwriter Recommendations")
            for r in verdict.recommendations:
                if verdict.risk_level in ["CRITICAL", "HIGH"]:
                    st.warning(f"• {r}")
                else:
                    st.info(f"• {r}")

    # TAB 2: Ledger Math Forensics
    with tab2:
        st.subheader("Mathematical Ledger Integrity & Balance Reconciliation")
        st.write("""
        Bank statements must obey fundamental ledger conservation: 
        $$\\text{Balance}_t = \\text{Balance}_{t-1} + \\text{Deposit}_t - \\text{Withdrawal}_t$$
        Any discrepancy indicates direct document tampering, numbers being pasted over, or omitted transactions.
        """)

        if verdict.ledger_audit.is_tampered:
            st.error(f"🚨 **DOCUMENT TAMPERING DETECTED**: Found {verdict.ledger_audit.tampered_row_count} balance discrepancies with a closing delta of ₹{verdict.ledger_audit.closing_discrepancy:,.2f}!")
            
            discrepancy_data = [
                {
                    "Row Index": d.row_index,
                    "Txn ID": d.txn_id,
                    "Date": d.date,
                    "Description": d.description,
                    "Reported Balance": f"₹{d.reported_balance:,.2f}",
                    "Expected Balance": f"₹{d.expected_balance:,.2f}",
                    "Discrepancy (Delta)": f"₹{d.discrepancy:,.2f}",
                    "Forensic Details": d.details
                }
                for d in verdict.ledger_audit.discrepancies
            ]
            st.dataframe(pd.DataFrame(discrepancy_data), use_container_width=True, hide_index=True)
        else:
            st.success("✅ **LEDGER MATH FULLY VERIFIED**: All row balances match transaction sums with zero discrepancies.")

        # Balance Trajectory Chart
        df_traj = verdict.annotated_df.copy()
        df_traj['row_num'] = range(1, len(df_traj) + 1)
        
        # Calculate Expected Balance Trajectory
        exp_bal_series = []
        curr = verdict.ledger_audit.opening_balance
        for _, r in df_traj.iterrows():
            curr = curr + r['deposit'] - r['withdrawal']
            exp_bal_series.append(curr)
        df_traj['expected_trajectory'] = exp_bal_series

        fig_bal = go.Figure()
        fig_bal.add_trace(go.Scatter(
            x=df_traj['row_num'],
            y=df_traj['balance'],
            mode='lines+markers',
            name='Reported Balance',
            line=dict(color='#2563eb', width=2)
        ))
        fig_bal.add_trace(go.Scatter(
            x=df_traj['row_num'],
            y=df_traj['expected_trajectory'],
            mode='lines',
            name='Expected Forensic Balance',
            line=dict(color='#ef4444', dash='dash', width=2)
        ))
        
        # Highlight discrepancy points
        if verdict.ledger_audit.is_tampered:
            flagged_indices = [d.row_index for d in verdict.ledger_audit.discrepancies]
            flagged_rows = df_traj.iloc[flagged_indices]
            fig_bal.add_trace(go.Scatter(
                x=flagged_rows['row_num'],
                y=flagged_rows['balance'],
                mode='markers',
                name='Altered Points',
                marker=dict(size=12, color='#dc2626', symbol='x')
            ))

        fig_bal.update_layout(
            title="Running Balance Trajectory Audit: Reported vs. Forensically Calculated",
            xaxis_title="Transaction Sequence (#)",
            yaxis_title="Balance (INR)",
            height=420
        )
        st.plotly_chart(fig_bal, use_container_width=True)

    # TAB 3: Benford's Law
    with tab3:
        st.subheader("Benford's Law (First-Digit Forensic Accounting Test)")
        st.write("""
        Benford's Law posits that in authentic socio-economic and accounting numbers, the first significant digit $d \\in \\{1..9\\}$ 
        follows $P(d) = \\log_{10}(1 + 1/d)$. Fabricated ledgers consistently show abnormal uniform or high-digit spikes (7, 8, 9).
        """)

        b_res = verdict.benford_audit
        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        col_b1.metric("Sample Size", b_res.sample_size)
        col_b2.metric("Conformity Level", b_res.conformity_level)
        col_b3.metric("Mean Abs Deviation (MAD)", f"{b_res.mad:.4f}")
        col_b4.metric("Chi-Square p-value", f"{b_res.p_value:.4f}")

        if b_res.distribution:
            df_dist = pd.DataFrame([
                {
                    "Digit": d.digit,
                    "Observed %": d.observed_pct,
                    "Expected Benford %": d.expected_pct,
                    "Count": d.observed_count
                }
                for d in b_res.distribution
            ])

            fig_benford = go.Figure()
            fig_benford.add_trace(go.Bar(
                x=df_dist['Digit'],
                y=df_dist['Observed %'],
                name='Observed Statement %',
                marker_color='#3b82f6'
            ))
            fig_benford.add_trace(go.Scatter(
                x=df_dist['Digit'],
                y=df_dist['Expected Benford %'],
                name="Theoretical Benford's Law",
                line=dict(color='#ef4444', width=3)
            ))
            fig_benford.update_layout(
                title=f"First-Digit Distribution vs Benford's Law ({b_res.conformity_level})",
                xaxis=dict(tickmode='linear', tick0=1, dtick=1),
                yaxis_title="Frequency (%)",
                height=400
            )
            st.plotly_chart(fig_benford, use_container_width=True)
            st.dataframe(df_dist, use_container_width=True, hide_index=True)

    # TAB 4: Velocity & Threshold Proximity
    with tab4:
        st.subheader("Regulatory Threshold Proximity (Rule 114B / PMLA) & Velocity Spikes")
        st.write("""
        **Threshold Avoidance Heuristic**: Identifies transactions clustered immediately below regulatory reporting mandates.
        In India, under **Income Tax Rule 114B / PMLA KYC norms**, cash deposits or withdrawals of **₹50,000 or more** require mandatory PAN quoting.
        High-frequency transactions in the **₹45,000 – ₹49,999 band** serve as an analytical risk heuristic indicating the need for KYC and source-of-funds verification.
        """)

        v_res = verdict.velocity_audit
        col_v1, col_v2, col_v3 = st.columns(3)
        col_v1.metric("Threshold Proximity Flagged", v_res.structuring_count)
        col_v2.metric("Velocity Bursts", v_res.burst_count)
        col_v3.metric("Round Amount Clusters", v_res.round_amount_count)

        if v_res.flagged_transactions:
            flag_table = [
                {
                    "Txn ID": f.txn_id,
                    "Date": f.date,
                    "Description": f.description,
                    "Amount": f"₹{f.amount:,.2f}",
                    "Reason": f.reason,
                    "Severity": f.severity.upper()
                }
                for f in v_res.flagged_transactions
            ]
            st.dataframe(pd.DataFrame(flag_table), use_container_width=True, hide_index=True)
        else:
            st.success("No suspicious velocity bursts or threshold proximity transactions detected.")

        # Amount Scatter Distribution
        df_plot = verdict.annotated_df.copy()
        fig_scatter = px.scatter(
            df_plot,
            x="date",
            y="amount",
            color="is_structuring",
            color_discrete_map={True: "#ef4444", False: "#3b82f6"},
            size="amount",
            hover_data=["description", "balance", "fraud_flags"],
            title="Transaction Amount Distribution Over Time (Red = ₹45,000 - ₹49,999 Proximity Zone)"
        )
        # Add regulatory threshold line for Rule 114B
        fig_scatter.add_hline(y=50000.0, line_dash="dash", line_color="red", annotation_text="Rule 114B ₹50,000 PAN Requirement Mandate")
        fig_scatter.add_hrect(y0=45000.0, y1=49999.0, fillcolor="red", opacity=0.1, line_width=0, annotation_text="Proximity Heuristic Zone (₹45k - ₹49.9k)")
        fig_scatter.update_layout(height=420)
        st.plotly_chart(fig_scatter, use_container_width=True)

    # TAB 5: ML Anomaly Models
    with tab5:
        st.subheader("Unsupervised Machine Learning Anomaly Detection (Isolation Forest)")
        st.write("""
        Detects multi-dimensional behavioral outliers based on sudden balance depletion, extreme Z-score deviations, 
        atypical timing, and transaction velocity changes.
        """)

        ml_res = verdict.ml_audit
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Highly Anomalous Outliers", ml_res.anomalous_count)
        col_m2.metric("Suspicious Outliers", ml_res.suspicious_count)

        # ML Scatter Plot
        df_ml = verdict.annotated_df.copy()
        fig_ml = px.scatter(
            df_ml,
            x="balance",
            y="amount",
            color="ml_label",
            color_discrete_map={
                "Normal": "#10b981",
                "Suspicious": "#f59e0b",
                "Highly Anomalous": "#ef4444"
            },
            size="ml_anomaly_score",
            hover_data=["description", "date", "ml_anomaly_score", "fraud_flags"],
            title="Isolation Forest Anomaly Landscape (Amount vs Account Balance)"
        )
        fig_ml.update_layout(height=420)
        st.plotly_chart(fig_ml, use_container_width=True)

        if ml_res.anomalies:
            st.markdown("#### Top Flagged Outliers & Contributing Behavioral Explanations")
            for a in ml_res.anomalies[:8]:
                with st.expander(f"Txn #{a.txn_id} | {a.date} | ₹{a.amount:,.2f} - {a.description} (Score: {a.anomaly_score:.1f}/100)"):
                    st.write(f"**Anomaly Label:** `{a.anomaly_label}`")
                    st.write(f"**Account Balance at time:** `₹{a.balance:,.2f}`")
                    st.write("**Top Contributing Anomaly Drivers:**")
                    for r in a.top_reasons:
                        st.write(f"• {r}")

    # TAB 6: Full Transaction Ledger
    with tab6:
        st.subheader("Annotated Transaction Ledger")
        
        filter_option = st.selectbox(
            "Filter Ledger Records",
            ["Show All Transactions", "Flagged Anomaly Rows Only", "Math Alterations Only", "Structuring / Smurfing Only"]
        )

        df_display = verdict.annotated_df.copy()
        if filter_option == "Flagged Anomaly Rows Only":
            df_display = df_display[df_display['fraud_flags'] != "Clean"]
        elif filter_option == "Math Alterations Only":
            df_display = df_display[df_display['is_math_tampered']]
        elif filter_option == "Structuring / Smurfing Only":
            df_display = df_display[df_display['is_structuring']]

        # Format display columns
        columns_to_show = ['txn_id', 'date', 'description', 'deposit', 'withdrawal', 'balance', 'ml_anomaly_score', 'fraud_flags']
        existing_cols = [c for c in columns_to_show if c in df_display.columns]
        
        st.dataframe(
            df_display[existing_cols],
            use_container_width=True,
            hide_index=True
        )

    # TAB 7: Export Reports
    with tab7:
        st.subheader("Generate & Download Audit Certificates")
        st.write("Export formal verification reports for loan underwriting, compliance records, and forensic review.")

        col_rep1, col_rep2, col_rep3 = st.columns(3)

        # JSON Report
        json_report = generate_json_report(verdict, statement.metadata)
        json_str = json.dumps(json_report, indent=2)

        with col_rep1:
            st.markdown("##### 📄 Machine-Readable JSON")
            st.download_button(
                label="Download JSON Audit Report",
                data=json_str,
                file_name=f"audit_report_{statement.metadata.account_number}.json",
                mime="application/json",
                use_container_width=True
            )

        # PDF Report
        tmp_pdf_path = f"/tmp/audit_report_{statement.metadata.account_number}.pdf"
        generate_pdf_report(verdict, statement.metadata, tmp_pdf_path)
        with open(tmp_pdf_path, "rb") as f:
            pdf_bytes = f.read()

        with col_rep2:
            st.markdown("##### 📑 Forensic PDF Certificate")
            st.download_button(
                label="Download PDF Audit Certificate",
                data=pdf_bytes,
                file_name=f"audit_certificate_{statement.metadata.account_number}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        # Annotated CSV
        csv_buffer = io.StringIO()
        verdict.annotated_df.to_csv(csv_buffer, index=False)

        with col_rep3:
            st.markdown("##### 📊 Annotated CSV Data")
            st.download_button(
                label="Download Scored CSV Ledger",
                data=csv_buffer.getvalue(),
                file_name=f"scored_ledger_{statement.metadata.account_number}.csv",
                mime="text/csv",
                use_container_width=True
            )

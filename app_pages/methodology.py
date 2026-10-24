"""
Methodology & Data Notes Page per UI_Design.md §6.6.
Single readable column (max 760px) documenting sources, the model chain, assumptions, and limits.
"""

import streamlit as st

from campaign_intel.ui.topbar import render_topbar

# 1. Top Bar
render_topbar("Methodology, Model Architecture & Data Notes")

# Center container capped at 760px per §6.6
center_col, _ = st.columns([1, 0.01])

with center_col:
    with st.container(border=True):
        st.markdown("""
        ### 1. Data Sources & Fidelity Classification
        Every metric in this application carries an explicit data-fidelity badge reflecting its provenance:

        | Source | Provider / Grain | Refresh | Application Use | Fidelity |
        |---|---|---|---|---|
        | **Google Political Ads** | BigQuery Public Data (`creative_stats`, `geo_spend`) | Daily | Pacing, spend bands, targeting formats | **Observed** |
        | **Meta Ad Library API** | Graph API (`/ads_archive` token-authenticated) | Daily Snapshot | Creative text, themes, demographic delivery | **Observed** |
        | **NCSBE Baseline Returns** | NC State Board of Elections certified precinct files | Certified | Baseline 2022 Senate precinct contest results | **Aggregated** |
        | **MEDSL Senate 2022** | MIT Election Data + Science Lab (`senate_2022.csv`) | Reference | County baseline validation by vote mode | **Aggregated** |
        | **CCES 2024 Survey** | Cooperative Election Study (UNC Module) | Survey | Weighted social media adoption & issue priority | **Aggregated** |
        | **District Allocations** | Modeled voter-share weights across CD, SD, HD | Model | Distributing statewide media pressure to units | **Modeled** |
        | **War Room Simulator** | Vectorized Monte Carlo response model | Dynamic | Simulating net vote impact from $2M budget | **Modeled** |
        """)

        st.markdown("---")

        st.markdown("""
        ### 2. War Room Causal Model Chain
        The War Room is an **explicit, assumption-driven simulation model** designed to evaluate marginal resource allocations. It does **not** purport to be a poll-based predictive forecast.

        ```mermaid
        graph TD
            A[Dollars Allocated x, Channel c, Week w] --> B[Impressions I = x / CPM * 1000]
            B --> C[Effective Frequency f = I_prior + I / Universe]
            C --> D[Saturating Reach R = U * 1 - exp -k*f]
            D --> E[Opponent Share of Voice Dampening 1 / 1 + lambda*opp]
            E --> F[Temporal Decay Weight rho^W - w]
            F --> G[Marginal Net Votes: Persuasion p vs Mobilization t]
            G --> H[Correlated Monte Carlo: Statewide + Unit Error]
            H --> I[Projected Win Probability & Net Margin Distribution]
        ```

        #### Formal Mechanics
        1. **Saturating Reach**:
           $$\\Delta R = U_{ua} \\cdot \\left(1 - e^{-k_c \\cdot \frac{I_{\text{prior}} + I}{U_{ua}}}\right) - U_{ua} \\cdot \\left(1 - e^{-k_c \\cdot \frac{I_{\text{prior}}}{U_{ua}}}\right)$$
        2. **Persuasion Impact**:
           $$\\Delta V_{\text{pers}} = \\Delta R \\cdot p_c \\cdot \rho^{W - w} \\cdot \frac{1}{1 + \\lambda \\cdot \text{opp\\_share}_u}$$
        3. **Mobilization Impact**:
           $$\\Delta V_{\text{mob}} = \\Delta R \\cdot t_c \\cdot (2d_u - 1) \\cdot \rho^{W - w} \\cdot \frac{1}{1 + \\lambda \\cdot \text{opp\\_share}_u}$$
        """)

        st.markdown("---")

        st.markdown("""
        ### 3. Empirical Basis for Default Effect Sizes
        - **Persuasion Rate ($p = 0.002$)**: Net margin shift per reached persuadable voter is calibrated conservatively. Rigorous academic field experiments (e.g. Kalla & Broockman, 2018) consistently find that general-election digital advertising effects are near zero without extreme targeted timing.
        - **Turnout Lift ($t = 0.003$)**: Mobilization response rates among low-propensity partisans align with randomized controlled trials of non-partisan and partisan digital GOTV impressions (Nickerson et al., Green & Gerber).
        - **Weekly Retention ($\rho = 0.60$)**: Digital ad memorability and persuasion effects decay rapidly, demonstrating exponential half-lives of under 10 days. Late money allocated in final weeks receives significantly higher effective weight.
        - **CPM Costs**: Derived empirically from median North Carolina political flight costs on Google Ads Transparency Report and Meta Ad Library ($8–$20 Meta, $11–$25 YouTube Video, $25–$50 CTV).
        """)

        st.markdown("---")

        st.markdown("""
        ### 4. Ethical Standards & Privacy Safeguards
        - **No Individual Voter Display**: Voter registration and history data are aggregated into precinct and district totals before ingestion. Cells with fewer than 10 individuals are suppressed.
        - **Token Security**: Meta access tokens and Google Cloud service credentials are strictly managed through environment variables (`.env`) and are never exposed in user logs, UI elements, or client bundles.
        - **Open-Ended Spend Bands**: For top-tier spending without published upper bounds, conservative midpoints ($1.5 \times \text{low}$) are flagged and visibly denoted with '$\\ge$' symbols.
        """)

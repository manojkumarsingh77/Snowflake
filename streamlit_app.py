# Airtel Telecom KPI Dashboard - powered by Medallion Architecture (ANALYTICS Gold layer)
# Co-authored with CoCo
import os
import streamlit as st

st.set_page_config(page_title="Airtel Telecom Dashboard", page_icon="📡", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))


@st.cache_data(ttl=300)
def run_query(sql):
    return conn.query(sql)


def safe_val(df, col, idx=0, fmt=",.0f", prefix="", suffix=""):
    """Safely extract and format a value from a dataframe."""
    try:
        val = df[col][idx]
        if val is None:
            return "N/A"
        return f"{prefix}{val:{fmt}}{suffix}"
    except (KeyError, IndexError, TypeError, ValueError):
        return "N/A"


def check_analytics_layer():
    """Verify the ANALYTICS layer exists before querying it."""
    try:
        result = run_query("""
            SELECT COUNT(*) AS CNT
            FROM AIRTEL_DW.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = 'ANALYTICS'
              AND TABLE_NAME = 'DIM_CUSTOMER'
        """)
        return result["CNT"][0] > 0
    except Exception:
        return False


# --- Pre-check: ANALYTICS layer exists? ---
analytics_ready = check_analytics_layer()

if not analytics_ready:
    st.error("**ANALYTICS layer not found!**")
    st.markdown("""
    The Streamlit dashboard reads from `AIRTEL_DW.ANALYTICS` (Gold layer).

    **Please run the SQL scripts in this order:**
    1. `AirtelDWH_Migration.sql` — creates RAW (Bronze) layer with data
    2. `AirtelDWH_Staging_Analytics.sql` — creates STAGING (Silver) + ANALYTICS (Gold) layers

    After running both scripts, refresh this app.
    """)
    st.stop()

# --- Sidebar ---
with st.sidebar:
    st.title("📡 Airtel Telecom")
    st.caption("Medallion Architecture Dashboard")
    st.markdown("**Data Source:** `AIRTEL_DW.ANALYTICS`")
    st.divider()

    circles = run_query(
        "SELECT DISTINCT CIRCLE FROM AIRTEL_DW.ANALYTICS.DIM_CUSTOMER ORDER BY CIRCLE"
    )
    selected_circles = st.multiselect(
        "Filter by Circle", circles["CIRCLE"].tolist(), default=[]
    )

    segments = run_query(
        "SELECT DISTINCT CUSTOMER_SEGMENT FROM AIRTEL_DW.ANALYTICS.DIM_CUSTOMER ORDER BY CUSTOMER_SEGMENT"
    )
    selected_segments = st.multiselect(
        "Filter by Segment", segments["CUSTOMER_SEGMENT"].tolist(), default=[]
    )

    st.divider()
    page = st.radio(
        "Dashboard Section",
        [
            "Executive Summary",
            "Revenue & ARPU",
            "Subscriber & Churn",
            "Network Performance",
            "Data & 5G Adoption",
            "Customer Experience",
            "Recharge Analytics",
        ],
    )

    st.divider()
    if st.button("Refresh Data"):
        run_query.clear()
        st.rerun()


def circle_clause(col="CIRCLE"):
    if selected_circles:
        vals = ",".join(f"'{c}'" for c in selected_circles)
        return f" AND {col} IN ({vals})"
    return ""


def segment_clause(col="CUSTOMER_SEGMENT"):
    if selected_segments:
        vals = ",".join(f"'{s}'" for s in selected_segments)
        return f" AND {col} IN ({vals})"
    return ""


# ============================================================
# EXECUTIVE SUMMARY
# ============================================================
if page == "Executive Summary":
    st.header("Executive Summary — All KPIs at a Glance")

    df = run_query("SELECT * FROM AIRTEL_DW.ANALYTICS.V_EXECUTIVE_SUMMARY")

    st.subheader("Subscriber & Revenue")
    with st.container(horizontal=True):
        st.metric("Total Subscribers", safe_val(df, "TOTAL_SUBSCRIBERS"), border=True)
        st.metric("Active Subscribers", safe_val(df, "ACTIVE_SUBSCRIBERS"), border=True)
        st.metric("Churn Rate", safe_val(df, "CHURN_RATE_PCT", suffix="%"), border=True)
        st.metric("Total Revenue (₹)", safe_val(df, "TOTAL_REVENUE", prefix="₹"), border=True)
        st.metric("ARPU (₹)", safe_val(df, "OVERALL_ARPU", fmt=",.2f", prefix="₹"), border=True)

    st.subheader("Network & Quality")
    with st.container(horizontal=True):
        st.metric("Call Drop Rate", safe_val(df, "AVG_CALL_DROP_RATE_PCT", suffix="%"), border=True)
        st.metric("Setup Success", safe_val(df, "AVG_SETUP_SUCCESS_PCT", suffix="%"), border=True)
        st.metric("Avg Speed", safe_val(df, "AVG_NETWORK_SPEED_MBPS", suffix=" Mbps"), border=True)
        st.metric("Tower Health", safe_val(df, "AVG_TOWER_HEALTH", suffix="/100"), border=True)

    st.subheader("Customer Experience & Digital")
    with st.container(horizontal=True):
        st.metric("Total Complaints", safe_val(df, "TOTAL_COMPLAINTS"), border=True)
        st.metric("Resolution Rate", safe_val(df, "COMPLAINT_RESOLUTION_RATE", suffix="%"), border=True)
        st.metric("Avg CSAT", safe_val(df, "AVG_CSAT_SCORE", fmt=".2f", suffix="/5"), border=True)
        st.metric("Data Consumed", safe_val(df, "TOTAL_DATA_CONSUMED_GB", suffix=" GB"), border=True)
        st.metric("Recharge Value (₹)", safe_val(df, "TOTAL_RECHARGE_VALUE", prefix="₹"), border=True)

    st.divider()
    st.subheader("Circle Performance Scorecard")
    df_score = run_query("SELECT * FROM AIRTEL_DW.ANALYTICS.V_CIRCLE_SCORECARD")
    st.dataframe(df_score, hide_index=True, use_container_width=True)


# ============================================================
# REVENUE & ARPU
# ============================================================
elif page == "Revenue & ARPU":
    st.header("Revenue & ARPU Analysis")

    df_kpi = run_query(f"""
        SELECT
            COALESCE(SUM(TOTAL_REVENUE), 0) AS REVENUE,
            COALESCE(SUM(UNIQUE_CUSTOMERS), 0) AS CUSTOMERS,
            ROUND(SUM(TOTAL_REVENUE) / NULLIF(SUM(UNIQUE_CUSTOMERS), 0), 2) AS ARPU,
            COALESCE(SUM(TOTAL_OUTSTANDING), 0) AS OUTSTANDING
        FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_REVENUE
        WHERE 1=1 {circle_clause()} {segment_clause()}
    """)

    with st.container(horizontal=True):
        st.metric("Total Revenue (₹)", safe_val(df_kpi, "REVENUE", prefix="₹"), border=True)
        st.metric("Customers Billed", safe_val(df_kpi, "CUSTOMERS"), border=True)
        st.metric("ARPU (₹)", safe_val(df_kpi, "ARPU", fmt=",.2f", prefix="₹"), border=True)
        st.metric("Outstanding (₹)", safe_val(df_kpi, "OUTSTANDING", prefix="₹"), border=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Monthly Revenue Trend")
            df_trend = run_query(f"""
                SELECT BILLING_MONTH AS MONTH,
                    SUM(TOTAL_REVENUE) AS REVENUE,
                    ROUND(SUM(TOTAL_REVENUE) / NULLIF(SUM(UNIQUE_CUSTOMERS), 0), 2) AS ARPU
                FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_REVENUE
                WHERE 1=1 {circle_clause()} {segment_clause()}
                GROUP BY BILLING_MONTH ORDER BY MONTH
            """)
            if not df_trend.empty:
                st.line_chart(df_trend, x="MONTH", y="REVENUE")
            else:
                st.info("No data available for selected filters.")

    with col2:
        with st.container(border=True):
            st.subheader("Revenue by Segment")
            df_seg = run_query(f"""
                SELECT CUSTOMER_SEGMENT AS SEGMENT, SUM(TOTAL_REVENUE) AS REVENUE
                FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_REVENUE
                WHERE 1=1 {circle_clause()} {segment_clause()}
                GROUP BY CUSTOMER_SEGMENT ORDER BY REVENUE DESC
            """)
            if not df_seg.empty:
                st.bar_chart(df_seg, x="SEGMENT", y="REVENUE")
            else:
                st.info("No data available for selected filters.")

    with st.container(border=True):
        st.subheader("Revenue Mix by Type")
        df_mix = run_query(f"""
            SELECT BILLING_MONTH AS MONTH,
                SUM(TOTAL_PLAN_REVENUE) AS PLAN,
                SUM(TOTAL_CALL_REVENUE) AS CALLS,
                SUM(TOTAL_DATA_REVENUE) AS DATA,
                SUM(TOTAL_VAS_REVENUE) AS VAS,
                SUM(TOTAL_ROAMING_REVENUE) AS ROAMING
            FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_REVENUE
            WHERE 1=1 {circle_clause()} {segment_clause()}
            GROUP BY MONTH ORDER BY MONTH
        """)
        if not df_mix.empty:
            st.line_chart(df_mix, x="MONTH", y=["PLAN", "CALLS", "DATA", "VAS", "ROAMING"])
        else:
            st.info("No data available for selected filters.")

    with st.container(border=True):
        st.subheader("Revenue by Circle")
        df_circ = run_query(f"""
            SELECT CIRCLE, SUM(TOTAL_REVENUE) AS REVENUE, SUM(UNIQUE_CUSTOMERS) AS CUSTOMERS,
                ROUND(SUM(TOTAL_REVENUE) / NULLIF(SUM(UNIQUE_CUSTOMERS), 0), 2) AS ARPU
            FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_REVENUE
            WHERE 1=1 {circle_clause()} {segment_clause()}
            GROUP BY CIRCLE ORDER BY REVENUE DESC
        """)
        st.dataframe(df_circ, hide_index=True, use_container_width=True)


# ============================================================
# SUBSCRIBER & CHURN
# ============================================================
elif page == "Subscriber & Churn":
    st.header("Subscriber & Churn Analysis")

    df_sub = run_query(f"""
        SELECT
            COUNT(*) AS TOTAL,
            SUM(1 - IS_CHURNED) AS ACTIVE,
            SUM(IS_CHURNED) AS CHURNED,
            ROUND(100.0 * SUM(IS_CHURNED) / NULLIF(COUNT(*), 0), 2) AS CHURN_RATE
        FROM AIRTEL_DW.ANALYTICS.DIM_CUSTOMER
        WHERE 1=1 {circle_clause()} {segment_clause()}
    """)

    with st.container(horizontal=True):
        st.metric("Total Subscribers", safe_val(df_sub, "TOTAL"), border=True)
        st.metric("Active", safe_val(df_sub, "ACTIVE"), border=True)
        st.metric("Churned", safe_val(df_sub, "CHURNED"), border=True)
        st.metric("Churn Rate", safe_val(df_sub, "CHURN_RATE", suffix="%"), border=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Churn by Revenue Tier")
            df_tier = run_query(f"""
                SELECT REVENUE_TIER, COUNT(*) AS TOTAL, SUM(IS_CHURNED) AS CHURNED,
                    ROUND(100.0 * SUM(IS_CHURNED) / NULLIF(COUNT(*), 0), 2) AS CHURN_RATE
                FROM AIRTEL_DW.ANALYTICS.DIM_CUSTOMER
                WHERE 1=1 {circle_clause()} {segment_clause()}
                GROUP BY REVENUE_TIER ORDER BY CHURN_RATE DESC
            """)
            if not df_tier.empty:
                st.bar_chart(df_tier, x="REVENUE_TIER", y="CHURN_RATE")
            else:
                st.info("No data available.")

    with col2:
        with st.container(border=True):
            st.subheader("Churn by Tenure Bucket")
            df_ten = run_query(f"""
                SELECT TENURE_BUCKET, COUNT(*) AS TOTAL, SUM(IS_CHURNED) AS CHURNED,
                    ROUND(100.0 * SUM(IS_CHURNED) / NULLIF(COUNT(*), 0), 2) AS CHURN_RATE
                FROM AIRTEL_DW.ANALYTICS.DIM_CUSTOMER
                WHERE 1=1 {circle_clause()} {segment_clause()}
                GROUP BY TENURE_BUCKET ORDER BY CHURN_RATE DESC
            """)
            if not df_ten.empty:
                st.bar_chart(df_ten, x="TENURE_BUCKET", y="CHURN_RATE")
            else:
                st.info("No data available.")

    with st.container(border=True):
        st.subheader("Churn by Circle (Revenue at Risk)")
        df_churn = run_query(f"""
            SELECT CIRCLE, COUNT(*) AS TOTAL_CUSTOMERS,
                SUM(IS_CHURNED) AS CHURNED,
                ROUND(100.0 * SUM(IS_CHURNED) / NULLIF(COUNT(*), 0), 2) AS CHURN_RATE,
                SUM(CASE WHEN IS_CHURNED = 1 THEN MONTHLY_CHARGE ELSE 0 END) AS MONTHLY_REVENUE_LOST
            FROM AIRTEL_DW.ANALYTICS.DIM_CUSTOMER
            WHERE 1=1 {circle_clause()} {segment_clause()}
            GROUP BY CIRCLE ORDER BY MONTHLY_REVENUE_LOST DESC
        """)
        st.dataframe(df_churn, hide_index=True, use_container_width=True)

    with st.container(border=True):
        st.subheader("Age Band Distribution")
        df_age = run_query(f"""
            SELECT AGE_BAND, COUNT(*) AS SUBSCRIBERS, ROUND(AVG(LIFETIME_VALUE), 0) AS AVG_LTV
            FROM AIRTEL_DW.ANALYTICS.DIM_CUSTOMER
            WHERE 1=1 {circle_clause()} {segment_clause()}
            GROUP BY AGE_BAND ORDER BY SUBSCRIBERS DESC
        """)
        if not df_age.empty:
            st.bar_chart(df_age, x="AGE_BAND", y="SUBSCRIBERS")
        else:
            st.info("No data available.")


# ============================================================
# NETWORK PERFORMANCE
# ============================================================
elif page == "Network Performance":
    st.header("Network Performance KPIs")

    df_net = run_query(f"""
        SELECT
            ROUND(AVG(AVG_CALL_DROP_RATE_PCT), 3) AS DROP_RATE,
            ROUND(AVG(AVG_SETUP_SUCCESS_PCT), 2) AS SETUP_SUCCESS,
            ROUND(AVG(AVG_THROUGHPUT_MBPS), 2) AS AVG_SPEED,
            ROUND(SUM(TOTAL_TRAFFIC_GB) / 1024, 2) AS TRAFFIC_TB,
            ROUND(AVG(AVG_HEALTH_SCORE), 2) AS HEALTH_SCORE,
            COALESCE(SUM(SLA_VIOLATIONS), 0) AS SLA_VIOLATIONS
        FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_NETWORK
        WHERE 1=1 {circle_clause()}
    """)

    with st.container(horizontal=True):
        st.metric("Call Drop Rate", safe_val(df_net, "DROP_RATE", suffix="%"), border=True)
        st.metric("Setup Success", safe_val(df_net, "SETUP_SUCCESS", suffix="%"), border=True)
        st.metric("Avg Speed", safe_val(df_net, "AVG_SPEED", suffix=" Mbps"), border=True)
        st.metric("Total Traffic", safe_val(df_net, "TRAFFIC_TB", suffix=" TB"), border=True)
        st.metric("Health Score", safe_val(df_net, "HEALTH_SCORE", suffix="/100"), border=True)
        st.metric("SLA Violations", safe_val(df_net, "SLA_VIOLATIONS"), border=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Performance by Technology")
            df_tech = run_query(f"""
                SELECT TECHNOLOGY,
                    ROUND(AVG(AVG_CALL_DROP_RATE_PCT), 3) AS DROP_RATE,
                    ROUND(AVG(AVG_THROUGHPUT_MBPS), 2) AS AVG_SPEED,
                    ROUND(SUM(TOTAL_TRAFFIC_GB), 0) AS TRAFFIC_GB,
                    ROUND(AVG(AVG_HEALTH_SCORE), 2) AS HEALTH
                FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_NETWORK
                WHERE 1=1 {circle_clause()}
                GROUP BY TECHNOLOGY ORDER BY TRAFFIC_GB DESC
            """)
            st.dataframe(df_tech, hide_index=True, use_container_width=True)

    with col2:
        with st.container(border=True):
            st.subheader("Daily Network Health Trend")
            df_daily_net = run_query(f"""
                SELECT MEASUREMENT_DATE,
                    ROUND(AVG(AVG_HEALTH_SCORE), 2) AS HEALTH_SCORE
                FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_NETWORK
                WHERE 1=1 {circle_clause()}
                GROUP BY MEASUREMENT_DATE ORDER BY MEASUREMENT_DATE
            """)
            if not df_daily_net.empty:
                st.line_chart(df_daily_net, x="MEASUREMENT_DATE", y="HEALTH_SCORE")
            else:
                st.info("No data available.")

    with st.container(border=True):
        st.subheader("Network KPIs by Circle")
        df_nc = run_query(f"""
            SELECT CIRCLE,
                SUM(ACTIVE_TOWERS) AS TOWERS,
                ROUND(AVG(AVG_CALL_DROP_RATE_PCT), 3) AS DROP_RATE,
                ROUND(AVG(AVG_THROUGHPUT_MBPS), 2) AS SPEED,
                ROUND(SUM(TOTAL_TRAFFIC_GB), 0) AS TRAFFIC_GB,
                SUM(TOTAL_DOWNTIME_MIN) AS DOWNTIME_MIN,
                ROUND(AVG(AVG_HEALTH_SCORE), 2) AS HEALTH
            FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_NETWORK
            WHERE 1=1 {circle_clause()}
            GROUP BY CIRCLE ORDER BY TRAFFIC_GB DESC
        """)
        st.dataframe(df_nc, hide_index=True, use_container_width=True)


# ============================================================
# DATA & 5G ADOPTION
# ============================================================
elif page == "Data & 5G Adoption":
    st.header("Data Usage & 5G Adoption")

    df_data = run_query(f"""
        SELECT
            ROUND(SUM(TOTAL_DATA_GB) / 1024, 2) AS TOTAL_TB,
            COALESCE(SUM(UNIQUE_USERS), 0) AS DATA_USERS,
            ROUND(AVG(AVG_SESSION_MB), 2) AS AVG_SESSION_MB,
            ROUND(AVG(AVG_DOWNLOAD_SPEED), 2) AS AVG_SPEED
        FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_USAGE
        WHERE 1=1 {circle_clause()}
    """)

    with st.container(horizontal=True):
        st.metric("Total Data", safe_val(df_data, "TOTAL_TB", suffix=" TB"), border=True)
        st.metric("Data Users", safe_val(df_data, "DATA_USERS"), border=True)
        st.metric("Avg Session", safe_val(df_data, "AVG_SESSION_MB", suffix=" MB"), border=True)
        st.metric("Avg Speed", safe_val(df_data, "AVG_SPEED", suffix=" Mbps"), border=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Data by Network Type")
            df_ntype = run_query(f"""
                SELECT NETWORK_TYPE, ROUND(SUM(TOTAL_DATA_GB), 2) AS DATA_GB
                FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_USAGE
                WHERE 1=1 {circle_clause()}
                GROUP BY NETWORK_TYPE ORDER BY DATA_GB DESC
            """)
            if not df_ntype.empty:
                st.bar_chart(df_ntype, x="NETWORK_TYPE", y="DATA_GB")
            else:
                st.info("No data available.")

    with col2:
        with st.container(border=True):
            st.subheader("Top App Categories")
            df_app = run_query(f"""
                SELECT APP_GROUP, ROUND(SUM(TOTAL_DATA_GB), 2) AS DATA_GB
                FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_USAGE
                WHERE 1=1 {circle_clause()}
                GROUP BY APP_GROUP ORDER BY DATA_GB DESC
            """)
            if not df_app.empty:
                st.bar_chart(df_app, x="APP_GROUP", y="DATA_GB")
            else:
                st.info("No data available.")

    with st.container(border=True):
        st.subheader("5G Adoption Trend (% of Data on 5G)")
        df_5g = run_query(f"""
            SELECT USAGE_DATE,
                ROUND(AVG(PCT_5G_DATA), 2) AS PCT_5G_DATA,
                ROUND(AVG(PCT_5G_USERS), 2) AS PCT_5G_USERS
            FROM AIRTEL_DW.ANALYTICS.V_5G_ADOPTION
            WHERE 1=1 {circle_clause()}
            GROUP BY USAGE_DATE ORDER BY USAGE_DATE
        """)
        if not df_5g.empty:
            st.line_chart(df_5g, x="USAGE_DATE", y=["PCT_5G_DATA", "PCT_5G_USERS"])
        else:
            st.info("No 5G data available.")

    with st.container(border=True):
        st.subheader("Data Usage by Time Slot")
        df_slot = run_query(f"""
            SELECT TIME_SLOT, ROUND(SUM(TOTAL_DATA_GB), 2) AS DATA_GB, SUM(SESSION_COUNT) AS SESSIONS
            FROM AIRTEL_DW.ANALYTICS.FACT_DAILY_USAGE
            WHERE 1=1 {circle_clause()}
            GROUP BY TIME_SLOT ORDER BY DATA_GB DESC
        """)
        if not df_slot.empty:
            st.bar_chart(df_slot, x="TIME_SLOT", y="DATA_GB")
        else:
            st.info("No data available.")


# ============================================================
# CUSTOMER EXPERIENCE
# ============================================================
elif page == "Customer Experience":
    st.header("Customer Experience & Complaints")

    df_cx = run_query(f"""
        SELECT
            COALESCE(SUM(COMPLAINT_COUNT), 0) AS TOTAL,
            COALESCE(SUM(RESOLVED_COUNT), 0) AS RESOLVED,
            ROUND(100.0 * SUM(RESOLVED_COUNT) / NULLIF(SUM(COMPLAINT_COUNT), 0), 2) AS RESOLUTION_RATE,
            ROUND(AVG(AVG_RESOLUTION_HRS), 2) AS AVG_RESOLUTION_HRS,
            ROUND(AVG(AVG_CSAT), 2) AS AVG_CSAT,
            COALESCE(SUM(SLA_BREACH_COUNT), 0) AS SLA_BREACHES
        FROM AIRTEL_DW.ANALYTICS.FACT_CUSTOMER_EXPERIENCE
        WHERE 1=1 {circle_clause()}
    """)

    with st.container(horizontal=True):
        st.metric("Total Complaints", safe_val(df_cx, "TOTAL"), border=True)
        st.metric("Resolved", safe_val(df_cx, "RESOLVED"), border=True)
        st.metric("Resolution Rate", safe_val(df_cx, "RESOLUTION_RATE", suffix="%"), border=True)
        st.metric("Avg Resolution (hrs)", safe_val(df_cx, "AVG_RESOLUTION_HRS", fmt=".1f"), border=True)
        st.metric("Avg CSAT", safe_val(df_cx, "AVG_CSAT", fmt=".2f", suffix="/5"), border=True)
        st.metric("SLA Breaches", safe_val(df_cx, "SLA_BREACHES"), border=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Complaints by Category")
            df_cat = run_query(f"""
                SELECT CATEGORY, SUM(COMPLAINT_COUNT) AS COMPLAINTS,
                    ROUND(AVG(AVG_CSAT), 2) AS CSAT
                FROM AIRTEL_DW.ANALYTICS.FACT_CUSTOMER_EXPERIENCE
                WHERE 1=1 {circle_clause()}
                GROUP BY CATEGORY ORDER BY COMPLAINTS DESC
            """)
            if not df_cat.empty:
                st.bar_chart(df_cat, x="CATEGORY", y="COMPLAINTS")
            else:
                st.info("No data available.")

    with col2:
        with st.container(border=True):
            st.subheader("Complaints by Priority")
            df_pri = run_query(f"""
                SELECT PRIORITY, SUM(COMPLAINT_COUNT) AS COMPLAINTS,
                    SUM(SLA_BREACH_COUNT) AS SLA_BREACHES
                FROM AIRTEL_DW.ANALYTICS.FACT_CUSTOMER_EXPERIENCE
                WHERE 1=1 {circle_clause()}
                GROUP BY PRIORITY ORDER BY COMPLAINTS DESC
            """)
            if not df_pri.empty:
                st.bar_chart(df_pri, x="PRIORITY", y=["COMPLAINTS", "SLA_BREACHES"])
            else:
                st.info("No data available.")

    with st.container(border=True):
        st.subheader("Monthly Complaint Trend")
        df_trend = run_query(f"""
            SELECT COMPLAINT_DATE AS DATE, SUM(COMPLAINT_COUNT) AS COMPLAINTS,
                ROUND(100.0 * SUM(RESOLVED_COUNT) / NULLIF(SUM(COMPLAINT_COUNT), 0), 2) AS RESOLUTION_RATE
            FROM AIRTEL_DW.ANALYTICS.FACT_CUSTOMER_EXPERIENCE
            WHERE 1=1 {circle_clause()}
            GROUP BY COMPLAINT_DATE ORDER BY DATE
        """)
        if not df_trend.empty:
            st.line_chart(df_trend, x="DATE", y="COMPLAINTS")
        else:
            st.info("No data available.")

    with st.container(border=True):
        st.subheader("Complaints by Channel")
        df_ch = run_query(f"""
            SELECT CHANNEL, SUM(COMPLAINT_COUNT) AS COMPLAINTS,
                ROUND(AVG(AVG_RESOLUTION_HRS), 2) AS AVG_RESOLUTION_HRS
            FROM AIRTEL_DW.ANALYTICS.FACT_CUSTOMER_EXPERIENCE
            WHERE 1=1 {circle_clause()}
            GROUP BY CHANNEL ORDER BY COMPLAINTS DESC
        """)
        st.dataframe(df_ch, hide_index=True, use_container_width=True)


# ============================================================
# RECHARGE ANALYTICS
# ============================================================
elif page == "Recharge Analytics":
    st.header("Recharge & Prepaid Analytics")

    df_rch = run_query("""
        SELECT
            COALESCE(SUM(TOTAL_TRANSACTIONS), 0) AS TOTAL,
            COALESCE(SUM(SUCCESSFUL_TRANSACTIONS), 0) AS SUCCESS,
            COALESCE(SUM(TOTAL_RECHARGE_VALUE), 0) AS VALUE,
            ROUND(AVG(AVG_RECHARGE_AMOUNT), 2) AS AVG_AMOUNT,
            ROUND(100.0 * SUM(FAILED_TRANSACTIONS) / NULLIF(SUM(TOTAL_TRANSACTIONS), 0), 2) AS FAIL_RATE
        FROM AIRTEL_DW.ANALYTICS.FACT_RECHARGE_PERFORMANCE
    """)

    with st.container(horizontal=True):
        st.metric("Total Recharges", safe_val(df_rch, "TOTAL"), border=True)
        st.metric("Successful", safe_val(df_rch, "SUCCESS"), border=True)
        st.metric("Total Value (₹)", safe_val(df_rch, "VALUE", prefix="₹"), border=True)
        st.metric("Avg Amount (₹)", safe_val(df_rch, "AVG_AMOUNT", fmt=",.2f", prefix="₹"), border=True)
        st.metric("Failure Rate", safe_val(df_rch, "FAIL_RATE", suffix="%"), border=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Recharge by Channel")
            df_rc = run_query("""
                SELECT CHANNEL, SUM(TOTAL_RECHARGE_VALUE) AS VALUE
                FROM AIRTEL_DW.ANALYTICS.FACT_RECHARGE_PERFORMANCE
                GROUP BY CHANNEL ORDER BY VALUE DESC
            """)
            if not df_rc.empty:
                st.bar_chart(df_rc, x="CHANNEL", y="VALUE")
            else:
                st.info("No data available.")

    with col2:
        with st.container(border=True):
            st.subheader("Recharge by Value Band")
            df_band = run_query("""
                SELECT RECHARGE_BAND, SUM(SUCCESSFUL_TRANSACTIONS) AS RECHARGES,
                    SUM(TOTAL_RECHARGE_VALUE) AS VALUE
                FROM AIRTEL_DW.ANALYTICS.FACT_RECHARGE_PERFORMANCE
                GROUP BY RECHARGE_BAND ORDER BY VALUE DESC
            """)
            if not df_band.empty:
                st.bar_chart(df_band, x="RECHARGE_BAND", y="RECHARGES")
            else:
                st.info("No data available.")

    with st.container(border=True):
        st.subheader("Daily Recharge Trend")
        df_rt = run_query("""
            SELECT RECHARGE_DATE, SUM(SUCCESSFUL_TRANSACTIONS) AS RECHARGES,
                SUM(TOTAL_RECHARGE_VALUE) AS VALUE
            FROM AIRTEL_DW.ANALYTICS.FACT_RECHARGE_PERFORMANCE
            GROUP BY RECHARGE_DATE ORDER BY RECHARGE_DATE
        """)
        if not df_rt.empty:
            st.line_chart(df_rt, x="RECHARGE_DATE", y="VALUE")
        else:
            st.info("No data available.")

    with st.container(border=True):
        st.subheader("Top Recharge Plans")
        df_plans = run_query("""
            SELECT PLAN_NAME, SUM(SUCCESSFUL_TRANSACTIONS) AS RECHARGES,
                SUM(TOTAL_RECHARGE_VALUE) AS VALUE,
                ROUND(AVG(AVG_RECHARGE_AMOUNT), 2) AS AVG_AMOUNT
            FROM AIRTEL_DW.ANALYTICS.FACT_RECHARGE_PERFORMANCE
            GROUP BY PLAN_NAME ORDER BY VALUE DESC
        """)
        st.dataframe(df_plans, hide_index=True, use_container_width=True)

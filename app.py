import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

# =====================================================
# GM CAMPAIGN DASHBOARD
# Pulls campaigns assigned to Gautham Marthandan across:
# - Action Network
# - Vegas Insider
# - Roto Grinders
# - Canada Sports Betting
#
# Recommended deployment:
# - Keep this file in GitHub
# - Deploy via Streamlit Community Cloud / Render / internal server
# - Do NOT expose your monday.com API token in GitHub Pages JavaScript
# =====================================================

MONDAY_API_URL = "https://api.monday.com/v2"

BOARD_NAMES = {
    "Action Network": "6727665427",
    "Vegas Insider": "6727663754",
    "Roto Grinders": "7077539299",
    "Canada Sports Betting": "7101616385",
}

BRAND_STYLES = {
    "Action Network": {"emoji": "🟢", "accent": "#00A862"},
    "Vegas Insider": {"emoji": "🟡", "accent": "#F2C23A"},
    "Roto Grinders": {"emoji": "🔵", "accent": "#2B6CB0"},
    "Canada Sports Betting": {"emoji": "🔴", "accent": "#EF0D23"},
}

ASSIGNEE_MATCHES = [
    "Gautham Marthandan",
    "Gautham",
    "GM",
]

# Optional: add exact Monday column IDs if you know them.
# The app also works without these by scanning all column text values.
PREFERRED_COLUMN_IDS = {
    "person": ["person", "people", "person__1", "people__1"],
    "status": ["status", "status__1", "color", "color__1"],
    "category": ["dropdown4__1", "dropdown", "category", "category__1"],
    "date": ["date", "date__1", "timeline", "timeline__1"],
    "link": ["link", "link__1", "url", "url__1"],
}

STATUS_ORDER = {
    "Working on it": 1,
    "Commissioned": 2,
    "In progress": 3,
    "Outreach in progress": 4,
    "Live on site": 5,
    "Done": 6,
}

STATUS_BADGES = {
    "Done": "✅ Done",
    "Working on it": "🛠️ Working on it",
    "Outreach in progress": "📣 Outreach in progress",
    "Commissioned": "📝 Commissioned",
    "Live on site": "📍 Live on site",
    "In progress": "➡️ In progress",
}


# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="GM Campaign Dashboard",
    page_icon="🧩",
    layout="wide",
)

st.markdown(
    """
<style>
[data-testid="stSidebar"] { background: #0f172a; }
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1380px; }
.gm-hero {
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 18px;
    padding: 22px 24px;
    background: linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,41,59,0.94));
    box-shadow: 0 12px 35px rgba(15,23,42,0.18);
    margin-bottom: 18px;
}
.gm-title {
    color: #f8fafc;
    font-size: 34px;
    font-weight: 850;
    margin: 0 0 5px 0;
    letter-spacing: -0.03em;
}
.gm-subtitle {
    color: #cbd5e1;
    font-size: 15px;
    margin: 0;
}
.metric-card {
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 16px;
    padding: 16px;
    background: #ffffff;
    box-shadow: 0 8px 24px rgba(15,23,42,0.07);
}
.metric-label { color:#64748b; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.03em; }
.metric-value { color:#0f172a; font-size:30px; font-weight:850; line-height:1.1; margin-top:4px; }
.campaign-card {
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-left: 5px solid var(--accent);
    border-radius: 16px;
    padding: 15px 16px;
    background: #ffffff;
    box-shadow: 0 7px 20px rgba(15,23,42,0.06);
    margin-bottom: 12px;
}
.campaign-topline {
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:14px;
}
.campaign-name {
    color:#0f172a;
    font-size:16px;
    font-weight:800;
    line-height:1.35;
}
.brand-pill, .week-pill, .status-pill, .category-pill {
    display:inline-flex;
    align-items:center;
    border-radius:999px;
    padding:5px 9px;
    font-size:12px;
    font-weight:750;
    margin: 7px 6px 0 0;
    white-space:nowrap;
}
.brand-pill { background: color-mix(in srgb, var(--accent) 15%, white); color:#0f172a; border:1px solid color-mix(in srgb, var(--accent) 35%, white); }
.week-pill { background:#f1f5f9; color:#334155; border:1px solid #e2e8f0; }
.status-pill { background:#ecfdf5; color:#065f46; border:1px solid #bbf7d0; }
.category-pill { background:#f8fafc; color:#475569; border:1px solid #e2e8f0; }
.small-muted { color:#64748b; font-size:12px; margin-top:8px; }
hr { margin: 1rem 0; }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# Helpers
# -----------------------------
def get_secret_token() -> str:
    try:
        return st.secrets["monday"]["monday_api_token"]
    except Exception:
        return ""


def monday_request(query: str, variables: Optional[dict] = None) -> dict:
    api_key = get_secret_token()
    if not api_key:
        st.error("Missing monday.com API token. Add it to `.streamlit/secrets.toml` as monday.monday_api_token.")
        st.stop()

    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(MONDAY_API_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    if data.get("errors"):
        st.error(data["errors"])
        st.stop()

    return data


def normalise_text(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def column_map(item: dict) -> Dict[str, str]:
    return {
        col.get("id", ""): normalise_text(col.get("text", ""))
        for col in item.get("column_values", [])
        if normalise_text(col.get("text", ""))
    }


def first_matching_col(cols: Dict[str, str], preferred_ids: List[str]) -> str:
    for col_id in preferred_ids:
        if cols.get(col_id):
            return cols[col_id]
    return ""


def assignee_matches(cols: Dict[str, str]) -> bool:
    combined = " | ".join(cols.values()).lower()
    return any(match.lower() in combined for match in ASSIGNEE_MATCHES)


def extract_status(cols: Dict[str, str]) -> str:
    status = first_matching_col(cols, PREFERRED_COLUMN_IDS["status"])
    if status:
        return status

    # Fallback: detect familiar status labels from any column text.
    all_text = " | ".join(cols.values())
    for status_name in STATUS_BADGES:
        if status_name.lower() in all_text.lower():
            return status_name
    return ""


def extract_category(cols: Dict[str, str]) -> str:
    category = first_matching_col(cols, PREFERRED_COLUMN_IDS["category"])
    if category:
        return category
    return ""


def extract_date(cols: Dict[str, str]) -> str:
    return first_matching_col(cols, PREFERRED_COLUMN_IDS["date"])


def extract_link(cols: Dict[str, str]) -> str:
    return first_matching_col(cols, PREFERRED_COLUMN_IDS["link"])


def parse_week_start(group_title: str) -> Optional[datetime]:
    """Parses group names like `Week c.11.05.26` or `Week 11.05.26`."""
    title = normalise_text(group_title)
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", title)
    if not match:
        return None

    day, month, year = match.groups()
    year_int = int(year)
    if year_int < 100:
        year_int += 2000

    try:
        return datetime(year_int, int(month), int(day))
    except ValueError:
        return None


def current_monday(today: Optional[datetime] = None) -> datetime:
    today = today or datetime.today()
    return datetime(today.year, today.month, today.day) - timedelta(days=today.weekday())


def week_bucket(group_title: str) -> str:
    week_start = parse_week_start(group_title)
    if not week_start:
        return "Unscheduled"

    this_week = current_monday()
    next_week = this_week + timedelta(days=7)

    if week_start < this_week:
        return "Past"
    if this_week <= week_start < next_week:
        return "Current Week"
    if next_week <= week_start < next_week + timedelta(days=7):
        return "Upcoming Week"
    return "Future"


def format_week_range(group_title: str) -> str:
    week_start = parse_week_start(group_title)
    if not week_start:
        return group_title or "No week group"
    week_end = week_start + timedelta(days=6)
    return f"{week_start.strftime('%d %b %Y')} – {week_end.strftime('%d %b %Y')}"


@st.cache_data(ttl=300, show_spinner="Loading Monday campaigns…")
def fetch_board_items(board_id: str) -> List[dict]:
    all_items: List[dict] = []
    cursor = None

    query_first = """
    query ($board_id: [ID!]) {
      boards(ids: $board_id) {
        id
        name
        items_page(limit: 100) {
          cursor
          items {
            id
            name
            group { id title }
            column_values { id text }
            updated_at
          }
        }
      }
    }
    """

    data = monday_request(query_first, {"board_id": [str(board_id)]})
    boards = data.get("data", {}).get("boards", [])
    if not boards:
        return []

    page = boards[0].get("items_page", {})
    all_items.extend(page.get("items", []))
    cursor = page.get("cursor")

    query_next = """
    query ($cursor: String!) {
      next_items_page(limit: 100, cursor: $cursor) {
        cursor
        items {
          id
          name
          group { id title }
          column_values { id text }
          updated_at
        }
      }
    }
    """

    while cursor:
        data = monday_request(query_next, {"cursor": cursor})
        page = data.get("data", {}).get("next_items_page", {})
        all_items.extend(page.get("items", []))
        cursor = page.get("cursor")

    return all_items


@st.cache_data(ttl=300, show_spinner="Filtering campaigns assigned to GM…")
def load_gm_campaigns() -> pd.DataFrame:
    rows = []

    for board_name, board_id in BOARD_NAMES.items():
        items = fetch_board_items(board_id)
        for item in items:
            cols = column_map(item)
            if not assignee_matches(cols):
                continue

            group_title = item.get("group", {}).get("title", "") or ""
            status = extract_status(cols)
            category = extract_category(cols)
            date_value = extract_date(cols)
            link_value = extract_link(cols)
            week_start = parse_week_start(group_title)

            rows.append(
                {
                    "Campaign": normalise_text(item.get("name", "")),
                    "Brand": board_name,
                    "Board ID": board_id,
                    "Item ID": item.get("id", ""),
                    "Group": group_title,
                    "Week Range": format_week_range(group_title),
                    "Week Start": week_start,
                    "Bucket": week_bucket(group_title),
                    "Status": status,
                    "Status Badge": STATUS_BADGES.get(status, status or "No status"),
                    "Category": category,
                    "Date / Timeline": date_value,
                    "Link": link_value,
                    "Updated At": item.get("updated_at", ""),
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    bucket_order = {"Past": 1, "Current Week": 2, "Upcoming Week": 3, "Future": 4, "Unscheduled": 5}
    df["Bucket Sort"] = df["Bucket"].map(bucket_order).fillna(99)
    df["Status Sort"] = df["Status"].map(STATUS_ORDER).fillna(99)
    df = df.sort_values(["Bucket Sort", "Week Start", "Brand", "Status Sort", "Campaign"], na_position="last")
    return df


def campaign_card(row: pd.Series):
    style = BRAND_STYLES.get(row["Brand"], {"emoji": "⚪", "accent": "#64748b"})
    accent = style["accent"]
    emoji = style["emoji"]

    campaign_name = row["Campaign"]
    link = row.get("Link", "")
    if link and link.startswith("http"):
        campaign_html = f'<a href="{link}" target="_blank" style="color:#0f172a;text-decoration:none;">{campaign_name}</a>'
    else:
        campaign_html = campaign_name

    category_html = f'<span class="category-pill">{row["Category"]}</span>' if row.get("Category") else ""
    date_html = f'<div class="small-muted">Date / timeline: {row["Date / Timeline"]}</div>' if row.get("Date / Timeline") else ""

    st.markdown(
        f"""
<div class="campaign-card" style="--accent:{accent};">
  <div class="campaign-topline">
    <div class="campaign-name">{campaign_html}</div>
  </div>
  <div>
    <span class="brand-pill">{emoji} {row['Brand']}</span>
    <span class="week-pill">{row['Bucket']} · {row['Week Range']}</span>
    <span class="status-pill">{row['Status Badge']}</span>
    {category_html}
  </div>
  {date_html}
</div>
""",
        unsafe_allow_html=True,
    )


def show_campaigns(df: pd.DataFrame, title: str):
    st.subheader(title)
    if df.empty:
        st.info("No campaigns found for this view.")
        return

    for _, row in df.iterrows():
        campaign_card(row)


# -----------------------------
# App layout
# -----------------------------
st.markdown(
    """
<div class="gm-hero">
  <h1 class="gm-title">🧩 GM Campaign Dashboard</h1>
  <p class="gm-subtitle">A live view of campaigns assigned to Gautham Marthandan across Action Network, Vegas Insider, Roto Grinders and Canada Sports Betting.</p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("⚙️ Controls")
    if st.button("🔄 Refresh Monday data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption("Data is cached for 5 minutes to avoid hammering the Monday API.")


df = load_gm_campaigns()

if df.empty:
    st.warning("No campaigns assigned to Gautham Marthandan / GM were found. Check the Monday person column text or update ASSIGNEE_MATCHES.")
    st.stop()

# -----------------------------
# Filters
# -----------------------------
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1.2, 1.2, 1.2, 1.8])

with filter_col1:
    brand_filter = st.multiselect(
        "Brand",
        options=list(BOARD_NAMES.keys()),
        default=list(BOARD_NAMES.keys()),
    )

with filter_col2:
    bucket_filter = st.multiselect(
        "Time view",
        options=["Past", "Current Week", "Upcoming Week", "Future", "Unscheduled"],
        default=["Past", "Current Week", "Upcoming Week", "Future", "Unscheduled"],
    )

with filter_col3:
    status_options = sorted([s for s in df["Status"].dropna().unique().tolist() if s])
    status_filter = st.multiselect("Status", options=status_options, default=status_options)

with filter_col4:
    search_text = st.text_input("Search campaigns", placeholder="Search by campaign, group, category or status")

filtered = df.copy()
filtered = filtered[filtered["Brand"].isin(brand_filter)]
filtered = filtered[filtered["Bucket"].isin(bucket_filter)]
if status_filter:
    filtered = filtered[filtered["Status"].isin(status_filter) | filtered["Status"].eq("")]

if search_text.strip():
    q = search_text.strip().lower()
    combined = filtered[["Campaign", "Brand", "Group", "Status", "Category", "Date / Timeline"]].fillna("").agg(" | ".join, axis=1).str.lower()
    filtered = filtered[combined.str.contains(re.escape(q), na=False)]

# -----------------------------
# Metrics
# -----------------------------
metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

with metric_col1:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Total GM Campaigns</div><div class="metric-value">{len(filtered)}</div></div>', unsafe_allow_html=True)
with metric_col2:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Current Week</div><div class="metric-value">{len(filtered[filtered["Bucket"] == "Current Week"])}</div></div>', unsafe_allow_html=True)
with metric_col3:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Upcoming Week</div><div class="metric-value">{len(filtered[filtered["Bucket"] == "Upcoming Week"])}</div></div>', unsafe_allow_html=True)
with metric_col4:
    st.markdown(f'<div class="metric-card"><div class="metric-label">Brands Active</div><div class="metric-value">{filtered["Brand"].nunique()}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# -----------------------------
# Views
# -----------------------------
tab_overview, tab_current, tab_upcoming, tab_past, tab_table = st.tabs(
    ["📌 Overview", "🟢 Current Week", "🔜 Upcoming Week", "📚 Past", "📊 Table"]
)

with tab_overview:
    for bucket in ["Current Week", "Upcoming Week", "Future", "Past", "Unscheduled"]:
        bucket_df = filtered[filtered["Bucket"] == bucket]
        if not bucket_df.empty:
            show_campaigns(bucket_df, f"{bucket} ({len(bucket_df)})")

with tab_current:
    show_campaigns(filtered[filtered["Bucket"] == "Current Week"], "Current Week")

with tab_upcoming:
    show_campaigns(filtered[filtered["Bucket"] == "Upcoming Week"], "Upcoming Week")

with tab_past:
    show_campaigns(filtered[filtered["Bucket"] == "Past"], "Past Campaigns")

with tab_table:
    st.dataframe(
        filtered[["Campaign", "Brand", "Bucket", "Week Range", "Group", "Status", "Category", "Date / Timeline", "Updated At"]],
        use_container_width=True,
        hide_index=True,
    )

    csv = filtered.drop(columns=["Bucket Sort", "Status Sort"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download filtered campaigns as CSV",
        data=csv,
        file_name="gm_monday_campaigns.csv",
        mime="text/csv",
        use_container_width=True,
    )

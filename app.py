import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests
import streamlit as st

# =====================================================
# GM CAMPAIGN DASHBOARD
# Simple live dashboard for campaigns assigned to:
# Gautham Marthandan / Gautham / GM
#
# IMPORTANT LOGIC
# - Vegas Insider + Action Network are group-based boards.
#   The 2026 sync sheet stores Monday group IDs for each week.
# - Roto Grinders + Canada Sports Betting are item-based boards.
#   The 2026 sync sheet stores comma-separated Monday item IDs for each week.
# =====================================================

MONDAY_API_URL = "https://api.monday.com/v2"

# Published Google Sheet base from the existing weekly roundup setup.
# This must be the published `/pub` URL, not the edit URL.
SHEET_PUB_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSLOHk9kqK5iw_7hx8z6zaarsMgo514PmgEV15UwQud2yhFL9PfAnzobTKqjt8LFISgxCG77UXL8vOT/pub"

# 2026 sync table tab: Board_Groups_2026
GID_BY_YEAR = {
    2026: 549871281,
}

BOARD_NAMES = {
    "Action Network": "6727665427",
    "Vegas Insider": "6727663754",
    "Roto Grinders": "7077539299",
    "Canada Sports Betting": "7101616385",
}

# Column names as they appear in the 2026 sync table.
SYNC_SHEET_BRAND_COLUMNS = {
    "Action Network": "Action Network",
    "Vegas Insider": "VegasInsider",
    "Roto Grinders": "RotoGrinders",
    "Canada Sports Betting": "CSB",
}

BRAND_MODE = {
    "Action Network": "group",
    "Vegas Insider": "group",
    "Roto Grinders": "items",
    "Canada Sports Betting": "items",
}

BRAND_STYLES = {
    "Action Network": {"emoji": "🟢", "accent": "#00A862", "soft": "#DCFCE7"},
    "Vegas Insider": {"emoji": "🟡", "accent": "#F2C23A", "soft": "#FEF3C7"},
    "Roto Grinders": {"emoji": "🔵", "accent": "#2563EB", "soft": "#DBEAFE"},
    "Canada Sports Betting": {"emoji": "🔴", "accent": "#EF0D23", "soft": "#FEE2E2"},
}

ASSIGNEE_MATCHES = [
    "Gautham Marthandan",
    "Gautham",
    "GM",
]

PREFERRED_COLUMN_IDS = {
    "person": ["person", "people", "person__1", "people__1"],
    "status": ["status", "status__1", "color", "color__1"],
    "category": ["dropdown4__1", "dropdown", "category", "category__1"],
    "date": ["date", "date__1", "timeline", "timeline__1", "date4"],
    "link": ["link", "link__1", "url", "url__1"],
}

STATUS_ORDER = {
    "Commissioned": 1,
    "Working on it": 2,
    "In progress": 3,
    "Outreach in progress": 4,
    "Live on site": 5,
    "Done": 6,
    "Killed": 7,
}

STATUS_BADGES = {
    "Done": "✅ Done",
    "Working on it": "🛠️ Working on it",
    "Outreach in progress": "📣 Outreach in progress",
    "Commissioned": "📝 Commissioned",
    "Live on site": "📍 Live on site",
    "In progress": "➡️ In progress",
    "Killed": "⛔ Killed",
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
:root {
    --page-bg: #0B0F17;
    --panel-bg: #111827;
    --panel-border: rgba(148, 163, 184, 0.18);
    --text-main: #F8FAFC;
    --text-soft: #CBD5E1;
    --muted: #94A3B8;
    --card-bg: #FFFFFF;
    --card-text: #111827;
    --green: #10B981;
}

.stApp { background: var(--page-bg); }
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1280px;
}

[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

h1, h2, h3, p, label, span, div { font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }

.gm-hero {
    border: 1px solid var(--panel-border);
    border-radius: 22px;
    padding: 24px 28px;
    background: linear-gradient(135deg, #111827 0%, #172033 55%, #0F172A 100%);
    box-shadow: 0 18px 45px rgba(0,0,0,0.24);
    margin-bottom: 18px;
}
.gm-title {
    color: var(--text-main);
    font-size: 36px;
    font-weight: 900;
    letter-spacing: -0.04em;
    margin: 0 0 8px 0;
}
.gm-subtitle {
    color: var(--text-soft);
    font-size: 16px;
    line-height: 1.65;
    max-width: 980px;
    margin: 0;
}

.section-title {
    color: var(--text-main);
    font-size: 28px;
    font-weight: 850;
    letter-spacing: -0.03em;
    margin: 18px 0 14px;
}
.section-kicker {
    color: var(--muted);
    font-size: 14px;
    margin-top: -6px;
    margin-bottom: 16px;
}

.metric-wrap {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
    margin: 8px 0 22px;
}
.metric-card {
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 20px;
    padding: 18px 20px;
    background: #FFFFFF;
    box-shadow: 0 10px 28px rgba(0,0,0,0.16);
}
.metric-label {
    color:#64748b;
    font-size:12px;
    font-weight:850;
    text-transform:uppercase;
    letter-spacing:.08em;
}
.metric-value {
    color:#0f172a;
    font-size:34px;
    font-weight:900;
    line-height:1;
    margin-top:9px;
}

.campaign-card {
    border: 1px solid rgba(226, 232, 240, 0.95);
    border-left: 6px solid var(--accent);
    border-radius: 20px;
    padding: 22px 24px;
    background: #FFFFFF;
    box-shadow: 0 10px 24px rgba(0,0,0,0.18);
    margin-bottom: 16px;
}
.campaign-name {
    color:#111827;
    font-size:22px;
    font-weight:900;
    line-height:1.3;
    letter-spacing: -0.02em;
    margin-bottom: 12px;
}
.brand-pill, .week-pill, .status-pill, .category-pill {
    display:inline-flex;
    align-items:center;
    border-radius:999px;
    padding:8px 13px;
    font-size:14px;
    font-weight:800;
    margin: 0 8px 8px 0;
    white-space:nowrap;
}
.brand-pill {
    background: var(--brand-soft);
    color:#0f172a;
    border:1px solid color-mix(in srgb, var(--accent) 35%, white);
}
.week-pill {
    background:#F1F5F9;
    color:#334155;
    border:1px solid #E2E8F0;
}
.status-pill {
    background:#ECFDF5;
    color:#065F46;
    border:1px solid #A7F3D0;
}
.category-pill {
    background:#F8FAFC;
    color:#475569;
    border:1px solid #E2E8F0;
}
.small-muted {
    color:#64748b;
    font-size:13px;
    margin-top:5px;
}

.empty-card {
    border: 1px dashed rgba(148, 163, 184, 0.4);
    border-radius: 18px;
    background: rgba(15, 23, 42, 0.65);
    padding: 26px;
    color: #CBD5E1;
    margin-bottom: 16px;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 14px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.22);
}
.stTabs [data-baseweb="tab"] {
    color: #E5E7EB;
    font-size: 18px;
    font-weight: 850;
    padding-left: 4px;
    padding-right: 4px;
}
.stTabs [aria-selected="true"] {
    color: #F43F5E !important;
}

div[data-baseweb="select"] > div,
input {
    border-radius: 13px !important;
    background: #252632 !important;
    border-color: rgba(148, 163, 184, 0.22) !important;
    color: #F8FAFC !important;
}

label, [data-testid="stWidgetLabel"] p {
    color: #F8FAFC !important;
    font-weight: 750 !important;
}

.stDataFrame { border-radius: 16px; overflow: hidden; }

@media (max-width: 900px) {
    .metric-wrap { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .gm-title { font-size: 30px; }
    .campaign-name { font-size: 19px; }
}
@media (max-width: 620px) {
    .metric-wrap { grid-template-columns: 1fr; }
    .campaign-card { padding: 18px; }
    .brand-pill, .week-pill, .status-pill, .category-pill { font-size: 12px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# Monday + Sheet helpers
# -----------------------------
def get_secret_token() -> str:
    try:
        return st.secrets["monday"]["monday_api_token"]
    except Exception:
        return ""


def csv_url_for_year(year: int) -> str:
    gid = GID_BY_YEAR.get(year)
    if gid is None:
        raise ValueError(f"Missing Google Sheet gid for {year}.")
    return f"{SHEET_PUB_BASE}?gid={gid}&single=true&output=csv"


def monday_request(query: str, variables: Optional[dict] = None) -> dict:
    api_key = get_secret_token()
    if not api_key:
        st.error("Missing monday.com API token. Add it to Streamlit secrets as monday.monday_api_token.")
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


def clean_sheet_cell(value) -> str:
    text = normalise_text(value)
    if not text or text.upper() in {"NA", "N/A", "NONE", "NAN"}:
        return ""
    return text


def parse_item_ids(value) -> List[str]:
    text = clean_sheet_cell(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


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

    all_text = " | ".join(cols.values())
    for status_name in STATUS_BADGES:
        if status_name.lower() in all_text.lower():
            return status_name
    return ""


def extract_category(cols: Dict[str, str]) -> str:
    return first_matching_col(cols, PREFERRED_COLUMN_IDS["category"])


def extract_date(cols: Dict[str, str]) -> str:
    return first_matching_col(cols, PREFERRED_COLUMN_IDS["date"])


def extract_link(cols: Dict[str, str]) -> str:
    return first_matching_col(cols, PREFERRED_COLUMN_IDS["link"])


def parse_week_start(group_title: str) -> Optional[datetime]:
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


def bucket_from_week_start(week_start: Optional[datetime]) -> str:
    if not week_start:
        return "Unscheduled"

    this_week = current_monday()
    next_week = this_week + timedelta(days=7)

    if this_week <= week_start < next_week:
        return "Current Week"
    if next_week <= week_start < next_week + timedelta(days=7):
        return "Upcoming Week"
    if week_start < this_week:
        return "Past"
    return "Future"


def format_week_range_from_start(week_start: Optional[datetime], fallback: str = "") -> str:
    if not week_start:
        return fallback or "No week group"
    week_end = week_start + timedelta(days=6)
    return f"{week_start.strftime('%d %b %Y')} – {week_end.strftime('%d %b %Y')}"


@st.cache_data(ttl=300, show_spinner="Loading 2026 sync table…")
def load_sync_table(year: int = 2026) -> pd.DataFrame:
    df = pd.read_csv(csv_url_for_year(year))
    df.columns = [normalise_text(c) for c in df.columns]

    if "Week" not in df.columns:
        st.error("The 2026 sync table needs a `Week` column.")
        st.stop()

    df["Week"] = df["Week"].apply(clean_sheet_cell)
    df = df[df["Week"].str.match(r"^Week c\.\d{2}\.\d{2}\.\d{2}$", na=False)].copy()
    df["Week Start"] = df["Week"].apply(parse_week_start)
    df["Bucket"] = df["Week Start"].apply(bucket_from_week_start)
    df["Week Range"] = df.apply(lambda r: format_week_range_from_start(r["Week Start"], r["Week"]), axis=1)
    return df


@st.cache_data(ttl=300, show_spinner="Loading campaigns from Monday…")
def fetch_items_by_group(board_id: str, group_id: str) -> List[dict]:
    if not group_id:
        return []

    all_items: List[dict] = []

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

    return [item for item in all_items if str(item.get("group", {}).get("id", "")) == str(group_id)]


@st.cache_data(ttl=300, show_spinner="Loading item-based campaigns from Monday…")
def fetch_items_by_ids(item_ids: List[str]) -> List[dict]:
    if not item_ids:
        return []

    cleaned_ids = [str(i).strip() for i in item_ids if str(i).strip()]
    if not cleaned_ids:
        return []

    all_items: List[dict] = []

    # Monday GraphQL can be sensitive with very long ID arrays, so chunk safely.
    chunk_size = 80
    for start in range(0, len(cleaned_ids), chunk_size):
        chunk = cleaned_ids[start:start + chunk_size]
        ids_str = ", ".join(chunk)
        query = f"""
        query {{
          items(ids: [{ids_str}]) {{
            id
            name
            group {{ id title }}
            column_values {{ id text }}
            updated_at
          }}
        }}
        """
        data = monday_request(query)
        all_items.extend(data.get("data", {}).get("items", []) or [])

    return all_items


@st.cache_data(ttl=300, show_spinner="Filtering campaigns assigned to GM…")
def load_gm_campaigns(year: int = 2026) -> pd.DataFrame:
    sync_df = load_sync_table(year)
    rows = []

    for _, week_row in sync_df.iterrows():
        week_label = week_row["Week"]
        week_start = week_row["Week Start"]
        week_range = week_row["Week Range"]
        bucket = week_row["Bucket"]

        for board_name, board_id in BOARD_NAMES.items():
            sheet_col = SYNC_SHEET_BRAND_COLUMNS[board_name]
            if sheet_col not in sync_df.columns:
                continue

            mode = BRAND_MODE[board_name]
            sheet_value = week_row.get(sheet_col, "")

            if mode == "group":
                group_id = clean_sheet_cell(sheet_value)
                items = fetch_items_by_group(board_id, group_id) if group_id else []
            else:
                item_ids = parse_item_ids(sheet_value)
                items = fetch_items_by_ids(item_ids) if item_ids else []

            for item in items:
                cols = column_map(item)
                if not assignee_matches(cols):
                    continue

                status = extract_status(cols)
                category = extract_category(cols)
                date_value = extract_date(cols)
                link_value = extract_link(cols)

                rows.append(
                    {
                        "Campaign": normalise_text(item.get("name", "")),
                        "Brand": board_name,
                        "Group": week_label,
                        "Week Range": week_range,
                        "Week Start": week_start,
                        "Bucket": bucket,
                        "Status": status,
                        "Status Badge": STATUS_BADGES.get(status, status or "No status"),
                        "Category": category,
                        "Date / Timeline": date_value,
                        "Link": link_value,
                        "Updated At": item.get("updated_at", ""),
                        "Monday Item ID": item.get("id", ""),
                    }
                )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # De-dupe in case the same item appears in more than one synced week row.
    df = df.drop_duplicates(subset=["Brand", "Monday Item ID", "Group"], keep="first")

    bucket_order = {"Current Week": 1, "Upcoming Week": 2, "Future": 3, "Past": 4, "Unscheduled": 5}
    df["Bucket Sort"] = df["Bucket"].map(bucket_order).fillna(99)
    df["Status Sort"] = df["Status"].map(STATUS_ORDER).fillna(99)
    df = df.sort_values(["Bucket Sort", "Week Start", "Brand", "Status Sort", "Campaign"], na_position="last")
    return df


def apply_brand_filter(df: pd.DataFrame, brand_choice: str) -> pd.DataFrame:
    if brand_choice == "All Brands":
        return df
    return df[df["Brand"] == brand_choice]


def apply_search(df: pd.DataFrame, search_text: str) -> pd.DataFrame:
    if not search_text.strip():
        return df
    q = search_text.strip().lower()
    combined = df[["Campaign", "Brand", "Group", "Status", "Category", "Date / Timeline"]].fillna("").agg(" | ".join, axis=1).str.lower()
    return df[combined.str.contains(re.escape(q), na=False)]


def campaign_card(row: pd.Series):
    style = BRAND_STYLES.get(row["Brand"], {"emoji": "⚪", "accent": "#64748B", "soft": "#F1F5F9"})
    accent = style["accent"]
    soft = style["soft"]
    emoji = style["emoji"]

    campaign_name = row["Campaign"]
    link = row.get("Link", "")
    if isinstance(link, str) and link.startswith("http"):
        campaign_html = f'<a href="{link}" target="_blank" style="color:#111827;text-decoration:none;">{campaign_name}</a>'
    else:
        campaign_html = campaign_name

    category_html = f'<span class="category-pill">{row["Category"]}</span>' if row.get("Category") else ""
    date_html = f'<div class="small-muted">Date / timeline: {row["Date / Timeline"]}</div>' if row.get("Date / Timeline") else ""

    st.markdown(
        f"""
<div class="campaign-card" style="--accent:{accent}; --brand-soft:{soft};">
  <div class="campaign-name">{campaign_html}</div>
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


def show_campaign_list(df: pd.DataFrame, empty_message: str):
    if df.empty:
        st.markdown(f'<div class="empty-card">{empty_message}</div>', unsafe_allow_html=True)
        return
    for _, row in df.iterrows():
        campaign_card(row)


def metrics_html(current_count: int, upcoming_count: int, total_count: int, active_brands: int):
    st.markdown(
        f"""
<div class="metric-wrap">
  <div class="metric-card"><div class="metric-label">Current Week</div><div class="metric-value">{current_count}</div></div>
  <div class="metric-card"><div class="metric-label">Upcoming Week</div><div class="metric-value">{upcoming_count}</div></div>
  <div class="metric-card"><div class="metric-label">Total GM Campaigns</div><div class="metric-value">{total_count}</div></div>
  <div class="metric-card"><div class="metric-label">Brands Active</div><div class="metric-value">{active_brands}</div></div>
</div>
""",
        unsafe_allow_html=True,
    )

# -----------------------------
# App layout
# -----------------------------
st.markdown(
    """
<div class="gm-hero">
  <h1 class="gm-title">🧩 GM Campaign Dashboard</h1>
  <p class="gm-subtitle">A simple live view of campaigns assigned to Gautham Marthandan across Action Network, Vegas Insider, Roto Grinders and Canada Sports Betting. The dashboard uses the 2026 sync table, with group-based logic for Action Network/Vegas Insider and item-based logic for Roto Grinders/Canada Sports Betting.</p>
</div>
""",
    unsafe_allow_html=True,
)

refresh_col, spacer_col = st.columns([1, 5])
with refresh_col:
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

campaigns = load_gm_campaigns(2026)

if campaigns.empty:
    st.warning("No campaigns assigned to Gautham Marthandan / GM were found from the 2026 sync table. Check the sync sheet, item IDs, group IDs, and Monday person column text.")
    st.stop()

current_df = campaigns[campaigns["Bucket"] == "Current Week"].copy()
upcoming_df = campaigns[campaigns["Bucket"] == "Upcoming Week"].copy()

metrics_html(
    current_count=len(current_df),
    upcoming_count=len(upcoming_df),
    total_count=len(campaigns),
    active_brands=campaigns["Brand"].nunique(),
)

main_tab, all_tab = st.tabs(["📌 This Week + Next Week", "📚 All Campaigns"])

with main_tab:
    st.markdown('<div class="section-title">This Week</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">Campaigns currently assigned to you for this week.</div>', unsafe_allow_html=True)
    show_campaign_list(current_df, "No campaigns assigned to you for the current week.")

    st.markdown('<div class="section-title">Coming Up Next Week</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">Campaigns already lined up for next week.</div>', unsafe_allow_html=True)
    show_campaign_list(upcoming_df, "No campaigns assigned to you for next week yet.")

with all_tab:
    st.markdown('<div class="section-title">All Campaigns</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">Use this section when you want to search older campaigns or filter by brand.</div>', unsafe_allow_html=True)

    filter_col1, filter_col2, filter_col3 = st.columns([1.15, 1.15, 2.2])

    with filter_col1:
        brand_choice = st.selectbox(
            "Brand",
            ["All Brands"] + list(BOARD_NAMES.keys()),
            index=0,
        )

    with filter_col2:
        time_choice = st.selectbox(
            "Campaign view",
            ["All Campaigns", "Past", "Current Week", "Upcoming Week", "Future", "Unscheduled"],
            index=0,
        )

    with filter_col3:
        search_text = st.text_input(
            "Search campaigns",
            placeholder="Search by campaign, group, category or status",
        )

    all_filtered = campaigns.copy()
    all_filtered = apply_brand_filter(all_filtered, brand_choice)
    if time_choice != "All Campaigns":
        all_filtered = all_filtered[all_filtered["Bucket"] == time_choice]
    all_filtered = apply_search(all_filtered, search_text)

    st.markdown(
        f'<div class="section-kicker">Showing {len(all_filtered)} campaign(s).</div>',
        unsafe_allow_html=True,
    )

    show_campaign_list(all_filtered, "No campaigns matched your filters.")

    with st.expander("Open table view / download CSV", expanded=False):
        st.dataframe(
            all_filtered[["Campaign", "Brand", "Bucket", "Week Range", "Group", "Status", "Category", "Date / Timeline", "Updated At"]],
            use_container_width=True,
            hide_index=True,
        )

        csv = all_filtered.drop(columns=["Bucket Sort", "Status Sort"], errors="ignore").to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download filtered campaigns as CSV",
            data=csv,
            file_name="gm_monday_campaigns.csv",
            mime="text/csv",
            use_container_width=True,
        )

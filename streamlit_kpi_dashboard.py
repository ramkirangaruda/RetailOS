import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="RetailOS KPI Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with Color Theme
st.markdown("""
<style>
/* Color Theme */
:root {
    --primary-dark: #30364f;
    --secondary-teal: #bacae1;
    --accent-light: #bcf0f0;
    --highlight-beige: #f0f0db;
    --success-green: #2ecc71;
    --info-blue: #3498db;
    --warning-orange: #f39c12;
    --danger-red: #e74c3c;
}

/* Main Background */
body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%);
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(135deg, #30364f 0%, #3d4563 100%);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: #ffffff !important;
}

[data-testid="stSidebar"] p {
    color: #ffffff !important;
}

[data-testid="stSidebar"] span {
    color: #ffffff !important;
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4,
[data-testid="stSidebar"] h5,
[data-testid="stSidebar"] h6 {
    color: #ffffff !important;
}

[data-testid="stSidebar"] label {
    color: #ffffff !important;
}

[data-testid="stSidebar"] [role="radio"] label {
    color: #ffffff !important;
}

[data-testid="stSidebar"] [data-testid="stInfo"] {
    background-color: rgba(48, 54, 79, 0.8) !important;
    border-left: 4px solid #bacae1 !important;
}

[data-testid="stSidebar"] [data-testid="stInfo"] p {
    color: #bacae1 !important;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    color: #30364f;
    font-weight: 700;
    letter-spacing: 0.5px;
}

/* Metric Cards Container */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%) !important;
    border-radius: 12px !important;
    border-left: 4px solid #bacae1 !important;
    padding: 24px !important;
    box-shadow: 0 2px 8px rgba(48, 54, 79, 0.08) !important;
    transition: all 0.3s ease;
    margin-bottom: 16px;
}

[data-testid="metric-container"]:hover {
    box-shadow: 0 4px 16px rgba(48, 54, 79, 0.12) !important;
    transform: translateY(-2px);
}

/* Metric Label */
[data-testid="metric-container"] > div:first-child {
    color: #30364f !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    letter-spacing: 0.3px;
    margin-bottom: 8px !important;
}

/* Metric Value */
[data-testid="metric-container"] > div:last-child {
    color: #2ecc71 !important;
    font-weight: 800 !important;
    font-size: 28px !important;
    line-height: 1.2;
    word-wrap: break-word;
    overflow-wrap: break-word;
}

/* Custom Metric Cards */
.custom-metric-card {
    background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
    border-radius: 12px;
    border-left: 4px solid #bacae1;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(48, 54, 79, 0.08);
    text-align: center;
    transition: all 0.3s ease;
}

.custom-metric-card:hover {
    box-shadow: 0 4px 16px rgba(48, 54, 79, 0.12);
    transform: translateY(-2px);
}

.metric-label {
    color: #30364f;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
}

.metric-value {
    color: #2ecc71;
    font-size: 28px;
    font-weight: 800;
    line-height: 1.2;
    word-break: break-word;
    display: block;
}

.metric-secondary {
    color: #bacae1;
    font-size: 12px;
    margin-top: 8px;
    font-style: italic;
}

/* Buttons */
button {
    background: linear-gradient(135deg, #bacae1 0%, #a5b5d0 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}

button:hover {
    background: linear-gradient(135deg, #a5b5d0 0%, #9aabca 100%) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(48, 54, 79, 0.15) !important;
}

/* Select Box */
[data-testid="stSelectbox"] [data-baseweb="select"] {
    background-color: #ffffff !important;
    border: 2px solid #bacae1 !important;
    border-radius: 8px !important;
}

/* Date Input */
[data-testid="stDateInput"] input {
    background-color: #ffffff !important;
    border: 2px solid #bacae1 !important;
    border-radius: 8px !important;
    color: #30364f !important;
}

/* Expandable Sections */
[data-testid="stExpander"] {
    background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
    border: 2px solid #bacae1 !important;
    border-radius: 12px !important;
    margin: 16px 0 !important;
}

[data-testid="stExpander"] [data-testid="stMarkdownContainer"] {
    color: #30364f;
}

/* Divider */
hr {
    border-color: #bacae1 !important;
    margin: 24px 0 !important;
}

/* Info/Warning Boxes */
[data-testid="stInfo"] {
    background-color: #e8f4f8 !important;
    border-left: 4px solid #bcf0f0 !important;
    border-radius: 8px !important;
}

[data-testid="stWarning"] {
    background-color: #fef5e7 !important;
    border-left: 4px solid #f0f0db !important;
    border-radius: 8px !important;
}

[data-testid="stError"] {
    background-color: #fadbd8 !important;
    border-left: 4px solid #e74c3c !important;
    border-radius: 8px !important;
}

/* Dataframe Styling */
[data-testid="stDataFrame"] {
    background-color: #ffffff !important;
}

/* Radio Button */
[data-testid="stRadio"] [role="radio"] {
    accent-color: #bacae1 !important;
}

/* Text in sidebar */
.css-1y4p5pa {
    color: #ffffff !important;
}

/* All sidebar text elements */
[data-testid="stSidebar"] .stRadio > label {
    color: #ffffff !important;
}

[data-testid="stSidebar"] div {
    color: #ffffff !important;
}

[data-testid="stSidebar"] .element-container {
    color: #ffffff !important;
}

[data-testid="stSidebar"] .stInfo, 
[data-testid="stSidebar"] .stWarning,
[data-testid="stSidebar"] .stError {
    color: #ffffff !important;
}

/* Markdown text */
p {
    color: #30364f;
    line-height: 1.6;
}

/* Link styling */
a {
    color: #bacae1 !important;
    text-decoration: none;
}

a:hover {
    color: #a5b5d0 !important;
    text-decoration: underline;
}

/* Footer */
.footer-text {
    color: #bacae1;
    font-size: 12px;
    text-align: center;
    margin-top: 40px;
    padding: 20px;
    border-top: 2px solid #bacae1;
}

/* Title styling */
[data-testid="stMarkdownContainer"] > h1 {
    color: #30364f !important;
    font-size: 36px !important;
    font-weight: 800 !important;
    margin-bottom: 24px !important;
    background: linear-gradient(135deg, #30364f 0%, #bacae1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

</style>
""", unsafe_allow_html=True)

# Configuration
KPI_DATA_PATH = "output/kpi_tables_export"

@st.cache_data(ttl=300)
def load_kpi_data():
    """Load all KPI data from CSV files"""
    data = {}
    kpi_files = {
        'summary': 'kpi_summary_dashboard.csv',
        'daily_revenue': 'kpi_daily_revenue.csv',
        'monthly_revenue': 'kpi_monthly_revenue.csv',
        'city_sales': 'kpi_city_sales.csv',
        'top_products': 'kpi_top_products.csv',
        'inventory_turnover': 'kpi_inventory_turnover.csv'
    }

    for key, filename in kpi_files.items():
        file_path = os.path.join(KPI_DATA_PATH, filename)
        if os.path.exists(file_path):
            try:
                data[key] = pd.read_csv(file_path)
            except Exception as e:
                st.error(f"Error loading {filename}: {e}")
                data[key] = pd.DataFrame()
        else:
            st.warning(f"File not found: {filename}")
            data[key] = pd.DataFrame()

    return data

def format_currency(value):
    """Format currency values"""
    if pd.isna(value):
        return "N/A"
    return f"₹{value:,.0f}"

def format_number(value):
    """Format large numbers"""
    if pd.isna(value):
        return "N/A"
    return f"{value:,.0f}"

def create_metric_card(label, value, icon="", subtext=""):
    """Create a custom metric card with proper styling"""
    html_content = f"""
    <div class="custom-metric-card">
        <div class="metric-label">{icon} {label}</div>
        <div class="metric-value">{value}</div>
        {f'<div class="metric-secondary">{subtext}</div>' if subtext else ''}
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

def show_summary_dashboard(data):
    """Show summary dashboard with key metrics"""
    st.header("📊 Executive Summary Dashboard")

    if data['summary'].empty:
        st.error("No summary data available")
        return

    # Create metric cards
    summary_data = data['summary'].set_index('metric')['value'].to_dict()

    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        create_metric_card(
            "Total Revenue",
            format_currency(summary_data.get('Total Revenue', 0)),
            icon="💰",
            subtext="Overall earnings"
        )

    with col2:
        create_metric_card(
            "Total Transactions",
            format_number(summary_data.get('Total Transactions', 0)),
            icon="🛒",
            subtext="Total sales count"
        )

    with col3:
        create_metric_card(
            "Total Customers",
            format_number(summary_data.get('Total Customers', 0)),
            icon="👥",
            subtext="Unique customers"
        )

    with col4:
        create_metric_card(
            "Total Products",
            format_number(summary_data.get('Total Products', 0)),
            icon="🛍️",
            subtext="Active SKUs"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Average transaction value
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        avg_transaction = summary_data.get('Avg Transaction Value', 0)
        create_metric_card(
            "Avg Transaction",
            format_currency(avg_transaction),
            icon="💳",
            subtext="Average order value"
        )

def show_daily_revenue_analysis(data):
    """Show daily revenue analysis with trends"""
    st.header("📈 Daily Revenue Analysis")

    if data['daily_revenue'].empty:
        st.error("No daily revenue data available")
        return

    df = data['daily_revenue'].copy()
    df['date'] = pd.to_datetime(df['date'])

    # Date range filter
    col1, col2 = st.columns(2, gap="medium")
    with col1:
        start_date = st.date_input("Start Date", df['date'].min().date())
    with col2:
        end_date = st.date_input("End Date", df['date'].max().date())

    # Filter data
    mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
    filtered_df = df[mask]

    # Key metrics
    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        total_revenue = filtered_df['daily_revenue'].sum()
        st.metric(
            "💰 Total Revenue",
            format_currency(total_revenue),
            delta=None
        )

    with col2:
        avg_revenue = filtered_df['daily_revenue'].mean()
        st.metric(
            "📊 Avg Daily Revenue",
            format_currency(avg_revenue),
            delta=None
        )

    with col3:
        total_transactions = filtered_df['transaction_count'].sum()
        st.metric(
            "🛒 Total Transactions",
            format_number(total_transactions),
            delta=None
        )

    with col4:
        avg_transaction = filtered_df['avg_transaction_value'].mean()
        st.metric(
            "💳 Avg Transaction",
            format_currency(avg_transaction),
            delta=None
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Time series chart with color theme
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Daily Revenue Trend', 'Daily Transaction Count'),
        vertical_spacing=0.12
    )

    # Revenue trend
    fig.add_trace(
        go.Scatter(
            x=filtered_df['date'],
            y=filtered_df['daily_revenue'],
            mode='lines+markers',
            name='Daily Revenue',
            line=dict(color='#2ecc71', width=3),
            marker=dict(size=6, color='#2ecc71'),
            hovertemplate='<b>Date:</b> %{x|%b %d, %Y}<br><b>Revenue:</b> ₹%{y:,.0f}<extra></extra>'
        ),
        row=1, col=1
    )

    # Transaction trend
    fig.add_trace(
        go.Scatter(
            x=filtered_df['date'],
            y=filtered_df['transaction_count'],
            mode='lines+markers',
            name='Transactions',
            line=dict(color='#3498db', width=3),
            marker=dict(size=6, color='#3498db'),
            hovertemplate='<b>Date:</b> %{x|%b %d, %Y}<br><b>Transactions:</b> %{y}<extra></extra>'
        ),
        row=2, col=1
    )

    fig.update_layout(
        height=700,
        title_text="<b>Daily Revenue and Transaction Trends</b>",
        title_font_size=18,
        title_font_color='#30364f',
        showlegend=False,
        plot_bgcolor='rgba(248, 251, 255, 0.5)',
        paper_bgcolor='rgba(245, 247, 250, 0)',
        hovermode='x unified',
        margin=dict(l=80, r=20, t=80, b=60)
    )

    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(186, 202, 225, 0.2)')
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(186, 202, 225, 0.2)')

    st.plotly_chart(fig, use_container_width=True)

    # Day type analysis
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        day_type_revenue = filtered_df.groupby('day_type')['daily_revenue'].sum().reset_index()
        fig_pie = px.pie(
            day_type_revenue,
            values='daily_revenue',
            names='day_type',
            title='<b>Revenue by Day Type</b>',
            color_discrete_map={'Weekday': '#3498db', 'Weekend': '#e74c3c'},
            hole=0.4
        )
        fig_pie.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            paper_bgcolor='rgba(245, 247, 250, 0)'
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # Top 10 revenue days
        top_days = filtered_df.nlargest(10, 'daily_revenue')[['date', 'daily_revenue', 'day_type']]
        fig_bar = px.bar(
            top_days,
            x='date',
            y='daily_revenue',
            color='day_type',
            title='<b>Top 10 Revenue Days</b>',
            labels={'daily_revenue': 'Revenue (₹)', 'date': 'Date'},
            color_discrete_map={'Weekday': '#3498db', 'Weekend': '#e74c3c'}
        )
        fig_bar.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='x unified'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Data table
    with st.expander("📋 View Daily Revenue Data"):
        display_df = filtered_df[['date', 'day_type', 'daily_revenue', 'transaction_count', 'avg_transaction_value']].copy()
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        st.dataframe(display_df, use_container_width=True, hide_index=True)

def show_city_sales_analysis(data):
    """Show city-wise sales performance"""
    st.header("🏙️ City Sales Performance")

    if data['city_sales'].empty:
        st.error("No city sales data available")
        return

    df = data['city_sales'].copy()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        total_cities = len(df)
        st.metric("🌍 Total Cities", total_cities)

    with col2:
        total_revenue = df['total_revenue'].sum()
        st.metric("💰 Total Revenue", format_currency(total_revenue))

    with col3:
        avg_revenue_per_city = df['total_revenue'].mean()
        st.metric("📊 Avg Revenue/City", format_currency(avg_revenue_per_city))

    with col4:
        total_stores = df['active_stores'].sum()
        st.metric("🏪 Total Stores", format_number(total_stores))

    st.markdown("<br>", unsafe_allow_html=True)

    # City revenue chart
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        fig_bar = px.bar(
            df.head(10),
            x='city',
            y='total_revenue',
            color='region',
            title='<b>Top 10 Cities by Revenue</b>',
            labels={'total_revenue': 'Revenue (₹)', 'city': 'City'},
            height=450
        )
        fig_bar.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='x unified'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        # Region performance
        region_revenue = df.groupby('region')['total_revenue'].sum().reset_index()
        fig_pie = px.pie(
            region_revenue,
            values='total_revenue',
            names='region',
            title='<b>Revenue by Region</b>',
            height=450,
            hole=0.4
        )
        fig_pie.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            paper_bgcolor='rgba(245, 247, 250, 0)'
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Store performance analysis
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        fig_scatter = px.scatter(
            df,
            x='active_stores',
            y='total_revenue',
            size='transaction_count',
            color='region',
            hover_name='city',
            title='<b>Store Count vs Revenue</b>',
            labels={
                'active_stores': 'Active Stores',
                'total_revenue': 'Total Revenue (₹)',
                'transaction_count': 'Transactions'
            },
            height=450
        )
        fig_scatter.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='closest'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col2:
        # Average transaction value by city
        df_sorted = df.sort_values('avg_transaction_value', ascending=False).head(10)
        fig_atv = px.bar(
            df_sorted,
            x='city',
            y='avg_transaction_value',
            color='region',
            title='<b>Top 10 Cities by Avg Transaction Value</b>',
            labels={'avg_transaction_value': 'Avg Transaction (₹)', 'city': 'City'},
            height=450
        )
        fig_atv.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='x unified'
        )
        st.plotly_chart(fig_atv, use_container_width=True)

    # Detailed table
    with st.expander("📋 View City Sales Data"):
        display_cols = ['city', 'region', 'active_stores', 'total_revenue', 'transaction_count', 'avg_transaction_value']
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

def show_product_performance(data):
    """Show product performance analysis"""
    st.header("🛍️ Product Performance Analysis")

    if data['top_products'].empty:
        st.error("No product data available")
        return

    df = data['top_products'].copy()

    # Category filter
    selected_category = st.selectbox(
        "Select Category",
        ['All'] + list(df['category'].unique()),
        index=0,
        key="product_category"
    )

    if selected_category != 'All':
        df = df[df['category'] == selected_category]

    # Key metrics
    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        total_products = len(df)
        st.metric("📦 Total Products", total_products)

    with col2:
        total_revenue = df['total_revenue'].sum()
        st.metric("💰 Total Revenue", format_currency(total_revenue))

    with col3:
        total_quantity = df['total_quantity_sold'].sum()
        st.metric("📊 Total Units Sold", format_number(total_quantity))

    with col4:
        avg_revenue_per_product = df['total_revenue'].mean()
        st.metric("💵 Avg Revenue/Product", format_currency(avg_revenue_per_product))

    st.markdown("<br>", unsafe_allow_html=True)

    # Top products chart
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        top_10_products = df.head(10)
        fig_bar = px.bar(
            top_10_products,
            x='product_name',
            y='total_revenue',
            color='category',
            title='<b>Top 10 Products by Revenue</b>',
            labels={'total_revenue': 'Revenue (₹)', 'product_name': 'Product'},
            height=450
        )
        fig_bar.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='x unified'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        # Category performance
        category_revenue = df.groupby('category')['total_revenue'].sum().reset_index()
        fig_pie = px.pie(
            category_revenue,
            values='total_revenue',
            names='category',
            title='<b>Revenue by Product Category</b>',
            height=450,
            hole=0.4
        )
        fig_pie.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            paper_bgcolor='rgba(245, 247, 250, 0)'
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Quantity vs Revenue analysis
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        fig_scatter = px.scatter(
            df.head(20),
            x='total_quantity_sold',
            y='total_revenue',
            size='transaction_count',
            color='category',
            hover_name='product_name',
            title='<b>Quantity Sold vs Revenue</b>',
            labels={
                'total_quantity_sold': 'Quantity Sold',
                'total_revenue': 'Revenue (₹)',
                'transaction_count': 'Transactions'
            },
            height=450
        )
        fig_scatter.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='closest'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col2:
        # Transaction frequency
        df_sorted = df.sort_values('transaction_count', ascending=False).head(10)
        fig_trans = px.bar(
            df_sorted,
            x='product_name',
            y='transaction_count',
            color='category',
            title='<b>Top 10 Products by Transaction Count</b>',
            labels={'transaction_count': 'Transactions', 'product_name': 'Product'},
            height=450
        )
        fig_trans.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='x unified'
        )
        st.plotly_chart(fig_trans, use_container_width=True)

    # Detailed table
    with st.expander("📋 View Product Performance Data"):
        display_cols = ['product_name', 'category', 'brand', 'total_quantity_sold', 'total_revenue', 'transaction_count']
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

def show_inventory_analysis(data):
    """Show inventory turnover analysis"""
    st.header("📦 Inventory Turnover Analysis")

    if data['inventory_turnover'].empty:
        st.error("No inventory data available")
        return

    df = data['inventory_turnover'].copy()

    # Movement category filter
    selected_movement = st.selectbox(
        "Select Movement Category",
        ['All'] + list(df['movement_category'].unique()),
        index=0,
        key="movement_category"
    )

    if selected_movement != 'All':
        df = df[df['movement_category'] == selected_movement]

    # Key metrics
    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        total_products = len(df)
        st.metric("📦 Total Products", total_products)

    with col2:
        avg_daily_sales = df['avg_daily_sales'].mean()
        st.metric("📊 Avg Daily Sales", f"{avg_daily_sales:.2f}")

    with col3:
        fast_moving = len(df[df['movement_category'] == 'Fast Moving'])
        st.metric("⚡ Fast Moving", fast_moving)

    with col4:
        slow_moving = len(df[df['movement_category'] == 'Slow Moving'])
        st.metric("🐌 Slow Moving", slow_moving)

    st.markdown("<br>", unsafe_allow_html=True)

    # Movement distribution
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        movement_counts = df['movement_category'].value_counts()
        fig_pie = px.pie(
            values=movement_counts.values,
            names=movement_counts.index,
            title='<b>Product Movement Categories</b>',
            color_discrete_map={
                'Fast Moving': '#2ecc71',
                'Medium Moving': '#f39c12',
                'Slow Moving': '#e74c3c'
            },
            hole=0.4
        )
        fig_pie.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            paper_bgcolor='rgba(245, 247, 250, 0)'
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # Top selling products by daily sales
        top_daily = df.nlargest(10, 'avg_daily_sales')
        fig_bar = px.bar(
            top_daily,
            x='product_name',
            y='avg_daily_sales',
            color='movement_category',
            title='<b>Top 10 Products by Daily Sales</b>',
            labels={'avg_daily_sales': 'Avg Daily Sales', 'product_name': 'Product'},
            height=450
        )
        fig_bar.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='x unified'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Category-wise movement
    col1, col2 = st.columns(2, gap="medium")

    with col1:
        category_movement = df.groupby(['category', 'movement_category']).size().reset_index(name='count')
        fig_stacked = px.bar(
            category_movement,
            x='category',
            y='count',
            color='movement_category',
            title='<b>Product Movement by Category</b>',
            labels={'count': 'Number of Products', 'category': 'Category'},
            height=450
        )
        fig_stacked.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            xaxis_tickangle=-45,
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='x unified'
        )
        st.plotly_chart(fig_stacked, use_container_width=True)

    with col2:
        # Days sold analysis
        fig_hist = px.histogram(
            df,
            x='days_sold',
            color='movement_category',
            title='<b>Distribution of Days Products Were Sold</b>',
            labels={'days_sold': 'Days Sold', 'count': 'Number of Products'},
            height=450,
            nbins=20
        )
        fig_hist.update_layout(
            title_font_size=14,
            title_font_color='#30364f',
            plot_bgcolor='rgba(248, 251, 255, 0.5)',
            paper_bgcolor='rgba(245, 247, 250, 0)',
            hovermode='x unified'
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # Detailed table
    with st.expander("📋 View Inventory Turnover Data"):
        display_cols = ['product_name', 'category', 'total_sold', 'days_sold', 'avg_daily_sales', 'movement_category']
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

def show_monthly_trends(data):
    """Show monthly revenue trends"""
    st.header("📅 Monthly Revenue Trends")

    if data['monthly_revenue'].empty:
        st.error("No monthly revenue data available")
        return

    df = data['monthly_revenue'].copy()

    # Create month names
    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    df['month_name'] = df['month'].map(month_names)
    df['month_year'] = df['month_name'] + ' ' + df['year'].astype(str)

    # Monthly trend chart
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Monthly Revenue Trend', 'Monthly Transaction Count', 'Average Transaction Value', 'Total Units Sold'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )

    # Revenue trend
    fig.add_trace(
        go.Scatter(
            x=df['month_year'],
            y=df['monthly_revenue'],
            mode='lines+markers',
            name='Monthly Revenue',
            line=dict(color='#2ecc71', width=3),
            marker=dict(size=8, color='#2ecc71'),
            hovertemplate='<b>%{x}</b><br>Revenue: ₹%{y:,.0f}<extra></extra>'
        ),
        row=1, col=1
    )

    # Transaction trend
    fig.add_trace(
        go.Scatter(
            x=df['month_year'],
            y=df['transaction_count'],
            mode='lines+markers',
            name='Transactions',
            line=dict(color='#3498db', width=3),
            marker=dict(size=8, color='#3498db'),
            hovertemplate='<b>%{x}</b><br>Transactions: %{y}<extra></extra>'
        ),
        row=1, col=2
    )

    # Average transaction value
    fig.add_trace(
        go.Scatter(
            x=df['month_year'],
            y=df['avg_transaction_value'],
            mode='lines+markers',
            name='Avg Transaction',
            line=dict(color='#e74c3c', width=3),
            marker=dict(size=8, color='#e74c3c'),
            hovertemplate='<b>%{x}</b><br>Avg: ₹%{y:,.0f}<extra></extra>'
        ),
        row=2, col=1
    )

    # Units sold
    fig.add_trace(
        go.Scatter(
            x=df['month_year'],
            y=df['total_units_sold'],
            mode='lines+markers',
            name='Units Sold',
            line=dict(color='#f39c12', width=3),
            marker=dict(size=8, color='#f39c12'),
            hovertemplate='<b>%{x}</b><br>Units: %{y}<extra></extra>'
        ),
        row=2, col=2
    )

    fig.update_layout(
        height=800,
        title_text="<b>Monthly Performance Trends</b>",
        title_font_size=18,
        title_font_color='#30364f',
        showlegend=False,
        plot_bgcolor='rgba(248, 251, 255, 0.5)',
        paper_bgcolor='rgba(245, 247, 250, 0)',
        hovermode='x unified',
        margin=dict(l=80, r=20, t=100, b=80)
    )

    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(186, 202, 225, 0.2)')
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(186, 202, 225, 0.2)')

    st.plotly_chart(fig, use_container_width=True)

    # Monthly comparison table
    with st.expander("📋 View Monthly Data"):
        display_cols = ['year', 'month_name', 'monthly_revenue', 'transaction_count', 'avg_transaction_value', 'total_units_sold']
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

def main():
    """Main dashboard function"""
    st.title("📊 RetailOS KPI Analytics Dashboard")
    st.markdown("---")

    # Load data
    data = load_kpi_data()

    # Check if data is available
    if all(df.empty for df in data.values()):
        st.error("❌ No KPI data found. Please run the KPI generation scripts first.")
        st.info("Run these commands to generate KPI data:")
        st.code("""
python src/analytics/setup_kpi_creator.py
python create_kpi_tables.py
python src/analytics/export_kpi_tables.py
        """)
        return

    # Sidebar navigation
    st.sidebar.title("📊 KPI Analytics")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Select Analysis",
        [
            "🏠 Executive Summary",
            "📈 Daily Revenue Analysis",
            "🏙️ City Sales Performance",
            "🛍️ Product Performance",
            "📦 Inventory Analysis",
            "📅 Monthly Trends"
        ]
    )

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.info(f"💡 Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Display selected page
    if page == "🏠 Executive Summary":
        show_summary_dashboard(data)
    elif page == "📈 Daily Revenue Analysis":
        show_daily_revenue_analysis(data)
    elif page == "🏙️ City Sales Performance":
        show_city_sales_analysis(data)
    elif page == "🛍️ Product Performance":
        show_product_performance(data)
    elif page == "📦 Inventory Analysis":
        show_inventory_analysis(data)
    elif page == "📅 Monthly Trends":
        show_monthly_trends(data)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div class="footer-text">
        <p>🏢 <strong>RetailOS KPI Analytics Dashboard</strong> | Real-time Business Intelligence</p>
        <p>Data Source: KPI Tables | Last Refresh: {}</p>
    </div>
    """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')), unsafe_allow_html=True)

if __name__ == "__main__":
    main()

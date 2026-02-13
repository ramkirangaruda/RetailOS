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

# Custom CSS
st.markdown("""
    <style>
    .main {padding: 0rem 1rem;}
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    h1 {color: #1f77b4; padding-bottom: 20px;}
    h2 {color: #2c3e50; padding-top: 10px;}
    .stTabs [data-baseweb="tab-list"] {gap: 8px;}
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        background-color: #f0f2f6;
        border-radius: 5px;
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

def show_summary_dashboard(data):
    """Show summary dashboard with key metrics"""
    st.header("📊 Executive Summary Dashboard")
    
    if data['summary'].empty:
        st.error("No summary data available")
        return
    
    # Create metric cards
    summary_data = data['summary'].set_index('metric')['value'].to_dict()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h3>💰 Total Revenue</h3>
            <h2 style="color: #2ecc71;">{}</h2>
        </div>
        """.format(format_currency(summary_data.get('Total Revenue', 0))), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h3>🛒 Total Transactions</h3>
            <h2 style="color: #3498db;">{}</h2>
        </div>
        """.format(format_number(summary_data.get('Total Transactions', 0))), unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h3>👥 Total Customers</h3>
            <h2 style="color: #e74c3c;">{}</h2>
        </div>
        """.format(format_number(summary_data.get('Total Customers', 0))), unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
            <h3>🛍️ Total Products</h3>
            <h2 style="color: #f39c12;">{}</h2>
        </div>
        """.format(format_number(summary_data.get('Total Products', 0))), unsafe_allow_html=True)
    
    # Average transaction value
    avg_transaction = summary_data.get('Avg Transaction Value', 0)
    st.markdown("""
    <div class="metric-card">
        <h3>💳 Average Transaction Value</h3>
        <h2 style="color: #9b59b6;">{}</h2>
    </div>
    """.format(format_currency(avg_transaction)), unsafe_allow_html=True)

def show_daily_revenue_analysis(data):
    """Show daily revenue analysis with trends"""
    st.header("📈 Daily Revenue Analysis")
    
    if data['daily_revenue'].empty:
        st.error("No daily revenue data available")
        return
    
    df = data['daily_revenue'].copy()
    df['date'] = pd.to_datetime(df['date'])
    
    # Date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", df['date'].min().date())
    with col2:
        end_date = st.date_input("End Date", df['date'].max().date())
    
    # Filter data
    mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
    filtered_df = df[mask]
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_revenue = filtered_df['daily_revenue'].sum()
        st.metric("Total Revenue", format_currency(total_revenue))
    with col2:
        avg_revenue = filtered_df['daily_revenue'].mean()
        st.metric("Avg Daily Revenue", format_currency(avg_revenue))
    with col3:
        total_transactions = filtered_df['transaction_count'].sum()
        st.metric("Total Transactions", format_number(total_transactions))
    with col4:
        avg_transaction = filtered_df['avg_transaction_value'].mean()
        st.metric("Avg Transaction", format_currency(avg_transaction))
    
    # Time series chart
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Daily Revenue Trend', 'Daily Transaction Count'),
        vertical_spacing=0.1
    )
    
    # Revenue trend
    fig.add_trace(
        go.Scatter(
            x=filtered_df['date'],
            y=filtered_df['daily_revenue'],
            mode='lines+markers',
            name='Daily Revenue',
            line=dict(color='#2ecc71', width=2),
            hovertemplate='Date: %{x}<br>Revenue: ₹%{y:,.0f}<extra></extra>'
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
            line=dict(color='#3498db', width=2),
            hovertemplate='Date: %{x}<br>Transactions: %{y}<extra></extra>'
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        height=600,
        title_text="Daily Revenue and Transaction Trends",
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Day type analysis
    col1, col2 = st.columns(2)
    
    with col1:
        day_type_revenue = filtered_df.groupby('day_type')['daily_revenue'].sum().reset_index()
        fig_pie = px.pie(
            day_type_revenue, 
            values='daily_revenue', 
            names='day_type',
            title='Revenue by Day Type',
            color_discrete_map={'Weekday': '#3498db', 'Weekend': '#e74c3c'}
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
            title='Top 10 Revenue Days',
            labels={'daily_revenue': 'Revenue (₹)', 'date': 'Date'},
            color_discrete_map={'Weekday': '#3498db', 'Weekend': '#e74c3c'}
        )
        fig_bar.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Data table
    with st.expander("📋 View Daily Revenue Data"):
        st.dataframe(filtered_df[['date', 'day_type', 'daily_revenue', 'transaction_count', 'avg_transaction_value']], 
                    use_container_width=True)

def show_city_sales_analysis(data):
    """Show city-wise sales performance"""
    st.header("🏙️ City Sales Performance")
    
    if data['city_sales'].empty:
        st.error("No city sales data available")
        return
    
    df = data['city_sales'].copy()
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_cities = len(df)
        st.metric("Total Cities", total_cities)
    with col2:
        total_revenue = df['total_revenue'].sum()
        st.metric("Total Revenue", format_currency(total_revenue))
    with col3:
        avg_revenue_per_city = df['total_revenue'].mean()
        st.metric("Avg Revenue/City", format_currency(avg_revenue_per_city))
    with col4:
        total_stores = df['active_stores'].sum()
        st.metric("Total Stores", total_stores)
    
    # City revenue chart
    col1, col2 = st.columns(2)
    
    with col1:
        fig_bar = px.bar(
            df.head(10),
            x='city',
            y='total_revenue',
            color='region',
            title='Top 10 Cities by Revenue',
            labels={'total_revenue': 'Revenue (₹)', 'city': 'City'},
            height=400
        )
        fig_bar.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col2:
        # Region performance
        region_revenue = df.groupby('region')['total_revenue'].sum().reset_index()
        fig_pie = px.pie(
            region_revenue,
            values='total_revenue',
            names='region',
            title='Revenue by Region',
            height=400
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Store performance analysis
    col1, col2 = st.columns(2)
    
    with col1:
        fig_scatter = px.scatter(
            df,
            x='active_stores',
            y='total_revenue',
            size='transaction_count',
            color='region',
            hover_name='city',
            title='Store Count vs Revenue',
            labels={
                'active_stores': 'Active Stores',
                'total_revenue': 'Total Revenue (₹)',
                'transaction_count': 'Transactions'
            },
            height=400
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
            title='Top 10 Cities by Avg Transaction Value',
            labels={'avg_transaction_value': 'Avg Transaction (₹)', 'city': 'City'},
            height=400
        )
        fig_atv.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_atv, use_container_width=True)
    
    # Detailed table
    with st.expander("📋 View City Sales Data"):
        st.dataframe(df[['city', 'region', 'active_stores', 'total_revenue', 'transaction_count', 'avg_transaction_value']], 
                    use_container_width=True)

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
        index=0
    )
    
    if selected_category != 'All':
        df = df[df['category'] == selected_category]
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_products = len(df)
        st.metric("Total Products", total_products)
    with col2:
        total_revenue = df['total_revenue'].sum()
        st.metric("Total Revenue", format_currency(total_revenue))
    with col3:
        total_quantity = df['total_quantity_sold'].sum()
        st.metric("Total Units Sold", format_number(total_quantity))
    with col4:
        avg_revenue_per_product = df['total_revenue'].mean()
        st.metric("Avg Revenue/Product", format_currency(avg_revenue_per_product))
    
    # Top products chart
    col1, col2 = st.columns(2)
    
    with col1:
        top_10_products = df.head(10)
        fig_bar = px.bar(
            top_10_products,
            x='product_name',
            y='total_revenue',
            color='category',
            title='Top 10 Products by Revenue',
            labels={'total_revenue': 'Revenue (₹)', 'product_name': 'Product'},
            height=400
        )
        fig_bar.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col2:
        # Category performance
        category_revenue = df.groupby('category')['total_revenue'].sum().reset_index()
        fig_pie = px.pie(
            category_revenue,
            values='total_revenue',
            names='category',
            title='Revenue by Product Category',
            height=400
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Quantity vs Revenue analysis
    col1, col2 = st.columns(2)
    
    with col1:
        fig_scatter = px.scatter(
            df.head(20),
            x='total_quantity_sold',
            y='total_revenue',
            size='transaction_count',
            color='category',
            hover_name='product_name',
            title='Quantity Sold vs Revenue',
            labels={
                'total_quantity_sold': 'Quantity Sold',
                'total_revenue': 'Revenue (₹)',
                'transaction_count': 'Transactions'
            },
            height=400
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
            title='Top 10 Products by Transaction Count',
            labels={'transaction_count': 'Transactions', 'product_name': 'Product'},
            height=400
        )
        fig_trans.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_trans, use_container_width=True)
    
    # Detailed table
    with st.expander("📋 View Product Performance Data"):
        display_cols = ['product_name', 'category', 'brand', 'total_quantity_sold', 'total_revenue', 'transaction_count']
        st.dataframe(df[display_cols], use_container_width=True)

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
        index=0
    )
    
    if selected_movement != 'All':
        df = df[df['movement_category'] == selected_movement]
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_products = len(df)
        st.metric("Total Products", total_products)
    with col2:
        avg_daily_sales = df['avg_daily_sales'].mean()
        st.metric("Avg Daily Sales", f"{avg_daily_sales:.2f}")
    with col3:
        fast_moving = len(df[df['movement_category'] == 'Fast Moving'])
        st.metric("Fast Moving", fast_moving)
    with col4:
        slow_moving = len(df[df['movement_category'] == 'Slow Moving'])
        st.metric("Slow Moving", slow_moving)
    
    # Movement distribution
    col1, col2 = st.columns(2)
    
    with col1:
        movement_counts = df['movement_category'].value_counts()
        fig_pie = px.pie(
            values=movement_counts.values,
            names=movement_counts.index,
            title='Product Movement Categories',
            color_discrete_map={
                'Fast Moving': '#2ecc71',
                'Medium Moving': '#f39c12',
                'Slow Moving': '#e74c3c'
            }
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
            title='Top 10 Products by Daily Sales',
            labels={'avg_daily_sales': 'Avg Daily Sales', 'product_name': 'Product'},
            height=400
        )
        fig_bar.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    # Category-wise movement
    col1, col2 = st.columns(2)
    
    with col1:
        category_movement = df.groupby(['category', 'movement_category']).size().reset_index(name='count')
        fig_stacked = px.bar(
            category_movement,
            x='category',
            y='count',
            color='movement_category',
            title='Product Movement by Category',
            labels={'count': 'Number of Products', 'category': 'Category'},
            height=400
        )
        fig_stacked.update_layout(xaxis_tickangle=45)
        st.plotly_chart(fig_stacked, use_container_width=True)
    
    with col2:
        # Days sold analysis
        fig_hist = px.histogram(
            df,
            x='days_sold',
            color='movement_category',
            title='Distribution of Days Products Were Sold',
            labels={'days_sold': 'Days Sold', 'count': 'Number of Products'},
            height=400,
            nbins=20
        )
        st.plotly_chart(fig_hist, use_container_width=True)
    
    # Detailed table
    with st.expander("📋 View Inventory Turnover Data"):
        display_cols = ['product_name', 'category', 'total_sold', 'days_sold', 'avg_daily_sales', 'movement_category']
        st.dataframe(df[display_cols], use_container_width=True)

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
        subplot_titles=('Monthly Revenue Trend', 'Monthly Transaction Count', 
                       'Average Transaction Value', 'Total Units Sold'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Revenue trend
    fig.add_trace(
        go.Scatter(
            x=df['month_year'],
            y=df['monthly_revenue'],
            mode='lines+markers',
            name='Monthly Revenue',
            line=dict(color='#2ecc71', width=3),
            hovertemplate='Month: %{x}<br>Revenue: ₹%{y:,.0f}<extra></extra>'
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
            hovertemplate='Month: %{x}<br>Transactions: %{y}<extra></extra>'
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
            hovertemplate='Month: %{x}<br>Avg Transaction: ₹%{y:,.0f}<extra></extra>'
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
            hovertemplate='Month: %{x}<br>Units Sold: %{y}<extra></extra>'
        ),
        row=2, col=2
    )
    
    fig.update_layout(
        height=800,
        title_text="Monthly Performance Trends",
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Monthly comparison table
    with st.expander("📋 View Monthly Data"):
        display_cols = ['year', 'month_name', 'monthly_revenue', 'transaction_count', 'avg_transaction_value', 'total_units_sold']
        st.dataframe(df[display_cols], use_container_width=True)

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
    if st.sidebar.button("🔄 Refresh Data"):
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
    <div style='text-align: center; color: #666;'>
        <p>RetailOS KPI Analytics Dashboard | Real-time Business Intelligence</p>
        <p>Data Source: KPI Tables | Last Refresh: {}</p>
    </div>
    """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
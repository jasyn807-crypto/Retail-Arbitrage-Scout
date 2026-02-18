"""
Streamlit Dashboard for Retail Arbitrage Scout
"""
import streamlit as st
import pandas as pd
import requests
import asyncio
from datetime import datetime
from typing import List, Dict, Any
import json

# Page configuration
st.set_page_config(
    page_title="Retail Arbitrage Scout",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .opportunity-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .profit-positive {
        color: #28a745;
        font-weight: bold;
    }
    .profit-negative {
        color: #dc3545;
        font-weight: bold;
    }
    .score-high {
        color: #28a745;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .score-medium {
        color: #ffc107;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .score-low {
        color: #dc3545;
        font-weight: bold;
        font-size: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

# API Configuration
API_BASE_URL = "http://localhost:8000"


def api_get(endpoint: str, params: Dict = None) -> Any:
    """Make GET request to API"""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to API. Please make sure the backend server is running.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ API Error: {str(e)}")
        return None


def api_post(endpoint: str, data: Dict) -> Any:
    """Make POST request to API"""
    try:
        response = requests.post(f"{API_BASE_URL}{endpoint}", json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to API. Please make sure the backend server is running.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"❌ API Error: {str(e)}")
        return None


def render_header():
    """Render application header"""
    st.markdown('<div class="main-header">🛒 Retail Arbitrage Scout</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Find profitable deals at Walmart & Home Depot to resell on Amazon & eBay</div>', unsafe_allow_html=True)


def render_sidebar():
    """Render sidebar controls"""
    with st.sidebar:
        st.header("🔍 Search Settings")
        
        # ZIP Code input
        zip_code = st.text_input(
            "Enter ZIP Code",
            value="",
            max_chars=10,
            placeholder="e.g., 10001",
            help="Enter your local ZIP code to find nearby stores"
        )
        
        # Search radius
        radius = st.slider(
            "Search Radius (miles)",
            min_value=5,
            max_value=50,
            value=20,
            step=5,
            help="How far to search for stores"
        )
        
        # Retailers selection
        st.subheader("Select Retailers")
        col1, col2 = st.columns(2)
        with col1:
            search_walmart = st.checkbox("Walmart", value=True)
        with col2:
            search_homedepot = st.checkbox("Home Depot", value=True)
        
        # Profit filters
        st.subheader("Profit Filters")
        min_profit = st.number_input(
            "Minimum Profit ($)",
            min_value=0.0,
            value=5.0,
            step=1.0,
            help="Minimum dollar profit per item"
        )
        
        min_margin = st.slider(
            "Minimum Margin (%)",
            min_value=0,
            max_value=100,
            value=20,
            step=5,
            help="Minimum profit margin percentage"
        ) / 100
        
        # Search button
        search_disabled = not zip_code or (not search_walmart and not search_homedepot)
        search_button = st.button(
            "🚀 Start Search",
            type="primary",
            disabled=search_disabled,
            use_container_width=True
        )
        
        # API Status
        st.divider()
        st.subheader("📊 System Status")
        
        health = api_get("/health")
        if health:
            st.success("✅ API Connected")
        else:
            st.error("❌ API Disconnected")
        
        return {
            'zip_code': zip_code,
            'radius': radius,
            'retailers': ['walmart'] if search_walmart else [] + ['homedepot'] if search_homedepot else [],
            'min_profit': min_profit,
            'min_margin': min_margin,
            'search_button': search_button
        }


def render_search_progress(search_id: int):
    """Render search progress"""
    st.subheader("⏳ Search Progress")
    
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    
    with progress_placeholder:
        progress_bar = st.progress(0)
    
    # Poll for status
    max_attempts = 60
    for attempt in range(max_attempts):
        status = api_get(f"/search/{search_id}/status")
        
        if not status:
            break
        
        with status_placeholder:
            if status['status'] == 'running':
                st.info(f"🔄 Searching... Found {status['stores_found']} stores, scraped {status['items_scraped']} items, {status['opportunities_found']} opportunities")
            elif status['status'] == 'completed':
                st.success(f"✅ Search completed! Found {status['opportunities_found']} opportunities")
                progress_bar.progress(100)
                return True
            elif status['status'] == 'failed':
                st.error(f"❌ Search failed: {status.get('error_message', 'Unknown error')}")
                return False
        
        # Update progress
        if status['stores_found'] > 0:
            progress = min((attempt / max_attempts) * 100, 95)
            progress_bar.progress(int(progress))
        
        import time
        time.sleep(2)
    
    return False


def render_metrics(opportunities: List[Dict]):
    """Render key metrics"""
    if not opportunities:
        return
    
    st.subheader("📈 Key Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_opps = len(opportunities)
        st.metric("Total Opportunities", total_opps)
    
    with col2:
        avg_profit = sum(opp['opportunity']['net_profit'] for opp in opportunities) / len(opportunities)
        st.metric("Avg Profit", f"${avg_profit:.2f}")
    
    with col3:
        avg_margin = sum(opp['opportunity']['profit_margin'] for opp in opportunities) / len(opportunities)
        st.metric("Avg Margin", f"{avg_margin:.1f}%")
    
    with col4:
        avg_roi = sum(opp['opportunity']['roi_percent'] for opp in opportunities) / len(opportunities)
        st.metric("Avg ROI", f"{avg_roi:.1f}%")


def render_opportunity_card(opp: Dict):
    """Render a single opportunity card"""
    opportunity = opp['opportunity']
    product = opp['product']
    
    # Determine score class
    score = opportunity['opportunity_score']
    if score >= 70:
        score_class = "score-high"
        score_emoji = "🟢"
    elif score >= 40:
        score_class = "score-medium"
        score_emoji = "🟡"
    else:
        score_class = "score-low"
        score_emoji = "🔴"
    
    # Profit class
    profit_class = "profit-positive" if opportunity['net_profit'] > 0 else "profit-negative"
    
    with st.container():
        st.markdown('<div class="opportunity-card">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown(f"**{product['product_name'][:80]}...**")
            st.caption(f"🏪 {product['deal_type']} | 📍 Store: {product.get('store_id', 'N/A')}")
            
            if product['upc']:
                st.caption(f"📋 UPC: {product['upc']}")
            
            if product['product_url']:
                st.markdown(f"[🔗 View Product]({product['product_url']})")
        
        with col2:
            st.markdown(f"**Buy:** ${opportunity['buy_price']:.2f}")
            st.markdown(f"**Sell ({opportunity['best_marketplace']}):** ${opportunity['sell_price']:.2f}")
            st.markdown(f"**Net Profit:** <span class='{profit_class}'>${opportunity['net_profit']:.2f}</span>", unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"**Margin:** {opportunity['profit_margin']:.1f}%")
            st.markdown(f"**ROI:** {opportunity['roi_percent']:.1f}%")
            st.markdown(f"**Score:** <span class='{score_class}'>{score_emoji} {score:.0f}</span>", unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)


def render_opportunities_table(opportunities: List[Dict]):
    """Render opportunities as a data table"""
    if not opportunities:
        return
    
    st.subheader("📋 All Opportunities")
    
    # Prepare data for table
    data = []
    for opp in opportunities:
        opportunity = opp['opportunity']
        product = opp['product']
        
        data.append({
            'Product': product['product_name'][:60] + '...' if len(product['product_name']) > 60 else product['product_name'],
            'Store': product.get('store_id', 'N/A'),
            'Deal Type': product['deal_type'],
            'Buy Price': f"${opportunity['buy_price']:.2f}",
            'Sell Price': f"${opportunity['sell_price']:.2f}",
            'Marketplace': opportunity['best_marketplace'],
            'Net Profit': f"${opportunity['net_profit']:.2f}",
            'Margin': f"{opportunity['profit_margin']:.1f}%",
            'ROI': f"{opportunity['roi_percent']:.1f}%",
            'Score': opportunity['opportunity_score']
        })
    
    df = pd.DataFrame(data)
    
    # Sort by score
    df = df.sort_values('Score', ascending=False)
    
    # Display table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Score': st.column_config.ProgressColumn(
                'Score',
                help='Opportunity score (0-100)',
                format='%d',
                min_value=0,
                max_value=100
            )
        }
    )
    
    # Export option
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"arbitrage_opportunities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )


def render_profit_calculator():
    """Render profit calculator section"""
    st.subheader("🧮 Quick Profit Calculator")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        buy_price = st.number_input("Buy Price ($)", min_value=0.0, value=10.0, step=0.01)
    
    with col2:
        sell_price = st.number_input("Sell Price ($)", min_value=0.0, value=25.0, step=0.01)
    
    with col3:
        marketplace = st.selectbox("Marketplace", ["amazon", "ebay"])
    
    if st.button("Calculate Profit", type="secondary"):
        result = api_post("/calculate-profit", {
            "buy_price": buy_price,
            "sell_price": sell_price,
            "marketplace": marketplace
        })
        
        if result:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Buy Cost", f"${result['total_buy_cost']:.2f}")
            
            with col2:
                st.metric("Total Fees", f"${result['total_fees']:.2f}")
            
            with col3:
                profit_color = "normal" if result['net_profit'] > 0 else "inverse"
                st.metric("Net Profit", f"${result['net_profit']:.2f}", delta_color=profit_color)
            
            with col4:
                st.metric("ROI", f"{result['roi_percent']:.1f}%")
            
            # Recommendation
            if result['is_profitable']:
                st.success(f"✅ {result['recommendation']}")
            else:
                st.warning(f"⚠️ {result['recommendation']}")


def render_inventory_explorer():
    """Render inventory explorer"""
    st.subheader("🔍 Inventory Explorer")
    
    col1, col2 = st.columns(2)
    
    with col1:
        store_filter = st.text_input("Filter by Store ID", placeholder="e.g., 1234")
    
    with col2:
        deal_type = st.selectbox(
            "Deal Type",
            options=["All", "Clearance", "Rollback", "Special Buy"]
        )
    
    if st.button("Load Inventory", type="secondary"):
        params = {}
        if store_filter:
            params['store_id'] = store_filter
        if deal_type != "All":
            params['deal_type'] = deal_type
        
        inventory = api_get("/inventory", params)
        
        if inventory:
            st.write(f"Found {len(inventory)} items")
            
            # Convert to dataframe
            df = pd.DataFrame(inventory)
            st.dataframe(df, use_container_width=True)


def render_price_checker():
    """Render price checker tool"""
    st.subheader("💰 Price Checker")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        upc = st.text_input("Enter UPC", placeholder="e.g., 012345678901")
    
    with col2:
        product_name = st.text_input("Product Name (optional)", placeholder="For fuzzy matching when UPC unavailable")
    
    if st.button("Check Prices", type="secondary"):
        if not upc and not product_name:
            st.warning("Please enter a UPC or product name")
            return
        
        with st.spinner("Checking prices..."):
            params = {}
            if upc:
                params['upc'] = upc
            if product_name:
                params['product_name'] = product_name
            
            prices = api_get("/check-price", params)
            
            if prices:
                for marketplace, listings in prices.items():
                    st.markdown(f"**{marketplace.upper()}**")
                    
                    if listings:
                        for listing in listings[:5]:  # Show top 5
                            st.markdown(
                                f"- **${listing['price']:.2f}** (+${listing['shipping']:.2f} shipping) = "
                                f"**${listing['total']:.2f}** | {listing['condition']} | "
                                f"[{listing['title'][:50]}...]({listing['url']})"
                            )
                    else:
                        st.caption("No listings found")


def main():
    """Main application"""
    render_header()
    
    # Get sidebar inputs
    settings = render_sidebar()
    
    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Opportunities",
        "🧮 Profit Calculator",
        "📦 Inventory",
        "💰 Price Checker"
    ])
    
    with tab1:
        # Handle search
        if settings['search_button'] and settings['zip_code']:
            search_data = {
                'zip_code': settings['zip_code'],
                'radius': settings['radius'],
                'retailers': settings['retailers'],
                'min_profit': settings['min_profit'],
                'min_margin': settings['min_margin'],
                'check_prices': True
            }
            
            with st.spinner("Starting search..."):
                result = api_post("/search", search_data)
                
                if result:
                    search_id = result['search_id']
                    st.success(f"Search started! ID: {search_id}")
                    
                    # Show progress
                    completed = render_search_progress(search_id)
                    
                    if completed:
                        st.rerun()
        
        # Load and display opportunities
        opportunities = api_get("/opportunities", {
            'min_profit': settings['min_profit'],
            'min_margin': settings['min_margin'],
            'limit': 100
        })
        
        if opportunities:
            render_metrics(opportunities)
            
            st.divider()
            
            # Top opportunities
            st.subheader("🏆 Top Opportunities")
            for opp in opportunities[:5]:
                render_opportunity_card(opp)
            
            st.divider()
            
            # Full table
            render_opportunities_table(opportunities)
        else:
            st.info("👋 No opportunities found yet. Start a search to find deals!")
    
    with tab2:
        render_profit_calculator()
    
    with tab3:
        render_inventory_explorer()
    
    with tab4:
        render_price_checker()
    
    # Footer
    st.divider()
    st.caption("Retail Arbitrage Scout v1.0 | Built with FastAPI + Streamlit")


if __name__ == "__main__":
    main()

# 🛒 Retail Arbitrage Scout

A comprehensive web application for finding profitable retail arbitrage opportunities by comparing clearance prices at Walmart and Home Depot against marketplace prices on Amazon and eBay.

## Features

- 🔍 **Store Locator**: Find Walmart and Home Depot stores within a specified radius of any ZIP code
- 🏷️ **Deal Scraper**: Automatically scrape clearance, rollback, and special buy inventory
- 💰 **Price Comparison**: Check current selling prices on Amazon and eBay
- 📊 **Profit Calculator**: Calculate net profit after fees, taxes, and shipping
- 📈 **Opportunity Scoring**: Rank opportunities by profit potential
- 🖥️ **Dashboard**: Clean Streamlit interface for viewing and managing opportunities

## Architecture

```
retail_arbitrage_scout/
├── app.py                 # Streamlit dashboard
├── api.py                 # FastAPI backend
├── scraper_module.py      # Walmart/Home Depot scrapers
├── market_checker.py      # Amazon/eBay price lookup
├── profit_calculator.py   # Profit calculation engine
├── database.py            # SQLite models and operations
├── config.py              # Configuration settings
├── utils.py               # Helper functions
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## Installation

### Prerequisites

- Python 3.9+
- Playwright browsers (installed automatically)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd retail_arbitrage_scout
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
playwright install
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API credentials
```

## Configuration

### eBay API (Required for eBay price lookup)

1. Go to [eBay Developers Program](https://developer.ebay.com/)
2. Create an account and register your application
3. Get your App ID, Cert ID, and Dev ID
4. Add them to your `.env` file:

```env
EBAY_APP_ID=your_app_id
EBAY_CERT_ID=your_cert_id
EBAY_DEV_ID=your_dev_id
EBAY_AUTH_TOKEN=your_auth_token
```

### Optional Settings

Edit `.env` to customize:
- Database URL
- Scraper delays and retry settings
- Profit calculation defaults
- API host and port

## Usage

### Start the Backend API

```bash
python api.py
```

The API will start on `http://localhost:8000`

API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Start the Dashboard

In a new terminal:

```bash
streamlit run app.py
```

The dashboard will open in your browser at `http://localhost:8501`

### Using the Application

1. **Enter your ZIP code** in the sidebar
2. **Select search radius** (5-50 miles)
3. **Choose retailers** to search (Walmart, Home Depot, or both)
4. **Set profit filters** (minimum profit amount and margin)
5. **Click "Start Search"** to begin scraping
6. **Wait for results** - the app will:
   - Find stores near your location
   - Scrape clearance/special buy inventory
   - Check prices on Amazon and eBay
   - Calculate profit opportunities
   - Display ranked results

## API Endpoints

### Search
- `POST /search` - Start a new search
- `GET /search/{search_id}/status` - Check search status

### Stores & Inventory
- `GET /stores` - List stores
- `GET /inventory` - List inventory items

### Opportunities
- `GET /opportunities` - Get high-opportunity items
- `DELETE /opportunities/{id}` - Invalidate an opportunity

### Tools
- `POST /calculate-profit` - Calculate profit for a potential arbitrage
- `GET /check-price` - Check marketplace prices for a UPC

### System
- `GET /health` - Health check

## Profit Calculation Formula

```
Total Buy Cost = Item Price + (Item Price × Sales Tax Rate)

Platform Fees:
  Amazon: ~15% referral fee + FBA fulfillment fee
  eBay: ~13% final value fee + PayPal fees

Net Profit = Selling Price - Total Buy Cost - Platform Fees - Shipping Cost

Profit Margin = (Net Profit / Selling Price) × 100
ROI = (Net Profit / Total Buy Cost) × 100
```

## Scraping Strategy

### Anti-Detection Measures

The scraper implements several techniques to avoid detection:

1. **Stealth Mode**: Uses `playwright-stealth` to mask automation
2. **User-Agent Rotation**: Randomly rotates between common browser UAs
3. **Random Delays**: Adds 2-5 second delays between requests
4. **Human-like Behavior**: Simulates scrolling and mouse movements
5. **Viewport Randomization**: Uses realistic screen resolutions

### Rate Limiting

- Default: 1 request per second to marketplaces
- Adjustable via `MIN_DELAY` and `MAX_DELAY` in config

### CAPTCHA Handling

The scraper detects CAPTCHA pages and:
- Logs the detection
- Skips the current request
- Continues with next item

## Database Schema

### Tables

- **stores**: Store location information
- **inventory_items**: Scraped products from stores
- **price_comparisons**: Marketplace price data
- **opportunities**: Calculated arbitrage opportunities
- **search_history**: Search job history

### Relationships

```
Store 1--* InventoryItem 1--* PriceComparison
InventoryItem 1--1 Opportunity
```

## Troubleshooting

### Common Issues

**Playwright browser not found**
```bash
playwright install chromium
```

**eBay API errors**
- Verify your API credentials in `.env`
- Check that your eBay developer account is active
- Ensure you have the correct API scopes

**CAPTCHA blocking**
- Increase delays in `config.py`
- Use residential proxies (advanced)
- Run during off-peak hours

**No opportunities found**
- Expand search radius
- Lower profit thresholds
- Try different ZIP codes
- Check that stores have clearance inventory

### Logs

The application logs to console. To enable SQL query logging:

```env
ECHO_SQL=True
```

## Advanced Usage

### Custom Scraping

```python
from scraper_module import WalmartScraper, HomeDepotScraper

async def custom_scrape():
    async with WalmartScraper() as scraper:
        items = await scraper.search_clearance_by_store("1234", "10001")
        for item in items:
            print(f"{item.product_name}: ${item.current_price}")
```

### Batch Price Checking

```python
from market_checker import check_marketplace_prices

prices = await check_marketplace_prices(
    upc="012345678901",
    product_name="Product Name"
)
```

### Custom Profit Analysis

```python
from profit_calculator import ProfitCalculator

calc = ProfitCalculator(
    sales_tax_rate=0.0875,  # Your local tax rate
    shipping_cost=6.50       # Your shipping cost
)

analysis = calc.calculate_profit(
    buy_price=10.00,
    sell_price=29.99,
    marketplace='amazon',
    category='Electronics'
)

print(f"Net Profit: ${analysis.net_profit}")
print(f"ROI: {analysis.roi_percent}%")
```

## Legal & Ethical Considerations

⚠️ **Important Notice**

This tool is for educational and research purposes. Before using:

1. **Review Terms of Service**: Check Walmart, Home Depot, Amazon, and eBay's ToS
2. **Respect Robots.txt**: Don't overwhelm servers with requests
3. **Use Responsibly**: Don't abuse scraping capabilities
4. **Data Privacy**: Handle any personal data according to applicable laws
5. **Commercial Use**: Verify legality in your jurisdiction

The developers assume no liability for misuse of this software.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Roadmap

- [ ] Add Target scraper
- [ ] Add Lowe's scraper
- [ ] Implement proxy rotation
- [ ] Add email alerts for high-opportunity items
- [ ] Create mobile app
- [ ] Add historical price tracking
- [ ] Implement machine learning for opportunity prediction

## Support

For issues and questions:
- Open a GitHub issue
- Check existing documentation
- Review troubleshooting section

---

**Disclaimer**: This is a research tool. Use at your own risk. Always verify prices and availability before making purchasing decisions.

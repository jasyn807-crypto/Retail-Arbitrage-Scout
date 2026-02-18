"""
Configuration settings for Retail Arbitrage Scout
"""
import os
from dataclasses import dataclass
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ScraperConfig:
    """Scraper configuration settings"""
    # Request delays (seconds)
    MIN_DELAY: float = 2.0
    MAX_DELAY: float = 5.0
    
    # Retry settings
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    
    # Browser settings
    HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000  # 30 seconds
    
    # User agents rotation
    USER_AGENTS: List[str] = None
    
    def __post_init__(self):
        if self.USER_AGENTS is None:
            self.USER_AGENTS = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
            ]


@dataclass
class StoreConfig:
    """Store-specific configuration"""
    # Search radius in miles
    DEFAULT_RADIUS: int = 20
    MAX_RADIUS: int = 50
    
    # Walmart settings
    WALMART_CLEARANCE_URL: str = "https://www.walmart.com/search?q=clearance&affinityOverride=store_led"
    WALMART_SPECIAL_URL: str = "https://www.walmart.com/search?q=special+buy&affinityOverride=store_led"
    
    # Home Depot settings
    HOMEDEPOT_CLEARANCE_URL: str = "https://www.homedepot.com/b/Clearance"
    HOMEDEPOT_SPECIAL_URL: str = "https://www.homedepot.com/c/Special_Buy"
    
    # Store IDs cache duration (hours)
    STORE_CACHE_HOURS: int = 24


@dataclass
class MarketplaceConfig:
    """Marketplace API configuration"""
    # eBay API (more friendly than Amazon)
    EBAY_APP_ID: str = os.getenv("EBAY_APP_ID", "")
    EBAY_CERT_ID: str = os.getenv("EBAY_CERT_ID", "")
    EBAY_DEV_ID: str = os.getenv("EBAY_DEV_ID", "")
    EBAY_AUTH_TOKEN: str = os.getenv("EBAY_AUTH_TOKEN", "")
    EBAY_API_ENDPOINT: str = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    
    # Amazon (using scraping approach due to API restrictions)
    AMAZON_SEARCH_URL: str = "https://www.amazon.com/s"
    AMAZON_PRODUCT_URL: str = "https://www.amazon.com/dp"
    
    # Rate limiting
    REQUESTS_PER_SECOND: float = 1.0


@dataclass
class ProfitConfig:
    """Profit calculation configuration"""
    # Platform fees (as decimal)
    AMAZON_FEE_PERCENT: float = 0.15  # 15%
    EBAY_FEE_PERCENT: float = 0.13    # 13% (approximate)
    PAYPAL_FEE_PERCENT: float = 0.029  # 2.9%
    PAYPAL_FEE_FIXED: float = 0.30     # $0.30 fixed
    
    # Default values
    DEFAULT_SALES_TAX: float = 0.08    # 8%
    DEFAULT_SHIPPING_COST: float = 5.00  # $5.00
    
    # Minimum profit thresholds
    MIN_PROFIT_AMOUNT: float = 5.00     # $5.00 minimum
    MIN_PROFIT_MARGIN: float = 0.20     # 20% minimum margin


@dataclass
class DatabaseConfig:
    """Database configuration"""
    DB_URL: str = os.getenv("DATABASE_URL", "sqlite:///retail_arbitrage.db")
    ECHO_SQL: bool = os.getenv("ECHO_SQL", "False").lower() == "true"


# Global configuration instances
SCRAPER_CONFIG = ScraperConfig()
STORE_CONFIG = StoreConfig()
MARKETPLACE_CONFIG = MarketplaceConfig()
PROFIT_CONFIG = ProfitConfig()
DB_CONFIG = DatabaseConfig()

# UPC/GTIN regex patterns
UPC_PATTERNS = [
    r'"upc":"(\d{12})"',
    r'"gtin":"(\d{14})"',
    r'"gtin14":"(\d{14})"',
    r'"productId":"(\d{12})"',
    r'data-upc="(\d{12})"',
    r'"barcode":"(\d{12,14})"',
    r'"ean":"(\d{13})"',
    r'"mpn":"([A-Z0-9-]+)"',
]

# Product category margins (for more accurate calculations)
CATEGORY_MARGINS: Dict[str, float] = {
    "Electronics": 0.15,
    "Home & Garden": 0.15,
    "Toys": 0.15,
    "Clothing": 0.17,
    "Books": 0.15,
    "Other": 0.15,
}

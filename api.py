"""
FastAPI backend for Retail Arbitrage Scout
"""
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from database import (
    get_db_session, StoreRepository, InventoryRepository,
    PriceComparisonRepository, OpportunityRepository, SearchHistoryRepository,
    Store, InventoryItem, PriceComparison, Opportunity, SearchHistory
)
from scraper_module import (
    find_stores, scrape_walmart_store, scrape_homedepot_store,
    ScrapedItem, StoreLocator
)
from market_checker import (
    check_marketplace_prices, get_best_selling_price,
    MarketplaceListing, PriceComparisonEngine
)
from profit_calculator import (
    ProfitCalculator, ProfitAnalysis, calculate_arbitrage_profit
)
from config import STORE_CONFIG, PROFIT_CONFIG


# Pydantic models for API
class StoreResponse(BaseModel):
    store_id: str
    retailer: str
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: Optional[str]
    distance_miles: Optional[float]


class InventoryItemResponse(BaseModel):
    product_id: str
    product_name: str
    current_price: float
    original_price: Optional[float]
    discount_percent: Optional[float]
    upc: Optional[str]
    stock_status: str
    deal_type: str
    product_url: Optional[str]
    image_url: Optional[str]
    brand: Optional[str]
    category: Optional[str]


class PriceComparisonResponse(BaseModel):
    marketplace: str
    listing_title: Optional[str]
    price: float
    shipping_cost: float
    total_price: float
    condition: str
    listing_url: Optional[str]
    seller_rating: Optional[float]


class ProfitAnalysisResponse(BaseModel):
    buy_price: float
    sell_price: float
    marketplace: str
    total_buy_cost: float
    total_fees: float
    estimated_shipping: float
    net_profit: float
    profit_margin: float
    roi_percent: float
    is_profitable: bool
    opportunity_score: float
    recommendation: str


class OpportunityResponse(BaseModel):
    id: int
    inventory_item: InventoryItemResponse
    best_marketplace: str
    buy_price: float
    sell_price: float
    net_profit: float
    profit_margin: float
    roi_percent: float
    opportunity_score: float
    recommendation: str


class SearchRequest(BaseModel):
    zip_code: str = Field(..., min_length=5, max_length=10)
    radius: int = Field(default=20, ge=5, le=50)
    retailers: List[str] = Field(default=["walmart", "homedepot"])
    check_prices: bool = True
    min_profit: float = Field(default=5.0, ge=0)
    min_margin: float = Field(default=0.20, ge=0, le=1)


class SearchStatusResponse(BaseModel):
    search_id: int
    status: str
    zip_code: str
    radius: int
    stores_found: int
    items_scraped: int
    opportunities_found: int
    duration_seconds: Optional[int]
    error_message: Optional[str]


# Global state for background tasks
active_searches: Dict[int, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print("Starting Retail Arbitrage Scout API...")
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="Retail Arbitrage Scout API",
    description="API for finding retail arbitrage opportunities",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helper functions
async def process_store_inventory(
    store: Dict[str, Any],
    search_id: int,
    min_profit: float,
    min_margin: float
):
    """Process inventory for a single store"""
    store_id = store['store_id']
    retailer = store['retailer']
    zip_code = store['zip_code']
    
    try:
        # Scrape store inventory
        if retailer == 'walmart':
            items = await scrape_walmart_store(store_id, zip_code)
        elif retailer == 'homedepot':
            items = await scrape_homedepot_store(store_id, zip_code)
        else:
            return
        
        # Save store to database
        with get_db_session() as session:
            StoreRepository.create_or_update(session, store)
        
        # Process each item
        for item in items:
            try:
                # Save inventory item
                with get_db_session() as session:
                    item_data = {
                        'store_id': store_id,
                        'product_id': item.product_id,
                        'product_name': item.product_name,
                        'current_price': item.current_price,
                        'original_price': item.original_price,
                        'discount_percent': item.discount_percent,
                        'upc': item.upc,
                        'stock_status': item.stock_status,
                        'deal_type': item.deal_type,
                        'product_url': item.product_url,
                        'image_url': item.image_url,
                        'brand': item.brand,
                        'category': item.category,
                        'raw_data': item.raw_data
                    }
                    db_item = InventoryRepository.create_or_update(session, item_data)
                    session.flush()
                    
                    # Check marketplace prices if UPC available
                    if item.upc:
                        await check_and_save_prices(session, db_item.id, item.upc, item.product_name)
                    
                    # Calculate profit opportunity
                    await calculate_and_save_opportunity(
                        session, db_item.id, item.current_price, 
                        min_profit, min_margin
                    )
                    
                    # Update search progress
                    active_searches[search_id]['items_scraped'] += 1
                    
            except Exception as e:
                print(f"Error processing item {item.product_id}: {e}")
                continue
                
    except Exception as e:
        print(f"Error processing store {store_id}: {e}")


async def check_and_save_prices(
    session, 
    inventory_item_id: int, 
    upc: str,
    product_name: str
):
    """Check marketplace prices and save to database"""
    try:
        prices = await check_marketplace_prices(upc, product_name)
        
        for marketplace, listings in prices.items():
            for listing in listings[:3]:  # Save top 3 listings per marketplace
                try:
                    comparison_data = {
                        'inventory_item_id': inventory_item_id,
                        'marketplace': marketplace,
                        'listing_price': listing.price,
                        'shipping_cost': listing.shipping_cost,
                        'total_price': listing.total_price,
                        'listing_url': listing.listing_url,
                        'listing_title': listing.listing_title,
                        'seller_rating': listing.seller_rating,
                        'condition': listing.condition,
                        'is_buy_box': listing.is_buy_box
                    }
                    PriceComparisonRepository.create_or_update(session, comparison_data)
                except Exception as e:
                    print(f"Error saving price comparison: {e}")
                    
    except Exception as e:
        print(f"Error checking prices for {upc}: {e}")


async def calculate_and_save_opportunity(
    session,
    inventory_item_id: int,
    buy_price: float,
    min_profit: float,
    min_margin: float
):
    """Calculate profit opportunity and save if meets criteria"""
    try:
        # Get best price comparison
        best_comparison = PriceComparisonRepository.get_best_price(session, inventory_item_id)
        
        if not best_comparison:
            return
        
        # Calculate profit
        calculator = ProfitCalculator(min_profit_amount=min_profit, min_profit_margin=min_margin)
        analysis = calculator.calculate_profit(
            buy_price=buy_price,
            sell_price=best_comparison.total_price,
            marketplace=best_comparison.marketplace
        )
        
        # Save opportunity if profitable
        if analysis.is_profitable:
            opp_data = {
                'inventory_item_id': inventory_item_id,
                'best_marketplace': best_comparison.marketplace,
                'buy_price': buy_price,
                'sell_price': best_comparison.total_price,
                'estimated_fees': analysis.total_fees,
                'net_profit': analysis.net_profit,
                'profit_margin': analysis.profit_margin,
                'roi_percent': analysis.roi_percent,
                'opportunity_score': analysis.opportunity_score,
                'is_valid': True
            }
            OpportunityRepository.create_or_update(session, opp_data)
            
    except Exception as e:
        print(f"Error calculating opportunity: {e}")


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Retail Arbitrage Scout API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post("/search", response_model=SearchStatusResponse)
async def start_search(search_request: SearchRequest, background_tasks: BackgroundTasks):
    """Start a new search for arbitrage opportunities"""
    
    # Create search history record
    with get_db_session() as session:
        history_data = {
            'zip_code': search_request.zip_code,
            'radius_miles': search_request.radius,
            'retailers_searched': str(search_request.retailers),
            'status': 'pending'
        }
        history = SearchHistoryRepository.create(session, history_data)
        search_id = history.id
    
    # Initialize search state
    active_searches[search_id] = {
        'status': 'running',
        'stores_found': 0,
        'items_scraped': 0,
        'opportunities_found': 0,
        'error': None
    }
    
    # Start background search
    background_tasks.add_task(
        run_full_search,
        search_id,
        search_request
    )
    
    return SearchStatusResponse(
        search_id=search_id,
        status='started',
        zip_code=search_request.zip_code,
        radius=search_request.radius,
        stores_found=0,
        items_scraped=0,
        opportunities_found=0,
        duration_seconds=None,
        error_message=None
    )


async def run_full_search(search_id: int, request: SearchRequest):
    """Run full search in background"""
    try:
        active_searches[search_id]['status'] = 'running'
        
        # Update status to running
        with get_db_session() as session:
            SearchHistoryRepository.update_status(session, search_id, 'running')
        
        # Find stores
        all_stores = await find_stores(request.zip_code, request.radius)
        
        stores_to_process = []
        for retailer in request.retailers:
            if retailer in all_stores:
                stores_to_process.extend(all_stores[retailer])
        
        active_searches[search_id]['stores_found'] = len(stores_to_process)
        
        # Process each store
        for store in stores_to_process:
            await process_store_inventory(
                store, search_id, request.min_profit, request.min_margin
            )
        
        # Count opportunities
        with get_db_session() as session:
            opportunities = OpportunityRepository.get_high_opportunities(
                session, min_profit=request.min_profit
            )
            active_searches[search_id]['opportunities_found'] = len(opportunities)
        
        # Mark as completed
        active_searches[search_id]['status'] = 'completed'
        
        with get_db_session() as session:
            SearchHistoryRepository.update_status(
                session, search_id, 'completed',
                results={
                    'stores_found': active_searches[search_id]['stores_found'],
                    'items_scraped': active_searches[search_id]['items_scraped'],
                    'opportunities_found': active_searches[search_id]['opportunities_found']
                }
            )
        
    except Exception as e:
        active_searches[search_id]['status'] = 'failed'
        active_searches[search_id]['error'] = str(e)
        
        with get_db_session() as session:
            SearchHistoryRepository.update_status(
                session, search_id, 'failed', error_message=str(e)
            )


@app.get("/search/{search_id}/status", response_model=SearchStatusResponse)
async def get_search_status(search_id: int):
    """Get status of a search"""
    
    # Check active searches first
    if search_id in active_searches:
        state = active_searches[search_id]
        return SearchStatusResponse(
            search_id=search_id,
            status=state['status'],
            zip_code="",
            radius=0,
            stores_found=state['stores_found'],
            items_scraped=state['items_scraped'],
            opportunities_found=state['opportunities_found'],
            duration_seconds=None,
            error_message=state.get('error')
        )
    
    # Check database
    with get_db_session() as session:
        history = session.query(SearchHistory).get(search_id)
        if not history:
            raise HTTPException(status_code=404, detail="Search not found")
        
        return SearchStatusResponse(
            search_id=search_id,
            status=history.status,
            zip_code=history.zip_code,
            radius=history.radius_miles,
            stores_found=history.stores_found,
            items_scraped=history.items_scraped,
            opportunities_found=history.opportunities_found,
            duration_seconds=history.duration_seconds,
            error_message=history.error_message
        )


@app.get("/stores", response_model=List[StoreResponse])
async def get_stores(
    zip_code: Optional[str] = None,
    retailer: Optional[str] = None
):
    """Get stores, optionally filtered by ZIP code and/or retailer"""
    
    with get_db_session() as session:
        if zip_code and retailer:
            stores = StoreRepository.get_by_zip(session, retailer, zip_code)
        elif retailer:
            stores = StoreRepository.get_by_retailer(session, retailer)
        else:
            stores = session.query(Store).all()
        
        return [
            StoreResponse(
                store_id=s.store_id,
                retailer=s.retailer,
                name=s.name,
                address=s.address,
                city=s.city,
                state=s.state,
                zip_code=s.zip_code,
                phone=s.phone,
                distance_miles=s.distance_miles
            )
            for s in stores
        ]


@app.get("/inventory", response_model=List[InventoryItemResponse])
async def get_inventory(
    store_id: Optional[str] = None,
    deal_type: Optional[str] = None,
    min_discount: Optional[float] = None
):
    """Get inventory items with optional filters"""
    
    with get_db_session() as session:
        if store_id:
            items = InventoryRepository.get_by_store(session, store_id, deal_type)
        elif min_discount:
            items = InventoryRepository.get_deals(session, min_discount)
        else:
            items = session.query(InventoryItem).filter_by(is_active=True).all()
        
        return [
            InventoryItemResponse(
                product_id=item.product_id,
                product_name=item.product_name,
                current_price=item.current_price,
                original_price=item.original_price,
                discount_percent=item.discount_percent,
                upc=item.upc,
                stock_status=item.stock_status,
                deal_type=item.deal_type,
                product_url=item.product_url,
                image_url=item.image_url,
                brand=item.brand,
                category=item.category
            )
            for item in items
        ]


@app.get("/opportunities", response_model=List[Dict[str, Any]])
async def get_opportunities(
    min_profit: Optional[float] = Query(default=5.0, ge=0),
    min_margin: Optional[float] = Query(default=0.20, ge=0, le=1),
    limit: int = Query(default=100, le=500)
):
    """Get high-opportunity arbitrage items"""
    
    with get_db_session() as session:
        opportunities = OpportunityRepository.get_high_opportunities(
            session, min_profit=min_profit, min_margin=min_margin, limit=limit
        )
        
        results = []
        for opp in opportunities:
            item = session.query(InventoryItem).get(opp.inventory_item_id)
            if item:
                results.append({
                    'opportunity': {
                        'id': opp.id,
                        'best_marketplace': opp.best_marketplace,
                        'buy_price': opp.buy_price,
                        'sell_price': opp.sell_price,
                        'net_profit': opp.net_profit,
                        'profit_margin': opp.profit_margin,
                        'roi_percent': opp.roi_percent,
                        'opportunity_score': opp.opportunity_score
                    },
                    'product': InventoryItemResponse(
                        product_id=item.product_id,
                        product_name=item.product_name,
                        current_price=item.current_price,
                        original_price=item.original_price,
                        discount_percent=item.discount_percent,
                        upc=item.upc,
                        stock_status=item.stock_status,
                        deal_type=item.deal_type,
                        product_url=item.product_url,
                        image_url=item.image_url,
                        brand=item.brand,
                        category=item.category
                    )
                })
        
        return results


@app.post("/calculate-profit", response_model=ProfitAnalysisResponse)
async def calculate_profit(
    buy_price: float,
    sell_price: float,
    marketplace: str = "amazon",
    category: str = "Other"
):
    """Calculate profit for a potential arbitrage"""
    
    calculator = ProfitCalculator()
    analysis = calculator.calculate_profit(
        buy_price=buy_price,
        sell_price=sell_price,
        marketplace=marketplace,
        category=category
    )
    
    return ProfitAnalysisResponse(
        buy_price=analysis.buy_price,
        sell_price=analysis.sell_price,
        marketplace=analysis.marketplace,
        total_buy_cost=analysis.total_buy_cost,
        total_fees=analysis.total_fees,
        estimated_shipping=analysis.estimated_shipping,
        net_profit=analysis.net_profit,
        profit_margin=analysis.profit_margin,
        roi_percent=analysis.roi_percent,
        is_profitable=analysis.is_profitable,
        opportunity_score=analysis.opportunity_score,
        recommendation=analysis.recommendation
    )


@app.get("/check-price")
async def check_price(upc: str, product_name: Optional[str] = None):
    """Check current prices on marketplaces"""
    
    prices = await check_marketplace_prices(upc, product_name)
    
    return {
        marketplace: [
            {
                'title': listing.listing_title,
                'price': listing.price,
                'shipping': listing.shipping_cost,
                'total': listing.total_price,
                'url': listing.listing_url,
                'condition': listing.condition
            }
            for listing in listings
        ]
        for marketplace, listings in prices.items()
    }


@app.delete("/opportunities/{opportunity_id}")
async def delete_opportunity(opportunity_id: int):
    """Invalidate an opportunity"""
    
    with get_db_session() as session:
        opp = session.query(Opportunity).get(opportunity_id)
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        opp.is_valid = False
        return {"message": "Opportunity invalidated"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


# Run the application
if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

"""
Database models and operations for Retail Arbitrage Scout
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from contextlib import contextmanager
import json

from config import DB_CONFIG

Base = declarative_base()


class Store(Base):
    """Store location information"""
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True)
    store_id = Column(String(50), unique=True, nullable=False, index=True)
    retailer = Column(String(50), nullable=False, index=True)  # 'walmart' or 'homedepot'
    name = Column(String(200))
    address = Column(String(500))
    city = Column(String(100))
    state = Column(String(10))
    zip_code = Column(String(10), index=True)
    phone = Column(String(20))
    latitude = Column(Float)
    longitude = Column(Float)
    distance_miles = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    inventory_items = relationship("InventoryItem", back_populates="store", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_retailer_zip', 'retailer', 'zip_code'),
    )


class InventoryItem(Base):
    """Scraped inventory items from stores"""
    __tablename__ = "inventory_items"
    
    id = Column(Integer, primary_key=True)
    store_id = Column(String(50), ForeignKey("stores.store_id"), nullable=False, index=True)
    product_id = Column(String(100), nullable=False, index=True)
    product_name = Column(Text, nullable=False)
    product_url = Column(Text)
    image_url = Column(Text)
    
    # Pricing
    current_price = Column(Float, nullable=False)
    original_price = Column(Float)
    discount_percent = Column(Float)
    
    # Product details
    upc = Column(String(14), index=True)
    brand = Column(String(100))
    category = Column(String(100))
    description = Column(Text)
    
    # Store info
    stock_status = Column(String(50))  # 'In Stock', 'Limited', 'Out of Stock'
    quantity_available = Column(Integer)
    
    # Deal type
    deal_type = Column(String(50))  # 'Clearance', 'Special Buy', 'Rollback'
    
    # Metadata
    scraped_at = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    raw_data = Column(Text)  # JSON string of raw scraped data
    
    # Relationships
    store = relationship("Store", back_populates="inventory_items")
    price_comparisons = relationship("PriceComparison", back_populates="inventory_item", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_upc_deal', 'upc', 'deal_type'),
        Index('idx_store_scraped', 'store_id', 'scraped_at'),
    )


class PriceComparison(Base):
    """Price comparisons from marketplaces"""
    __tablename__ = "price_comparisons"
    
    id = Column(Integer, primary_key=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False, index=True)
    marketplace = Column(String(50), nullable=False, index=True)  # 'amazon', 'ebay'
    
    # Price data
    listing_price = Column(Float)
    shipping_cost = Column(Float, default=0.0)
    total_price = Column(Float)
    
    # Listing details
    listing_url = Column(Text)
    listing_title = Column(Text)
    seller_rating = Column(Float)
    condition = Column(String(50))
    
    # Calculated fields
    estimated_fees = Column(Float)
    net_profit = Column(Float)
    profit_margin = Column(Float)
    roi_percent = Column(Float)
    
    # Metadata
    checked_at = Column(DateTime, default=datetime.utcnow)
    is_buy_box = Column(Boolean, default=False)
    
    # Relationship
    inventory_item = relationship("InventoryItem", back_populates="price_comparisons")
    
    __table_args__ = (
        Index('idx_marketplace_profit', 'marketplace', 'net_profit'),
    )


class Opportunity(Base):
    """High-opportunity items calculated from comparisons"""
    __tablename__ = "opportunities"
    
    id = Column(Integer, primary_key=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False, unique=True)
    
    # Profit metrics
    best_marketplace = Column(String(50))
    buy_price = Column(Float, nullable=False)
    sell_price = Column(Float, nullable=False)
    estimated_fees = Column(Float, nullable=False)
    net_profit = Column(Float, nullable=False)
    profit_margin = Column(Float, nullable=False)
    roi_percent = Column(Float, nullable=False)
    
    # Ranking
    opportunity_score = Column(Float, index=True)  # Composite score for ranking
    
    # Status
    is_valid = Column(Boolean, default=True)
    expired_at = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text)


class SearchHistory(Base):
    """User search history"""
    __tablename__ = "search_history"
    
    id = Column(Integer, primary_key=True)
    zip_code = Column(String(10), nullable=False, index=True)
    radius_miles = Column(Integer, default=20)
    retailers_searched = Column(Text)  # JSON list
    
    # Results summary
    stores_found = Column(Integer, default=0)
    items_scraped = Column(Integer, default=0)
    opportunities_found = Column(Integer, default=0)
    
    # Timing
    search_started = Column(DateTime, default=datetime.utcnow)
    search_completed = Column(DateTime)
    duration_seconds = Column(Integer)
    
    # Status
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    error_message = Column(Text)


# Database engine and session
engine = create_engine(DB_CONFIG.DB_URL, echo=DB_CONFIG.ECHO_SQL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session() -> Session:
    """Get database session with automatic cleanup"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables (use with caution)"""
    Base.metadata.drop_all(bind=engine)


# CRUD Operations
class StoreRepository:
    """Store data access"""
    
    @staticmethod
    def create_or_update(session: Session, store_data: Dict[str, Any]) -> Store:
        """Create or update store record"""
        store = session.query(Store).filter_by(store_id=store_data['store_id']).first()
        
        if store:
            for key, value in store_data.items():
                setattr(store, key, value)
            store.last_updated = datetime.utcnow()
        else:
            store = Store(**store_data)
            session.add(store)
        
        return store
    
    @staticmethod
    def get_by_zip(session: Session, retailer: str, zip_code: str, radius: float = None) -> List[Store]:
        """Get stores by ZIP code and retailer"""
        query = session.query(Store).filter_by(retailer=retailer, zip_code=zip_code)
        if radius:
            query = query.filter(Store.distance_miles <= radius)
        return query.all()
    
    @staticmethod
    def get_by_retailer(session: Session, retailer: str) -> List[Store]:
        """Get all stores for a retailer"""
        return session.query(Store).filter_by(retailer=retailer).all()


class InventoryRepository:
    """Inventory data access"""
    
    @staticmethod
    def create_or_update(session: Session, item_data: Dict[str, Any]) -> InventoryItem:
        """Create or update inventory item"""
        item = session.query(InventoryItem).filter_by(
            store_id=item_data['store_id'],
            product_id=item_data['product_id']
        ).first()
        
        if item:
            for key, value in item_data.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            item.last_checked = datetime.utcnow()
        else:
            item = InventoryItem(**item_data)
            if 'raw_data' in item_data and isinstance(item_data['raw_data'], dict):
                item.raw_data = json.dumps(item_data['raw_data'])
            session.add(item)
        
        return item
    
    @staticmethod
    def get_by_upc(session: Session, upc: str) -> List[InventoryItem]:
        """Get items by UPC"""
        return session.query(InventoryItem).filter_by(upc=upc, is_active=True).all()
    
    @staticmethod
    def get_by_store(session: Session, store_id: str, deal_type: str = None) -> List[InventoryItem]:
        """Get items by store"""
        query = session.query(InventoryItem).filter_by(store_id=store_id, is_active=True)
        if deal_type:
            query = query.filter_by(deal_type=deal_type)
        return query.order_by(InventoryItem.discount_percent.desc()).all()
    
    @staticmethod
    def get_deals(session: Session, min_discount: float = 20.0) -> List[InventoryItem]:
        """Get all deals with minimum discount"""
        return session.query(InventoryItem).filter(
            InventoryItem.discount_percent >= min_discount,
            InventoryItem.is_active == True
        ).order_by(InventoryItem.discount_percent.desc()).all()


class PriceComparisonRepository:
    """Price comparison data access"""
    
    @staticmethod
    def create_or_update(session: Session, comparison_data: Dict[str, Any]) -> PriceComparison:
        """Create or update price comparison"""
        comparison = session.query(PriceComparison).filter_by(
            inventory_item_id=comparison_data['inventory_item_id'],
            marketplace=comparison_data['marketplace']
        ).first()
        
        if comparison:
            for key, value in comparison_data.items():
                if hasattr(comparison, key):
                    setattr(comparison, key, value)
            comparison.checked_at = datetime.utcnow()
        else:
            comparison = PriceComparison(**comparison_data)
            session.add(comparison)
        
        return comparison
    
    @staticmethod
    def get_best_price(session: Session, inventory_item_id: int) -> Optional[PriceComparison]:
        """Get best price comparison for an item"""
        return session.query(PriceComparison).filter_by(
            inventory_item_id=inventory_item_id
        ).order_by(PriceComparison.net_profit.desc()).first()


class OpportunityRepository:
    """Opportunity data access"""
    
    @staticmethod
    def create_or_update(session: Session, opp_data: Dict[str, Any]) -> Opportunity:
        """Create or update opportunity"""
        opp = session.query(Opportunity).filter_by(
            inventory_item_id=opp_data['inventory_item_id']
        ).first()
        
        if opp:
            for key, value in opp_data.items():
                if hasattr(opp, key):
                    setattr(opp, key, value)
            opp.last_updated = datetime.utcnow()
        else:
            opp = Opportunity(**opp_data)
            session.add(opp)
        
        return opp
    
    @staticmethod
    def get_high_opportunities(
        session: Session, 
        min_profit: float = None, 
        min_margin: float = None,
        limit: int = 100
    ) -> List[Opportunity]:
        """Get high opportunity items"""
        query = session.query(Opportunity).filter_by(is_valid=True)
        
        if min_profit:
            query = query.filter(Opportunity.net_profit >= min_profit)
        if min_margin:
            query = query.filter(Opportunity.profit_margin >= min_margin)
        
        return query.order_by(Opportunity.opportunity_score.desc()).limit(limit).all()
    
    @staticmethod
    def invalidate_old(session: Session, hours: int = 24):
        """Invalidate opportunities older than specified hours"""
        cutoff = datetime.utcnow() - __import__('datetime').timedelta(hours=hours)
        session.query(Opportunity).filter(
            Opportunity.created_at < cutoff,
            Opportunity.is_valid == True
        ).update({'is_valid': False, 'expired_at': datetime.utcnow()})


class SearchHistoryRepository:
    """Search history data access"""
    
    @staticmethod
    def create(session: Session, search_data: Dict[str, Any]) -> SearchHistory:
        """Create search history record"""
        history = SearchHistory(**search_data)
        session.add(history)
        session.flush()  # Get ID without committing
        return history
    
    @staticmethod
    def update_status(
        session: Session, 
        history_id: int, 
        status: str, 
        error_message: str = None,
        results: Dict[str, Any] = None
    ):
        """Update search status"""
        history = session.query(SearchHistory).get(history_id)
        if history:
            history.status = status
            history.search_completed = datetime.utcnow()
            
            if error_message:
                history.error_message = error_message
            
            if results:
                history.stores_found = results.get('stores_found', 0)
                history.items_scraped = results.get('items_scraped', 0)
                history.opportunities_found = results.get('opportunities_found', 0)
            
            if history.search_started:
                duration = (history.search_completed - history.search_started).total_seconds()
                history.duration_seconds = int(duration)


# Initialize database on module import
init_database()

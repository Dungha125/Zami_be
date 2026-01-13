from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Float, Text, Boolean, ForeignKey, Integer
from datetime import datetime
from settings import get_settings

settings = get_settings()

# Use async database URL from settings
engine = create_async_engine(settings.database_url_async, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

# Database Models
class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    user_id = Column(String, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    avatar = Column(Text, nullable=True)  # Base64 encoded image
    bio = Column(Text, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Friend(Base):
    __tablename__ = "friends"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("user_profiles.user_id"), nullable=False, index=True)
    friend_id = Column(String, ForeignKey("user_profiles.user_id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Ensure unique friendship (bidirectional)
    __table_args__ = (
        {'extend_existing': True},
    )

class UserLocation(Base):
    __tablename__ = "user_locations"
    
    user_id = Column(String, ForeignKey("user_profiles.user_id"), primary_key=True, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

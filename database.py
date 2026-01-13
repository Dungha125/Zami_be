from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Float, Text, Boolean, ForeignKey, Integer, text
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
    google_id = Column(String, nullable=True, index=True, unique=True)  # Google user ID
    email = Column(String, nullable=True, index=True)
    username = Column(String, nullable=False, index=True)
    avatar = Column(Text, nullable=True)  # URL or Base64 encoded image
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

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sender_id = Column(String, ForeignKey("user_profiles.user_id"), nullable=False, index=True)
    receiver_id = Column(String, ForeignKey("user_profiles.user_id"), nullable=False, index=True)
    content = Column(Text, nullable=True)
    sticker = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Index for querying conversations
    __table_args__ = (
        {'extend_existing': True},
    )

async def init_db():
    """Initialize database tables and migrate schema if needed"""
    async with engine.begin() as conn:
        # Create all tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
        
        # Migrate: Add google_id and email columns if they don't exist
        try:
            # Check if google_id column exists
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='user_profiles' AND column_name='google_id'
            """))
            row = result.fetchone()
            if not row:
                # Add google_id column
                await conn.execute(text("""
                    ALTER TABLE user_profiles 
                    ADD COLUMN google_id VARCHAR
                """))
                # Create index (PostgreSQL doesn't support IF NOT EXISTS for indexes in all versions)
                try:
                    await conn.execute(text("""
                        CREATE INDEX ix_user_profiles_google_id 
                        ON user_profiles(google_id)
                    """))
                except Exception:
                    pass  # Index might already exist
                try:
                    await conn.execute(text("""
                        CREATE UNIQUE INDEX ix_user_profiles_google_id_unique 
                        ON user_profiles(google_id) 
                        WHERE google_id IS NOT NULL
                    """))
                except Exception:
                    pass  # Index might already exist
                print("Added google_id column to user_profiles")
            
            # Check if email column exists
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='user_profiles' AND column_name='email'
            """))
            row = result.fetchone()
            if not row:
                # Add email column
                await conn.execute(text("""
                    ALTER TABLE user_profiles 
                    ADD COLUMN email VARCHAR
                """))
                # Create index
                try:
                    await conn.execute(text("""
                        CREATE INDEX ix_user_profiles_email 
                        ON user_profiles(email)
                    """))
                except Exception:
                    pass  # Index might already exist
                print("Added email column to user_profiles")
        except Exception as e:
            # If migration fails, log but don't crash (column might already exist)
            print(f"Migration note: {e}")
        
        # Migrate: Clean up messages table schema (remove unwanted columns)
        try:
            # Check if messages table exists and has unwanted columns
            result = await conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='messages' AND column_name IN ('status', 'delivered_at', 'read_at')
            """))
            unwanted_columns = [row[0] for row in result.fetchall()]
            
            # Drop unwanted columns if they exist
            for col in unwanted_columns:
                try:
                    await conn.execute(text(f"""
                        ALTER TABLE messages DROP COLUMN IF EXISTS {col}
                    """))
                    print(f"Removed column {col} from messages table")
                except Exception as e:
                    print(f"Error removing column {col}: {e}")
        except Exception as e:
            # If migration fails, log but don't crash
            print(f"Messages table migration note: {e}")

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

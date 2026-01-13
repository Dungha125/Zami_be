from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache

class Settings(BaseSettings):
    # Application
    app_name: str = "Jagat Clone API"
    debug: bool = False
    
    # Database
    database_url: str = "postgresql://jagat_user:jagat_password@localhost:5432/jagat_db"
    
    # CORS
    allowed_origins: Optional[str] = None  # Comma-separated list of origins
    railway_environment: Optional[str] = None
    railway_public_domain: Optional[str] = None
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    
    # Railway will set PORT environment variable
    @property
    def server_port(self) -> int:
        """Get port, prefer PORT env var (for Railway)"""
        import os
        return int(os.getenv("PORT", self.port))
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS allowed origins as list"""
        if self.allowed_origins:
            return [origin.strip() for origin in self.allowed_origins.split(",")]
        
        # Check Railway environment variables (set by Railway automatically)
        import os
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PUBLIC_DOMAIN"):
            # In Railway but no ALLOWED_ORIGINS set, allow all (not recommended)
            return ["*"]
        
        # Default for local development
        return ["http://localhost:3000", "http://localhost:5173"]
    
    @property
    def cors_allow_credentials(self) -> bool:
        """Determine if CORS should allow credentials"""
        if self.allowed_origins:
            return True
        
        # Check Railway environment variables
        import os
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PUBLIC_DOMAIN"):
            return False  # Cannot use credentials with wildcard origin
        
        return True
    
    @property
    def database_url_async(self) -> str:
        """Convert postgresql:// to postgresql+asyncpg:// for async support"""
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

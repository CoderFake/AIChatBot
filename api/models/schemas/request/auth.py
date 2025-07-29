from pydantic import BaseModel

class LoginRequest(BaseModel):
    """Request model for login"""
    pass

class LogoutRequest(BaseModel):
    """Request model for logout"""
    pass

class RefreshTokenRequest(BaseModel):
    pass
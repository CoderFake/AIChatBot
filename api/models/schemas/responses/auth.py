from pydantic import BaseModel

class LoginResponse(BaseModel):
    """Response model for login"""
    pass

class LogoutResponse(BaseModel):
    """Response model for logout"""
    pass

class RefreshTokenResponse(BaseModel):
    """Response model for refresh token"""
    pass
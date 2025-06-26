from dataclasses import dataclass
from utils.datetime_utils import CustomDateTime as datetime

@dataclass
class OTPEntry:
    """OTP entry trong cache"""
    user_id: str
    token_hash: str
    operation: str
    created_at: datetime
    expires_at: datetime
    used: bool = False

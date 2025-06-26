
import secrets
import hashlib
import time
from typing import Dict, Optional, Tuple
from datetime import timedelta
from utils.datetime_utils import CustomDateTime as datetime
from utils.logging import get_logger
from services.dataclasses.otp import OTPEntry

logger = get_logger(__name__)



class OTPManager:
    """
    OTP Manager cho config operations
    Sử dụng in-memory cache cho OTP tokens
    """
    
    def __init__(self, validity_minutes: int = 5):
        self._otp_cache: Dict[str, OTPEntry] = {}
        self._validity_minutes = validity_minutes
        self._cleanup_interval = 60  # seconds
        self._last_cleanup = time.time()
    
    def generate_otp(
        self, 
        user_id: str, 
        operation: str = "config_change"
    ) -> str:
        """
        Generate OTP token cho user
        
        Args:
            user_id: ID của user
            operation: Loại operation (config_change, tool_toggle, provider_change)
            
        Returns:
            OTP token string (6 digits)
        """
        try:
            self._cleanup_expired_tokens()
            
            otp_token = self._generate_secure_token()
            
            token_hash = self._hash_token(otp_token)
            
            now = datetime.now()
            expires_at = now + timedelta(minutes=self._validity_minutes)
            
            cache_key = f"{user_id}_{operation}_{int(now.timestamp())}"
            
            otp_entry = OTPEntry(
                user_id=user_id,
                token_hash=token_hash,
                operation=operation,
                created_at=now,
                expires_at=expires_at
            )
            
            self._otp_cache[cache_key] = otp_entry
            
            self._remove_old_user_otps(user_id, operation, exclude_key=cache_key)
            
            logger.info(f"OTP generated for user {user_id} operation {operation}")
            
            return otp_token
            
        except Exception as e:
            logger.error(f"Failed to generate OTP: {e}")
            raise
    
    def verify_otp(
        self, 
        user_id: str, 
        token: str, 
        operation: str = "config_change"
    ) -> Tuple[bool, str]:
        """
        Verify OTP token
        
        Args:
            user_id: ID của user
            token: OTP token để verify
            operation: Loại operation
            
        Returns:
            Tuple[bool, str]: (is_valid, reason)
        """
        try:
            self._cleanup_expired_tokens()
            
            token_hash = self._hash_token(token)
            
            matching_entry = None
            matching_key = None
            
            for key, entry in self._otp_cache.items():
                if (entry.user_id == user_id and 
                    entry.operation == operation and 
                    entry.token_hash == token_hash and
                    not entry.used):
                    matching_entry = entry
                    matching_key = key
                    break
            
            if not matching_entry:
                logger.warning(f"Invalid OTP attempt for user {user_id}")
                return False, "Invalid or expired OTP token"
            
            if datetime.now() > matching_entry.expires_at:
                del self._otp_cache[matching_key]
                logger.warning(f"Expired OTP used by user {user_id}")
                return False, "OTP token has expired"
            
            matching_entry.used = True
            
            logger.info(f"OTP verified successfully for user {user_id}")
            
            self._schedule_token_cleanup(matching_key)
            
            return True, "OTP verified successfully"
            
        except Exception as e:
            logger.error(f"Failed to verify OTP: {e}")
            return False, f"Error verifying OTP: {str(e)}"
    
    def get_user_otp_status(self, user_id: str) -> Dict[str, any]:
        """
        Lấy OTP status của user
        
        Args:
            user_id: ID của user
            
        Returns:
            Dict chứa OTP status
        """
        self._cleanup_expired_tokens()
        
        user_otps = []
        for entry in self._otp_cache.values():
            if entry.user_id == user_id:
                user_otps.append({
                    'operation': entry.operation,
                    'created_at': entry.created_at.isoformat(),
                    'expires_at': entry.expires_at.isoformat(),
                    'is_used': entry.used,
                    'is_expired': datetime.now() > entry.expires_at
                })
        
        return {
            'user_id': user_id,
            'active_otps': len([otp for otp in user_otps if not otp['is_used'] and not otp['is_expired']]),
            'total_otps': len(user_otps),
            'otps': user_otps
        }
    
    def revoke_user_otps(self, user_id: str, operation: Optional[str] = None) -> int:
        """
        Revoke all OTPs for user
        
        Args:
            user_id: ID của user
            operation: Optional - chỉ revoke specific operation
            
        Returns:
            Number of OTPs revoked
        """
        revoked_count = 0
        keys_to_remove = []
        
        for key, entry in self._otp_cache.items():
            if entry.user_id == user_id:
                if operation is None or entry.operation == operation:
                    keys_to_remove.append(key)
                    revoked_count += 1
        
        for key in keys_to_remove:
            del self._otp_cache[key]
        
        logger.info(f"Revoked {revoked_count} OTPs for user {user_id}")
        
        return revoked_count
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Lấy statistics của OTP cache"""
        self._cleanup_expired_tokens()
        
        active_otps = len([entry for entry in self._otp_cache.values() if not entry.used])
        used_otps = len([entry for entry in self._otp_cache.values() if entry.used])
        
        operations = {}
        for entry in self._otp_cache.values():
            if entry.operation not in operations:
                operations[entry.operation] = 0
            operations[entry.operation] += 1
        
        return {
            'total_tokens': len(self._otp_cache),
            'active_tokens': active_otps,
            'used_tokens': used_otps,
            'operations': operations,
            'cleanup_interval': self._cleanup_interval,
            'validity_minutes': self._validity_minutes
        }
    
    
    def _generate_secure_token(self) -> str:
        """Generate 6-digit secure random token"""
        # Generate số random 6 chữ số
        return f"{secrets.randbelow(1000000):06d}"
    
    def _hash_token(self, token: str) -> str:
        """Hash token using SHA-256"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _cleanup_expired_tokens(self):
        """Remove expired tokens từ cache"""
        current_time = time.time()
        
        # Only cleanup periodically để tránh performance impact
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        now = datetime.now()
        keys_to_remove = []
        
        for key, entry in self._otp_cache.items():
            if now > entry.expires_at or entry.used:
                keys_to_remove.append(key)
        
        removed_count = 0
        for key in keys_to_remove:
            del self._otp_cache[key]
            removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired/used OTP tokens")
        
        self._last_cleanup = current_time
    
    def _remove_old_user_otps(
        self, 
        user_id: str, 
        operation: str, 
        exclude_key: str
    ):
        """Remove old OTPs cho same user/operation"""
        keys_to_remove = []
        
        for key, entry in self._otp_cache.items():
            if (key != exclude_key and 
                entry.user_id == user_id and 
                entry.operation == operation):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._otp_cache[key]
    
    def _schedule_token_cleanup(self, token_key: str):
        """Schedule cleanup of used token (placeholder for future async cleanup)"""
        # For now, used tokens will be cleaned up trong next cleanup cycle
        pass


# Global OTP manager instance
otp_manager = OTPManager()

# Export
__all__ = [
    "otp_manager", 
    "OTPManager", 
    "OTPEntry"
]
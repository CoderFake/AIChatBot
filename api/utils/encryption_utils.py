"""
Encryption utilities for API keys and sensitive data
Uses app secret key for encryption/decryption
"""
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import List, Optional
import secrets

from config.settings import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EncryptionService:
    """
    Service for encrypting/decrypting sensitive data using app secret key
    """
    
    def __init__(self):
        self._fernet = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """
        Initialize Fernet encryption using app secret key
        """
        try:
            secret_key = settings.SECRET_KEY.encode()
            
            app_salt = self._get_app_salt()
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=app_salt,
                iterations=100000,
            )
            
            key = base64.urlsafe_b64encode(kdf.derive(secret_key))
            self._fernet = Fernet(key)
            
            logger.info("Encryption service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise
    
    def _get_app_salt(self) -> bytes:
        """
        Generate consistent salt based on app configuration
        Not fixed, but deterministic per app instance
        """
        salt_source = f"{settings.APP_NAME}:{settings.SECRET_KEY}".encode()
        
        digest = hashes.Hash(hashes.SHA256())
        digest.update(salt_source)
        salt_hash = digest.finalize()
        
        return salt_hash[:16]
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt string data
        Returns base64 encoded encrypted data
        """
        try:
            if not data:
                return ""
            
            encrypted_data = self._fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt base64 encoded encrypted data
        Returns original string
        """
        try:
            if not encrypted_data:
                return ""
            
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self._fernet.decrypt(encrypted_bytes)
            return decrypted_data.decode()
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_api_keys(self, api_keys: List[str]) -> List[str]:
        """
        Encrypt list of API keys
        """
        try:
            return [self.encrypt(key) for key in api_keys if key]
        except Exception as e:
            logger.error(f"API keys encryption failed: {e}")
            raise
    
    def decrypt_api_keys(self, encrypted_keys: List[str]) -> List[str]:
        """
        Decrypt list of encrypted API keys
        """
        try:
            return [self.decrypt(key) for key in encrypted_keys if key]
        except Exception as e:
            logger.error(f"API keys decryption failed: {e}")
            raise
    
    def encrypt_sensitive_config(self, config_data: dict) -> dict:
        """
        Encrypt sensitive fields in configuration data
        """
        try:
            encrypted_config = config_data.copy()
            
            sensitive_fields = [
                'api_key', 'secret_key', 'password', 'token', 
                'private_key', 'access_token', 'refresh_token'
            ]
            
            for field in sensitive_fields:
                if field in encrypted_config and encrypted_config[field]:
                    encrypted_config[field] = self.encrypt(str(encrypted_config[field]))
            
            return encrypted_config
            
        except Exception as e:
            logger.error(f"Config encryption failed: {e}")
            raise
    
    def decrypt_sensitive_config(self, encrypted_config: dict) -> dict:
        """
        Decrypt sensitive fields in configuration data
        """
        try:
            decrypted_config = encrypted_config.copy()
            
            sensitive_fields = [
                'api_key', 'secret_key', 'password', 'token',
                'private_key', 'access_token', 'refresh_token'
            ]
            
            for field in sensitive_fields:
                if field in decrypted_config and decrypted_config[field]:
                    decrypted_config[field] = self.decrypt(str(decrypted_config[field]))
            
            return decrypted_config
            
        except Exception as e:
            logger.error(f"Config decryption failed: {e}")
            raise
    
    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate cryptographically secure random token
        """
        return secrets.token_urlsafe(length)


encryption_service = EncryptionService() 
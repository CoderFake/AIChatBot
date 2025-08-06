"""
JWT utility functions with blacklist support
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
import uuid

from config.settings import get_settings
from utils.logging import get_logger
from core.exceptions import AuthenticationError

logger = get_logger(__name__)
settings = get_settings()


class JWTManager:
    """
    JWT token management with blacklist support
    """
    
    @staticmethod
    def is_token_valid_for_user(token: str, user_password_changed_at: Optional[datetime]) -> bool:
        """
        Check if token is still valid based on user's password_changed_at
        Tokens issued before password change are invalid
        """
        try:
            payload = JWTManager.decode_token(token, verify_exp=False)
            token_issued_at = payload.get("iat")
            
            if not token_issued_at or not user_password_changed_at:
                return True
            
            token_datetime = datetime.fromtimestamp(token_issued_at)
            return token_datetime > user_password_changed_at
            
        except Exception:
            return False
    
    @staticmethod
    def encode_token(payload: Dict[str, Any], token_type: str = "access") -> str:
        """
        Encode JWT token with JTI for blacklist support
        """
        try:
            user_role = payload.get("role", "USER")
            jwt_settings = settings.get_jwt_settings_for_user_type(user_role)
            
            now = datetime.utcnow()
            jti = str(uuid.uuid4())
            
            if token_type == "access":
                exp_minutes = jwt_settings["access_token_expire_minutes"]
                exp_time = now + timedelta(minutes=exp_minutes)
            elif token_type == "refresh":
                exp_days = jwt_settings["refresh_token_expire_days"]
                exp_time = now + timedelta(days=exp_days)
            else:
                raise ValueError(f"Invalid token type: {token_type}")
            
            payload.update({
                "iat": now,
                "exp": exp_time,
                "jti": jti,
                "type": token_type,
                "iss": settings.APP_NAME
            })
            
            token = jwt.encode(
                payload,
                jwt_settings["secret_key"],
                algorithm=jwt_settings["algorithm"]
            )
            
            logger.debug(f"Token encoded: type={token_type}, jti={jti}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to encode token: {e}")
            raise AuthenticationError("Token encoding failed")
    
    @staticmethod
    def decode_token(token: str, verify_exp: bool = True) -> Dict[str, Any]:
        """
        Decode JWT token
        """
        try:
            options = {"verify_exp": verify_exp}
            
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options=options
            )
            
            return payload
            
        except JWTError as e:
            logger.warning(f"Token decode failed: {e}")
            raise AuthenticationError("Invalid or expired token")
    
    @staticmethod
    def verify_token_type(token: str, expected_type: str) -> Dict[str, Any]:
        """
        Verify token and check its type
        """
        try:
            payload = JWTManager.decode_token(token)
            
            token_type = payload.get("type")
            if token_type != expected_type:
                raise AuthenticationError(f"Invalid token type. Expected {expected_type}")
            
            return payload
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise AuthenticationError("Token verification failed")
    
    @staticmethod
    def create_token_payload(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create JWT payload for different user types
        """
        base_payload = {
            "user_id": user_data["user_id"],
            "email": user_data["email"],
            "username": user_data.get("username"),
            "role": user_data["role"],
        }
        
        if user_data.get("tenant_id"):
            base_payload["tenant_id"] = user_data["tenant_id"]
        
        if user_data.get("department_id") and user_data["role"] in ["DEPT_ADMIN", "DEPT_MANAGER", "USER"]:
            base_payload["department_id"] = user_data["department_id"]
            base_payload["department_name"] = user_data.get("department_name")
        
        if user_data.get("permissions"):
            base_payload["permissions"] = user_data["permissions"]
        
        return base_payload
    
    @staticmethod
    def extract_user_context(token: str) -> Dict[str, Any]:
        """
        Extract user context from access token
        """
        try:
            payload = JWTManager.verify_token_type(token, "access")
            
            user_context = {
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "email": payload.get("email"),
                "role": payload.get("role"),
                "tenant_id": payload.get("tenant_id"),
                "department_id": payload.get("department_id"),
                "department_name": payload.get("department_name"),
                "permissions": payload.get("permissions", []),
                "jti": payload.get("jti")
            }
            
            return user_context
            
        except Exception as e:
            logger.error(f"Failed to extract user context: {e}")
            raise AuthenticationError("Invalid token")
    
    @staticmethod
    def create_token_pair(user_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Create access and refresh token pair
        """
        try:
            access_payload = JWTManager.create_token_payload(user_data)
            access_token = JWTManager.encode_token(access_payload, "access")
            
            refresh_payload = {
                "user_id": user_data["user_id"],
                "role": user_data["role"]
            }
            refresh_token = JWTManager.encode_token(refresh_payload, "refresh")
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
            
        except Exception as e:
            logger.error(f"Failed to create token pair: {e}")
            raise AuthenticationError("Token creation failed")
    
    @staticmethod
    def get_token_jti(token: str) -> Optional[str]:
        """
        Extract JTI from token without full verification
        """
        try:
            payload = JWTManager.decode_token(token, verify_exp=False)
            return payload.get("jti")
        except Exception:
            return None
    
    @staticmethod
    def get_token_expiry(token: str) -> Optional[datetime]:
        """
        Get token expiry time
        """
        try:
            payload = JWTManager.decode_token(token, verify_exp=False)
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp)
            return None
        except Exception:
            return None


jwt_manager = JWTManager()
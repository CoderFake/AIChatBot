from typing import List, Optional
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timedelta

from models.database.base import BaseModel
from utils.datetime_utils import CustomDateTime as datetime


class User(BaseModel):
    """
    User model cho authentication và authorization
    """
    
    __tablename__ = "users"
    
    username = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Username duy nhất của user"
    )
    
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Email address của user"
    )
    
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password"
    )
    
    first_name = Column(
        String(100),
        nullable=False,
        comment="Tên của user"
    )
    
    last_name = Column(
        String(100),
        nullable=False,
        comment="Họ của user"
    )
    
    full_name = Column(
        String(200),
        nullable=False,
        index=True,
        comment="Họ tên đầy đủ của user"
    )
    
    department = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Phòng ban của user: HR, IT, FINANCE, etc."
    )
    
    role = Column(
        String(50),
        nullable=False,
        index=True,
        default="EMPLOYEE",
        comment="Role của user: EMPLOYEE, MANAGER, DIRECTOR, ADMIN, CEO"
    )
    
    job_title = Column(
        String(200),
        nullable=True,
        comment="Chức danh công việc"
    )
    
    employee_id = Column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
        comment="Mã nhân viên"
    )
    
    phone_number = Column(
        String(20),
        nullable=True,
        comment="Số điện thoại"
    )
    
    avatar_url = Column(
        String(500),
        nullable=True,
        comment="URL của avatar image"
    )
   
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="User có active không"
    )
    
    is_staff = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="User có quyền staff không"
    )
    
    is_superuser = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="User có quyền superuser không"
    )
    
    last_login = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Lần login cuối cùng"
    )
    
    login_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Số lần đã login"
    )
    
    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="User bị lock đến thời điểm nào"
    )
    
    password_changed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Lần đổi password cuối cùng"
    )
    
    session_expires = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời điểm session hết hạn"
    )
    
    preferences = Column(
        JSONB,
        nullable=True,
        comment="User preferences dưới dạng JSON"
    )
    
    profile_data = Column(
        JSONB,
        nullable=True,
        comment="Additional profile data"
    )
    
    permissions = relationship(
        "UserPermission",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_user_active_tenant', 'tenant_id', 'is_active'),
        Index('idx_user_department_role', 'department', 'role'),
        Index('idx_user_email_tenant', 'email', 'tenant_id'),
        Index('idx_user_username_tenant', 'username', 'tenant_id'),
        Index('idx_user_last_login', 'last_login'),
        Index('idx_user_locked_until', 'locked_until'),
    )
    
    @property
    def display_name(self) -> str:
        """
        Lấy display name của user
        """
        return self.full_name or f"{self.first_name} {self.last_name}"
    
    @property
    def is_locked(self) -> bool:
        """
        Check xem user có bị lock không
        """
        if self.locked_until is None:
            return False
        return datetime.now() < self.locked_until
    
    @property
    def is_password_expired(self) -> bool:
        """
        Check xem password có hết hạn không (90 ngày)
        """
        if self.password_changed_at is None:
            return True
        
        password_expiry_days = 90
        expiry_date = self.password_changed_at + timedelta(days=password_expiry_days)
        return datetime.now() > expiry_date
    
    @property
    def is_session_valid(self) -> bool:
        """
        Check xem session có còn valid không
        """
        if self.session_expires is None:
            return False
        return datetime.now() < self.session_expires
    
    def update_login_info(self):
        """
        Update thông tin khi user login thành công
        """
        self.last_login = datetime.now()
        self.login_count += 1
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def record_failed_login(self, max_attempts: int = 5, lockout_duration: int = 900):
        """
        Record failed login attempt và lock user nếu vượt quá số lần cho phép
        """
        self.failed_login_attempts += 1
        
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now() + timedelta(seconds=lockout_duration)
    
    def unlock_account(self):
        """
        Unlock user account
        """
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def set_session_expiry(self, minutes: int = 30):
        """
        Set session expiry time
        """
        self.session_expires = datetime.now() + timedelta(minutes=minutes)
    
    def mark_password_changed(self):
        """
        Mark password đã được thay đổi
        """
        self.password_changed_at = datetime.now()
    
    def activate(self):
        """
        Activate user account
        """
        self.is_active = True
        self.unlock_account()
    
    def deactivate(self):
        """
        Deactivate user account
        """
        self.is_active = False
        self.session_expires = None
    
    def verify_staff(self):
        """
        Verify user staff
        """
        self.is_staff = True
    
    def update_preferences(self, preferences: dict):
        """
        Update user preferences
        """
        if self.preferences is None:
            self.preferences = {}
        
        self.preferences.update(preferences)
    
    def get_preference(self, key: str, default=None):
        """
        Lấy specific preference value
        """
        if self.preferences is None:
            return default
        return self.preferences.get(key, default)
    
    def update_profile_data(self, profile_data: dict):
        """
        Update profile data
        """
        if self.profile_data is None:
            self.profile_data = {}
        
        self.profile_data.update(profile_data)
    
    def get_profile_field(self, field: str, default=None):
        """
        Lấy specific profile field
        """
        if self.profile_data is None:
            return default
        return self.profile_data.get(field, default)
    
    def has_role(self, role: str) -> bool:
        """
        Check xem user có role cụ thể không
        """
        return self.role.upper() == role.upper()
    
    def is_in_department(self, department: str) -> bool:
        """
        Check xem user có thuộc department cụ thể không
        """
        return self.department.upper() == department.upper()
    
    def can_access_department(self, department: str) -> bool:
        """
        Check xem user có thể access department khác không
        Based on role và permissions
        """
        if self.is_in_department(department):
            return True
        
        if self.role in ['MANAGER', 'DIRECTOR', 'CEO']:
            return True
        
        if self.is_superuser:
            return True
        
        return False
    
    def get_accessible_departments(self) -> List[str]:
        """
        Lấy danh sách departments user có thể access
        """
        departments = [self.department]
        
        if self.role in ['MANAGER', 'DIRECTOR', 'CEO'] or self.is_superuser:
            departments.extend(['HR', 'IT', 'FINANCE', 'SALES', 'MARKETING'])
        
        return list(set(departments)) 
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert user to dictionary, có option để include sensitive data
        """
        data = super().to_dict()
        
        if not include_sensitive:
            sensitive_fields = [
                'hashed_password', 'failed_login_attempts', 
                'locked_until', 'session_expires'
            ]
            for field in sensitive_fields:
                data.pop(field, None)
        
        data.update({
            'display_name': self.display_name,
            'is_locked': self.is_locked,
            'is_password_expired': self.is_password_expired,
            'is_session_valid': self.is_session_valid,
            'accessible_departments': self.get_accessible_departments()
        })
        
        return data
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}', department='{self.department}')>"


class UserSession(BaseModel):
    """
    Model để track user sessions
    """
    
    __tablename__ = "user_sessions"
    
    user_id = Column(
        String(36),
        nullable=False,
        index=True,
        comment="ID của user"
    )
    
    session_token = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Session token"
    )
    
    refresh_token = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Refresh token"
    )
    
    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP address của client"
    )
    
    user_agent = Column(
        Text,
        nullable=True,
        comment="User agent string"
    )
    
    device_info = Column(
        JSONB,
        nullable=True,
        comment="Device information"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Session expiry time"
    )
    
    last_activity = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        comment="Last activity time"
    )
    
    is_revoked = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Session có bị revoke không"
    )
    
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời điểm revoke session"
    )
    
    revoked_by = Column(
        String(36),
        nullable=True,
        comment="User ID của người revoke session"
    )
    
    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'is_revoked'),
        Index('idx_session_expires', 'expires_at'),
        Index('idx_session_last_activity', 'last_activity'),
    )
    
    @property
    def is_expired(self) -> bool:
        """
        Check xem session có expired không
        """
        return datetime.now() > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """
        Check xem session có valid không
        """
        return not self.is_revoked and not self.is_expired
    
    def extend_session(self, minutes: int = 30):
        """
        Extend session expiry time
        """
        self.expires_at = datetime.now() + timedelta(minutes=minutes)
        self.last_activity = datetime.now()
    
    def revoke(self, revoked_by: str = None):
        """
        Revoke session
        """
        self.is_revoked = True
        self.revoked_at = datetime.now()
        if revoked_by:
            self.revoked_by = revoked_by
    
    def update_activity(self):
        """
        Update last activity time
        """
        self.last_activity = datetime.now()
    
    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id='{self.user_id}', expires_at='{self.expires_at}')>"


class UserLoginHistory(BaseModel):
    """
    Model để track login history của users
    """
    
    __tablename__ = "user_login_history"
    
    user_id = Column(
        String(36),
        nullable=False,
        index=True,
        comment="ID của user"
    )
    
    login_time = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        index=True,
        comment="Thời gian login"
    )
    
    logout_time = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Thời gian logout"
    )
    
    ip_address = Column(
        String(45),
        nullable=True,
        index=True,
        comment="IP address"
    )
    
    user_agent = Column(
        Text,
        nullable=True,
        comment="User agent string"
    )
    
    device_info = Column(
        JSONB,
        nullable=True,
        comment="Device information"
    )
    
    location_info = Column(
        JSONB,
        nullable=True,
        comment="Location information based on IP"
    )
    
    login_method = Column(
        String(50),
        nullable=False,
        default="password",
        comment="Login method: password, sso, etc."
    )
    
    success = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Login có thành công không"
    )
    
    failure_reason = Column(
        String(200),
        nullable=True,
        comment="Lý do login thất bại"
    )
    
    session_duration = Column(
        Integer,
        nullable=True,
        comment="Session duration tính bằng giây"
    )
    
    __table_args__ = (
        Index('idx_login_history_user_time', 'user_id', 'login_time'),
        Index('idx_login_history_success', 'success'),
        Index('idx_login_history_ip', 'ip_address'),
    )
    
    def mark_logout(self):
        """
        Mark session logout
        """
        self.logout_time = datetime.now()
        if self.login_time:
            duration = (self.logout_time - self.login_time).total_seconds()
            self.session_duration = int(duration)
    
    def __repr__(self) -> str:
        return f"<UserLoginHistory(id={self.id}, user_id='{self.user_id}', login_time='{self.login_time}', success={self.success})>"
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import HTTPException, Depends, Request
import secrets
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

security = HTTPBasic()
logger = logging.getLogger(__name__)

# In-memory session store for admin sessions (use Redis in production)
admin_sessions = {}

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials using HTTP Basic Auth with enhanced security"""
    try:
        # Get credentials from environment
        correct_username = os.getenv("ADMIN_USERNAME", "admin")
        correct_password = os.getenv("ADMIN_PASSWORD", "admin123")
        
        # Verify credentials using constant-time comparison
        correct_username_check = secrets.compare_digest(
            credentials.username,
            correct_username
        )
        correct_password_check = secrets.compare_digest(
            credentials.password,
            correct_password
        )
        
        if not (correct_username_check and correct_password_check):
            logger.warning(f"Failed admin login attempt for username: {credentials.username}")
            raise HTTPException(
                status_code=401,
                detail="Incorrect admin credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        
        # Log successful authentication
        logger.info(f"Successful admin login: {credentials.username}")
        
        # Store session info (in production, use proper session management)
        session_id = secrets.token_urlsafe(32)
        admin_sessions[session_id] = {
            "username": credentials.username,
            "login_time": datetime.now(),
            "last_activity": datetime.now()
        }
        
        return credentials.username
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin authentication error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Authentication service error"
        )

def get_admin_session(session_id: str) -> Optional[dict]:
    """Get admin session information"""
    session = admin_sessions.get(session_id)
    if session:
        # Check if session is still valid (24 hours)
        if datetime.now() - session["login_time"] > timedelta(hours=24):
            del admin_sessions[session_id]
            return None
        
        # Update last activity
        session["last_activity"] = datetime.now()
        return session
    return None

def cleanup_expired_sessions():
    """Clean up expired admin sessions"""
    current_time = datetime.now()
    expired_sessions = [
        session_id for session_id, session in admin_sessions.items()
        if current_time - session["login_time"] > timedelta(hours=24)
    ]
    
    for session_id in expired_sessions:
        del admin_sessions[session_id]
    
    if expired_sessions:
        logger.info(f"Cleaned up {len(expired_sessions)} expired admin sessions")

def require_admin_permission(permission: str):
    """Decorator for requiring specific admin permissions (future enhancement)"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # In a full implementation, check user permissions here
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Rate limiting for admin endpoints (basic implementation)
admin_request_counts = {}

def check_admin_rate_limit(username: str, max_requests: int = 100, window_minutes: int = 60):
    """Basic rate limiting for admin endpoints"""
    current_time = datetime.now()
    window_start = current_time - timedelta(minutes=window_minutes)
    
    if username not in admin_request_counts:
        admin_request_counts[username] = []
    
    # Clean old requests
    admin_request_counts[username] = [
        req_time for req_time in admin_request_counts[username]
        if req_time > window_start
    ]
    
    # Check if limit exceeded
    if len(admin_request_counts[username]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {window_minutes} minutes."
        )
    
    # Add current request
    admin_request_counts[username].append(current_time)

def log_admin_action(username: str, action: str, details: str = ""):
    """Log admin actions for audit trail"""
    logger.info(f"ADMIN_ACTION | User: {username} | Action: {action} | Details: {details}")

# Enhanced admin verification with rate limiting and logging
def verify_admin_with_logging(credentials: HTTPBasicCredentials = Depends(security)):
    """Enhanced admin verification with rate limiting and action logging"""
    username = verify_admin(credentials)
    
    # Apply rate limiting
    check_admin_rate_limit(username)
    
    # Clean up expired sessions periodically
    if len(admin_sessions) > 100:  # Arbitrary threshold
        cleanup_expired_sessions()
    
    return username
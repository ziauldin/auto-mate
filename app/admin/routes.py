from fastapi import APIRouter, Depends, Request, HTTPException, Query, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, and_, or_, extract
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json
import csv
import io
import secrets
from pydantic import BaseModel
import os

from app.database import get_db
from app.models import ChatSession, Message, AdminSettings
from .dependencies import verify_admin

router = APIRouter()
templates = Jinja2Templates(directory="app/admin/templates")

# Pydantic models for settings
class SettingsUpdate(BaseModel):
    app_name: str
    timezone: str
    date_format: str
    records_per_page: int
    dark_mode: bool
    require_2fa: bool
    login_alerts: bool
    session_timeout: int
    email_notifications: bool
    notification_email: str

# Analytics data models
class AnalyticsRequest(BaseModel):
    start_date: str
    end_date: str
    granularity: str

# --- Common Utility Functions ---
def format_relative_time(dt: Optional[datetime]) -> str:
    """Format datetime as relative time string"""
    if not dt:
        return "Never"
    
    now = datetime.now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=None)
    if now.tzinfo is None:
        now = now.replace(tzinfo=None)
    
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

# --- Dashboard Routes ---
@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """Admin dashboard overview with enhanced statistics"""
    try:
        # Get comprehensive statistics
        stats = {}
        
        # Basic counts
        stats["total_users"] = await db.scalar(
            select(func.count(func.distinct(ChatSession.user_id))))
        stats["total_sessions"] = await db.scalar(
            select(func.count(ChatSession.id)))
        stats["total_messages"] = await db.scalar(
            select(func.count(Message.id)))
        
        # Active today
        today = datetime.now().date()
        stats["active_today"] = await db.scalar(
            select(func.count(ChatSession.id))
            .where(func.date(ChatSession.created_at) == today)
        )
        
        # Additional metrics for enhanced dashboard
        stats["avg_messages_per_session"] = await db.scalar(
            select(func.avg(
                select(func.count(Message.id))
                .where(Message.session_id == ChatSession.id)
                .scalar_subquery()
            ))
        ) or 0
        
        # Popular car manufacturers
        manufacturer_stats = await db.execute(
            select(
                ChatSession.manufacturer,
                func.count(ChatSession.id).label("count")
            )
            .group_by(ChatSession.manufacturer)
            .order_by(desc("count"))
            .limit(5)
        )
        stats["popular_manufacturers"] = manufacturer_stats.all()
        
        return templates.TemplateResponse(
            "admin/dashboard.html",
            {
                "request": request,
                "stats": stats,
                "username": username
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")

# --- Settings Routes ---
@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """Render the settings page with current settings"""
    try:
        # Get current settings
        settings = await db.scalar(select(AdminSettings).limit(1))
        
        if not settings:
            # Create default settings if none exist
            settings = AdminSettings(
                app_name="Auto-Mate",
                timezone="UTC",
                date_format="Y-m-d",
                records_per_page=25,
                dark_mode=True,
                require_2fa=True,
                login_alerts=True,
                session_timeout=30,
                email_notifications=True,
                notification_email="admin@example.com",
                alert_new_user=True,
                alert_failed_login=True,
                alert_system_error=True,
                alert_high_usage=False
            )
            db.add(settings)
            await db.commit()
            await db.refresh(settings)
        
        return templates.TemplateResponse(
            "admin/settings.html",
            {
                "request": request,
                "username": username,
                "settings": settings
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Settings page error: {str(e)}")

@router.post("/api/settings", response_class=JSONResponse)
async def update_settings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """Update system settings"""
    try:
        form_data = await request.form()
        
        # Get current settings or create new if none exist
        settings = await db.scalar(select(AdminSettings).limit(1))
        if not settings:
            settings = AdminSettings()
            db.add(settings)
        
        # Update settings from form data
        settings.app_name = form_data.get("appName", "Auto-Mate")
        settings.timezone = form_data.get("timezone", "UTC")
        settings.date_format = form_data.get("dateFormat", "Y-m-d")
        settings.records_per_page = int(form_data.get("recordsPerPage", 25))
        settings.dark_mode = form_data.get("darkMode") == "on"
        settings.require_2fa = form_data.get("require2FA") == "on"
        settings.login_alerts = form_data.get("loginAlerts") == "on"
        settings.session_timeout = int(form_data.get("sessionTimeout", 30))
        settings.email_notifications = form_data.get("emailNotifications") == "on"
        settings.notification_email = form_data.get("notificationEmail", "admin@example.com")
        settings.alert_new_user = form_data.get("alertNewUser") == "on"
        settings.alert_failed_login = form_data.get("alertFailedLogin") == "on"
        settings.alert_system_error = form_data.get("alertSystemError") == "on"
        settings.alert_high_usage = form_data.get("alertHighUsage") == "on"
        
        await db.commit()
        
        return {"success": True, "message": "Settings updated successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Settings update error: {str(e)}")

@router.post("/api/settings/password", response_class=JSONResponse)
async def update_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """Update admin password"""
    try:
        if new_password != confirm_password:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "New passwords do not match"}
            )
        
        # In a real app, you would verify current password first
        # Then hash and store the new password
        
        return {"success": True, "message": "Password updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password update error: {str(e)}")

                # --- Analytics Routes ---
# ---------------------- ANALYTICS HELPERS ----------------------

async def get_time_series_data(db: AsyncSession, model, start_date, end_date, granularity):
    stmt = select(
        func.date(model.created_at).label("date"),
        func.count(model.id).label("count")
    ).where(
        func.date(model.created_at) >= start_date,
        func.date(model.created_at) <= end_date
    ).group_by(func.date(model.created_at)).order_by(func.date(model.created_at))

    results = await db.execute(stmt)
    counts_by_date = {r.date: r.count for r in results.fetchall()}

    date_cursor = start_date
    series = []
    while date_cursor <= end_date:
        series.append(counts_by_date.get(date_cursor, 0))
        date_cursor += timedelta(days=1)
    return series

async def get_avg_session_duration(db: AsyncSession, start_date, end_date):
    stmt = select(
        func.avg(
            func.extract('epoch', func.max(ChatSession.created_at)) -
            func.extract('epoch', func.min(ChatSession.created_at))
        )
    ).where(
        func.date(ChatSession.created_at) >= start_date,
        func.date(ChatSession.created_at) <= end_date
    )

    result = await db.scalar(stmt)
    return round(result / 60, 2) if result else 0

async def get_user_locations(db: AsyncSession, start_date, end_date):
    # Dummy placeholder – replace with real IP or geo-tagged data
    return [("Lahore", 15), ("Karachi", 12), ("Islamabad", 9)]

async def get_top_models(db: AsyncSession, start_date, end_date):
    stmt = select(
        ChatSession.model,
        func.count(ChatSession.id)
    ).where(
        and_(
            func.date(ChatSession.created_at) >= start_date,
            func.date(ChatSession.created_at) <= end_date
        )
    ).group_by(ChatSession.model).order_by(func.count(ChatSession.id).desc()).limit(5)

    result = await db.execute(stmt)
    return result.fetchall()

async def generate_date_labels(start_date, end_date, granularity):
    labels = []
    current = start_date
    while current <= end_date:
        labels.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return labels

async def get_session_times(db: AsyncSession, start_date, end_date):
    stmt = select(
        extract('hour', ChatSession.created_at).label("hour"),
        func.count(ChatSession.id)
    ).where(
        func.date(ChatSession.created_at).between(start_date, end_date)
    ).group_by("hour").order_by("hour")

    results = await db.execute(stmt)
    hourly = {int(row.hour): row[1] for row in results.fetchall()}
    return [hourly.get(h, 0) for h in range(24)]

# ---------------------- ROUTES ----------------------

@router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)
        return templates.TemplateResponse(
            "admin/analytics.html",
            {
                "request": request,
                "username": username,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics page error: {str(e)}")

@router.post("admin/api/analytics", response_class=JSONResponse)
async def get_analytics_data(
    analytics_request: AnalyticsRequest,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    try:
        start_date = datetime.strptime(analytics_request.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(analytics_request.end_date, "%Y-%m-%d").date()
        granularity = analytics_request.granularity

        delta = end_date - start_date
        prev_start = start_date - delta
        prev_end = start_date

        session_counts = await get_time_series_data(db, ChatSession, start_date, end_date, granularity)
        message_counts = await get_time_series_data(db, Message, start_date, end_date, granularity)
        session_times = await get_session_times(db, start_date, end_date)
        top_models = await get_top_models(db, start_date, end_date)
        user_locations = await get_user_locations(db, start_date, end_date)

        total_sessions = sum(session_counts)
        total_messages = sum(message_counts)
        active_users = await db.scalar(
            select(func.count(func.distinct(ChatSession.user_id)))
            .where(and_(
                func.date(ChatSession.created_at) >= start_date,
                func.date(ChatSession.created_at) <= end_date
            ))
        )

        avg_duration = await get_avg_session_duration(db, start_date, end_date)
        messages_per_session = total_messages / total_sessions if total_sessions > 0 else 0

        prev_sessions = sum(await get_time_series_data(db, ChatSession, prev_start, prev_end, granularity))
        sessions_change = ((total_sessions - prev_sessions) / prev_sessions * 100) if prev_sessions > 0 else 0

        return {
            "metrics": {
                "total_sessions": total_sessions,
                "active_users": active_users,
                "avg_duration": avg_duration,
                "messages_per_session": messages_per_session,
                "sessions_change": sessions_change
            },
            "charts": {
                "activity_over_time": {
                    "labels": await generate_date_labels(start_date, end_date, granularity),
                    "sessions": session_counts,
                    "messages": message_counts
                },
                "session_times": {
                    "labels": [f"{hour}:00" for hour in range(24)],
                    "data": session_times
                },
                "top_models": {
                    "labels": [m[0] for m in top_models],
                    "data": [m[1] for m in top_models]
                },
                "user_locations": {
                    "labels": [loc[0] for loc in user_locations],
                    "data": [loc[1] for loc in user_locations]
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics data error: {str(e)}")

@router.get("/export/analytics")
async def export_analytics(
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        sessions = await db.execute(
            select(
                func.date(ChatSession.created_at).label("date"),
                func.count(ChatSession.id).label("sessions"),
                func.count(func.distinct(ChatSession.user_id)).label("users")
            )
            .where(and_(
                func.date(ChatSession.created_at) >= start,
                func.date(ChatSession.created_at) <= end
            ))
            .group_by(func.date(ChatSession.created_at))
            .order_by(func.date(ChatSession.created_at))
        )
        sessions = sessions.all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Sessions", "Unique Users"])
        for session in sessions:
            writer.writerow([session.date.strftime("%Y-%m-%d"), session.sessions, session.users])

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=analytics_{start}_{end}.csv"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")
# --- Maintenance Routes ---
@router.post("/api/maintenance/backup", response_class=JSONResponse)
async def backup_database(
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """Initiate database backup"""
    try:
        # In a real app, this would trigger a backup process
        backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        
        return {
            "success": True,
            "message": "Backup initiated",
            "backup_file": backup_file
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup error: {str(e)}")

@router.post("/api/maintenance/clear-cache", response_class=JSONResponse)
async def clear_cache(
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """Clear system cache"""
    try:
        # In a real app, this would clear your cache system
        return {"success": True, "message": "Cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clear error: {str(e)}")

# --- Helper Functions ---
async def get_time_series_data(
    db: AsyncSession,
    model,
    start_date: datetime.date,
    end_date: datetime.date,
    granularity: str
) -> List[int]:
    """Get time series data for a model"""
    if granularity == "day":
        date_expr = func.date(model.created_at)
    elif granularity == "week":
        date_expr = func.date_trunc('week', model.created_at)
    else:  # month
        date_expr = func.date_trunc('month', model.created_at)
    
    result = await db.execute(
        select(
            date_expr.label("period"),
            func.count(model.id).label("count")
        )
        .where(and_(
            func.date(model.created_at) >= start_date,
            func.date(model.created_at) <= end_date
        ))
        .group_by(date_expr)
        .order_by(date_expr)
    )
    
    data = result.all()
    
    # Fill in missing periods with 0
    counts = []
    current = start_date
    while current <= end_date:
        found = False
        for item in data:
            if granularity == "day" and item.period == current:
                counts.append(item.count)
                found = True
                break
            elif granularity == "week" and item.period.date() == current:
                counts.append(item.count)
                found = True
                break
            elif granularity == "month" and item.period.date().month == current.month:
                counts.append(item.count)
                found = True
                break
        
        if not found:
            counts.append(0)
        
        if granularity == "day":
            current += timedelta(days=1)
        elif granularity == "week":
            current += timedelta(weeks=1)
        else:  # month
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
    
    return counts

async def generate_date_labels(
    start_date: datetime.date,
    end_date: datetime.date,
    granularity: str
) -> List[str]:
    """Generate date labels for the chart based on granularity"""
    labels = []
    current = start_date
    while current <= end_date:
        if granularity == "day":
            labels.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        elif granularity == "week":
            labels.append(f"Week {current.isocalendar()[1]}")
            current += timedelta(weeks=1)
        elif granularity == "month":
            labels.append(current.strftime("%Y-%m"))
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
    return labels

async def get_session_times(
    db: AsyncSession,
    start_date: datetime.date,
    end_date: datetime.date
) -> List[int]:
    """Get session counts by hour of day"""
    result = await db.execute(
        select(
            extract('hour', ChatSession.created_at).label("hour"),
            func.count(ChatSession.id).label("count")
        )
        .where(and_(
            func.date(ChatSession.created_at) >= start_date,
            func.date(ChatSession.created_at) <= end_date
        ))
        .group_by(extract('hour', ChatSession.created_at))
        .order_by(extract('hour', ChatSession.created_at))
    )
    
    # Initialize all hours to 0
    hours = [0] * 24
    for row in result:
        hour = int(row.hour)
        hours[hour] = row.count
    
    return hours

async def get_top_models(
    db: AsyncSession,
    start_date: datetime.date,
    end_date: datetime.date,
    limit: int = 5
) -> List[tuple]:
    """Get top vehicle models by session count"""
    result = await db.execute(
        select(
            ChatSession.model,
            func.count(ChatSession.id).label("count")
        )
        .where(and_(
            func.date(ChatSession.created_at) >= start_date,
            func.date(ChatSession.created_at) <= end_date
        ))
        .group_by(ChatSession.model)
        .order_by(desc("count"))
        .limit(limit)
    )
    
    return result.all()

async def get_user_locations(
    db: AsyncSession,
    start_date: datetime.date,
    end_date: datetime.date,
    limit: int = 6
) -> List[tuple]:
    """Get user locations by session count"""
    # This assumes you have location data in your ChatSession model
    # If not, you might need to remove or modify this function
    result = await db.execute(
        select(
            ChatSession.location,
            func.count(ChatSession.id).label("count")
        )
        .where(and_(
            func.date(ChatSession.created_at) >= start_date,
            func.date(ChatSession.created_at) <= end_date,
            ChatSession.location.is_not(None)
        ))
        .group_by(ChatSession.location)
        .order_by(desc("count"))
        .limit(limit)
    )
    
    return result.all()

async def get_avg_session_duration(
    db: AsyncSession,
    start_date: datetime.date,
    end_date: datetime.date
) -> float:
    """Calculate average session duration in seconds"""
    result = await db.execute(
        select(
            func.avg(
                select(extract('epoch', func.max(Message.timestamp) - func.min(Message.timestamp)))
                .select_from(Message)
                .where(Message.session_id == ChatSession.id)
                .scalar_subquery()
            )
        )
        .where(and_(
            func.date(ChatSession.created_at) >= start_date,
            func.date(ChatSession.created_at) <= end_date
        ))
    )
    
    avg_duration = result.scalar() or 0
    return float(avg_duration)

# --- Include all your existing routes below ---
@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=10, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    """Enhanced user management with pagination and filtering"""
    try:
        # Build base query
        query = select(
            ChatSession.user_id,
            func.count(ChatSession.id).label("session_count"),
            func.count(Message.id).label("message_count"),
            func.max(ChatSession.created_at).label("last_active"),
            func.min(ChatSession.created_at).label("created_at")
        ).select_from(
            ChatSession
        ).outerjoin(
            Message, Message.session_id == ChatSession.id
        ).group_by(ChatSession.user_id)
        
        # Apply search filter
        if search:
            query = query.where(ChatSession.user_id.ilike(f"%{search}%"))
        
        # Apply status filter (based on recent activity)
        if status == "active":
            recent_date = datetime.now() - timedelta(days=7)
            query = query.having(func.max(ChatSession.created_at) > recent_date)
        elif status == "inactive":
            recent_date = datetime.now() - timedelta(days=7)
            query = query.having(func.max(ChatSession.created_at) <= recent_date)
        
        # Order by last active
        query = query.order_by(desc("last_active"))
        
        # Apply pagination
        offset = (page - 1) * limit
        result = await db.execute(query.offset(offset).limit(limit))
        users = result.all()
        
        # Enhance user data with relative timestamps
        enhanced_users = []
        for user in users:
            user_dict = user._asdict()
            if user_dict["last_active"]:
                user_dict["last_active_relative"] = format_relative_time(user_dict["last_active"])
            enhanced_users.append(user_dict)
        
        return templates.TemplateResponse(
            "admin/users.html",
            {
                "request": request,
                "users": enhanced_users,
                "username": username,
                "page": page,
                "limit": limit
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Users page error: {str(e)}")

@router.get("/sessions", response_class=HTMLResponse)
async def admin_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin),
    user_id: Optional[str] = Query(None),
    manufacturer: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=10, le=100)
):
    """Enhanced session management with advanced filtering"""
    try:
        # Build base query
        query = select(ChatSession).order_by(desc(ChatSession.created_at))
        
        # Apply filters
        if user_id:
            query = query.where(ChatSession.user_id == user_id)
        if manufacturer:
            query = query.where(ChatSession.manufacturer == manufacturer)
        
        # Apply pagination
        offset = (page - 1) * limit
        result = await db.execute(query.offset(offset).limit(limit))
        sessions = result.scalars().all()
        
        # Get message counts and enhance session data
        sessions_with_counts = []
        for session in sessions:
            message_count = await db.scalar(
                select(func.count())
                .select_from(Message)
                .where(Message.session_id == session.id)
            )
            
            # Calculate session duration if completed
            duration = None
            if message_count > 0:
                first_msg = await db.scalar(
                    select(Message.timestamp)
                    .where(Message.session_id == session.id)
                    .order_by(Message.timestamp)
                    .limit(1)
                )
                last_msg = await db.scalar(
                    select(Message.timestamp)
                    .where(Message.session_id == session.id)
                    .order_by(desc(Message.timestamp))
                    .limit(1)
                )
                if first_msg and last_msg:
                    duration_seconds = (last_msg - first_msg).total_seconds()
                    duration = format_duration(duration_seconds)
            
            session_dict = {
                "session": session,
                "message_count": message_count,
                "duration": duration,
                "created_at_relative": format_relative_time(session.created_at)
            }
            sessions_with_counts.append(session_dict)
        
        return templates.TemplateResponse(
            "admin/sessions.html",
            {
                "request": request,
                "sessions": sessions_with_counts,
                "username": username,
                "page": page,
                "limit": limit
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sessions page error: {str(e)}")

@router.get("/api/stats", response_class=JSONResponse)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """API endpoint for real-time dashboard statistics"""
    try:
        stats = {
            "total_users": await db.scalar(
                select(func.count(func.distinct(ChatSession.user_id)))
            ),
            "total_sessions": await db.scalar(
                select(func.count(ChatSession.id))
            ),
            "total_messages": await db.scalar(
                select(func.count(Message.id))
            ),
            "active_today": await db.scalar(
                select(func.count(ChatSession.id))
                .where(func.date(ChatSession.created_at) == datetime.now().date())
            )
        }
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats API error: {str(e)}")

@router.get("/export/users")
async def export_users(
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin),
    format: str = Query("csv", regex="^(csv|json)$")
):
    """Export users data in CSV or JSON format"""
    try:
        result = await db.execute(
            select(
                ChatSession.user_id,
                func.count(ChatSession.id).label("session_count"),
                func.count(Message.id).label("message_count"),
                func.max(ChatSession.created_at).label("last_active"),
                func.min(ChatSession.created_at).label("created_at")
            )
            .select_from(ChatSession)
            .outerjoin(Message, Message.session_id == ChatSession.id)
            .group_by(ChatSession.user_id)
            .order_by(desc("last_active"))
        )
        users = result.all()
        
        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["User ID", "Sessions", "Messages", "Last Active", "Created"])
            
            for user in users:
                writer.writerow([
                    user.user_id,
                    user.session_count,
                    user.message_count or 0,
                    user.last_active.isoformat() if user.last_active else "",
                    user.created_at.isoformat() if user.created_at else ""
                ])
            
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=users.csv"}
            )
        else:  # JSON format
            users_data = [
                {
                    "user_id": user.user_id,
                    "session_count": user.session_count,
                    "message_count": user.message_count or 0,
                    "last_active": user.last_active.isoformat() if user.last_active else None,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                }
                for user in users
            ]
            
            return StreamingResponse(
                io.BytesIO(json.dumps(users_data, indent=2).encode()),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=users.json"}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")

@router.get("/export/sessions")
async def export_sessions(
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin),
    format: str = Query("csv", regex="^(csv|json)$"),
    ids: Optional[str] = Query(None)
):
    """Export sessions data with optional filtering by IDs"""
    try:
        query = select(ChatSession).order_by(desc(ChatSession.created_at))
        
        # Filter by specific session IDs if provided
        if ids:
            session_ids = ids.split(',')
            query = query.where(ChatSession.id.in_(session_ids))
        
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Session ID", "User ID", "Manufacturer", "Model", "Year", 
                "Created", "Message Count"
            ])
            
            for session in sessions:
                message_count = await db.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.session_id == session.id)
                )
                
                writer.writerow([
                    session.id,
                    session.user_id,
                    session.manufacturer,
                    session.model,
                    session.year,
                    session.created_at.isoformat(),
                    message_count
                ])
            
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=sessions.csv"}
            )
        else:  # JSON format
            sessions_data = []
            for session in sessions:
                message_count = await db.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.session_id == session.id)
                )
                
                sessions_data.append({
                    "id": session.id,
                    "user_id": session.user_id,
                    "manufacturer": session.manufacturer,
                    "model": session.model,
                    "year": session.year,
                    "created_at": session.created_at.isoformat(),
                    "message_count": message_count
                })
            
            return StreamingResponse(
                io.BytesIO(json.dumps(sessions_data, indent=2).encode()),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=sessions.json"}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")

@router.get("/sessions/{session_id}/details", response_class=HTMLResponse)
async def get_session_details(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """Get detailed session information for modal display"""
    try:
        # Get session
        session = await db.scalar(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get messages
        messages = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.timestamp)
        )
        messages = messages.scalars().all()
        
        # Generate HTML content for modal
        html_content = f"""
        <div class="session-details">
            <div class="row mb-3">
                <div class="col-md-6">
                    <strong>Session ID:</strong><br>
                    <code>{session.id}</code>
                </div>
                <div class="col-md-6">
                    <strong>User ID:</strong><br>
                    {session.user_id}
                </div>
            </div>
            <div class="row mb-3">
                <div class="col-md-4">
                    <strong>Vehicle:</strong><br>
                    {session.year} {session.manufacturer} {session.model}
                </div>
                <div class="col-md-4">
                    <strong>Created:</strong><br>
                    {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}
                </div>
                <div class="col-md-4">
                    <strong>Messages:</strong><br>
                    {len(messages)}
                </div>
            </div>
            <div class="messages-container" style="max-height: 400px; overflow-y: auto;">
                <h6>Conversation:</h6>
        """
        
        for msg in messages:
            role_class = "primary" if msg.role == "user" else "secondary"
            html_content += f"""
                <div class="message mb-2">
                    <div class="badge bg-{role_class} mb-1">{msg.role.title()}</div>
                    <div class="message-content p-2 border rounded">
                        {msg.content}
                    </div>
                    <small class="text-muted">{msg.timestamp.strftime('%H:%M:%S')}</small>
                </div>
            """
        
        html_content += """
            </div>
        </div>
        """
        
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session details error: {str(e)}")

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(verify_admin)
):
    """Delete a specific session and its messages"""
    try:
        # Delete messages first (foreign key constraint)
        await db.execute(
            select(Message).where(Message.session_id == session_id)
        )
        
        # Delete session
        session = await db.scalar(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        if session:
            await db.delete(session)
            await db.commit()
            return {"success": True, "message": "Session deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete error: {str(e)}")
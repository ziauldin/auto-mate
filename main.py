import os
import logging
import uuid
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Form, File, UploadFile, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func
from dotenv import load_dotenv
from typing import Dict
from starlette.middleware.sessions import SessionMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

# Local modules
from app.llm.diagnose_llm import DiagnoseLLM
from app.recommend.recommend import recommend_products
from app.database import get_db, engine, Base
from app.models import ChatSession, Message
from app.auth.google import router as auth_router, get_current_user, UserInfo

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ==================== Admin Setup ====================
security = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(
        credentials.username, 
        os.getenv("ADMIN_USERNAME", "admin")
    )
    correct_password = secrets.compare_digest(
        credentials.password,
        os.getenv("ADMIN_PASSWORD", "admin123")
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Create admin router
admin_router = APIRouter(prefix="/admin", tags=["admin"])

@admin_router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db), username: str = Depends(verify_admin)):
    # Get basic stats
    total_users = await db.scalar(select(func.count(func.distinct(ChatSession.user_id))))
    total_sessions = await db.scalar(select(func.count(ChatSession.id)))
    total_messages = await db.scalar(select(func.count(Message.id)))
    
    # Create a 'stats' dictionary to pass to the template
    stats = {
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_messages": total_messages
    }

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "stats": stats # Pass the 'stats' dictionary here
    })

@admin_router.get("/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: AsyncSession = Depends(get_db), username: str = Depends(verify_admin)):
    result = await db.execute(
        select(
            ChatSession.user_id,
            func.count(ChatSession.id).label("session_count"),
            func.max(ChatSession.created_at).label("last_active")
        )
        .group_by(ChatSession.user_id)
        .order_by(desc("last_active"))
    )
    
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "users": result.all()
    })

@admin_router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db), username: str = Depends(verify_admin)):
    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "username": username
    })

@admin_router.get("/analytics", response_class=HTMLResponse)
async def analytics_dashboard(request: Request, db: AsyncSession = Depends(get_db), username: str = Depends(verify_admin)):
    return templates.TemplateResponse("admin/analytics.html", {
        "request": request,
        "username": username
    })

@admin_router.get("/sessions", response_class=HTMLResponse)
async def admin_sessions(request: Request, db: AsyncSession = Depends(get_db), username: str = Depends(verify_admin)):
    result = await db.execute(select(ChatSession).order_by(desc(ChatSession.created_at)))
    sessions = result.scalars().all()
    
    sessions_with_counts = []
    for session in sessions:
        message_count = await db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.session_id == session.id)
        )
        sessions_with_counts.append({
            "session": session,
            "message_count": message_count
        })
    
    return templates.TemplateResponse("admin/sessions.html", {
        "request": request,
        "sessions": sessions_with_counts
    })

# ==================== Main App Setup ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database initialized")
    yield
    await engine.dispose()

app = FastAPI(title="Car Diagnostics API", lifespan=lifespan)

# Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "change-me-in-production"),
    max_age=3600,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost", "http://localhost:8000",
        "http://localhost:8500", "http://127.0.0.1:8500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/admin/static", StaticFiles(directory="app/admin/static"), name="admin_static")
templates = Jinja2Templates(directory=["templates", "app/admin/templates", "app/admin/templates/admin"])

# Include routers
app.include_router(auth_router)
app.include_router(admin_router)
diagnose_llm = DiagnoseLLM()

# ==================== Data Models ====================
class CarDetails(BaseModel):
    manufacturer: str
    model: str
    year: int

class ChatRequest(BaseModel):
    session_id: str
    message: str
    image_path: str = None

class TextSizeRequest(BaseModel):
    session_id: str
    size: str

# ==================== Helper Functions ====================
def utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ==================== Application Routes ====================
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/session")
async def create_new_session(
    car_details: CarDetails,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        session_id = str(uuid.uuid4())
        db_session = ChatSession(
            id=session_id,
            user_id=user.id,
            manufacturer=car_details.manufacturer,
            model=car_details.model,
            year=car_details.year,
            created_at=utcnow_naive()
        )
        db.add(db_session)
        await db.commit()

        db.add_all([
            Message(
                session_id=session_id,
                role="system",
                content=f"Vehicle: {car_details.year} {car_details.manufacturer} {car_details.model}",
                timestamp=utcnow_naive()
            ),
            Message(
                session_id=session_id,
                role="assistant",
                content=f"Hello! I'm ready to help with your {car_details.year} {car_details.manufacturer} {car_details.model}. What issues are you experiencing?",
                timestamp=utcnow_naive()
            )
        ])
        await db.commit()
        return {"session_id": session_id, "car_details": car_details}
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(
    chat_req: ChatRequest,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    try:
        # 1. Validate session
        result = await db.execute(select(ChatSession).where(ChatSession.id == chat_req.session_id))
        session = result.scalars().first()
        if not session or session.user_id != user.id:
            raise HTTPException(status_code=403, detail="Session not found or unauthorized")

        # 2. Load conversation history
        msg_result = await db.execute(
            select(Message).where(Message.session_id == session.id).order_by(Message.timestamp)
        )
        history = [{"role": msg.role, "content": msg.content} for msg in msg_result.scalars().all()]
        history.append({"role": "user", "content": chat_req.message})

        # 3. Determine which image to use
        image_path = chat_req.image_path or session.image_path

        # 4. Save user message to DB
        db.add(Message(
            session_id=session.id,
            role="user",
            content=chat_req.message,
            timestamp=utcnow_naive(),
            car_image=image_path
        ))
        await db.flush()

        # 5. Get LLM-based diagnosis
        diagnosis_text = await diagnose_llm.get_diagnosis(history, session, image_path)
        logger.info(f"[Diagnosis Text]: {diagnosis_text.strip()}")

        # 6. Generate recommendations only if relevant keywords exist
        products = recommend_products(diagnosis_text, top_k=3)
        logger.info(f"Returned {len(products)} recommended products.")

        # 7. Save assistant reply to DB
        db.add(Message(
            session_id=session.id,
            role="assistant",
            content=diagnosis_text,
            timestamp=utcnow_naive(),
            products=json.dumps(products) if products else None
        ))
        await db.commit()

        # 8. Return clean response
        return {
            "message": diagnosis_text,
            "products": products
        }

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error.")

@app.post("/api/upload-image")
async def upload_image(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        res = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = res.scalars().first()

        if not session or session.user_id != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        os.makedirs("static/uploads", exist_ok=True)
        file_path = f"static/uploads/{session_id}_{file.filename}"

        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save image path to session
        session.image_path = os.path.abspath(file_path)
        await db.commit()

        return {
            "success": True,
            "file_url": f"/{file_path}",
            "image_path": session.image_path
        }

    except Exception as e:
        logger.error(f"Upload image error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/set-text-size")
async def set_text_size(req: TextSizeRequest, db: AsyncSession = Depends(get_db), user: UserInfo = Depends(get_current_user)):
    try:
        res = await db.execute(select(ChatSession).where(ChatSession.id == req.session_id))
        session = res.scalars().first()
        if not session or session.user_id != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        session.text_size = req.size
        await db.commit()
        return {"success": True}
    except Exception as e:
        logger.error(f"Set text-size error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
async def get_history(user: UserInfo = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(ChatSession).where(ChatSession.user_id == user.id).order_by(desc(ChatSession.created_at)))
        sessions = res.scalars().all()
        history = []

        for sess in sessions:
            last_msg_res = await db.execute(select(Message).where(Message.session_id == sess.id).order_by(desc(Message.timestamp)).limit(1))
            last_msg = last_msg_res.scalars().first()
            msg_count = await db.scalar(select(func.count()).select_from(Message).where(Message.session_id == sess.id))

            history.append({
                "id": sess.id,
                "car_details": {"manufacturer": sess.manufacturer, "model": sess.model, "year": sess.year},
                "created_at": sess.created_at.isoformat() if sess.created_at else "",
                "last_message": last_msg.content if last_msg else "",
                "message_count": msg_count
            })

        return {"sessions": history}
    except Exception as e:
        logger.error(f"History error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history/{session_id}")
async def get_session_history(session_id: str, user: UserInfo = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = res.scalars().first()

        if not session or session.user_id != user.id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        msg_res = await db.execute(select(Message).where(Message.session_id == session.id).order_by(Message.timestamp))
        messages = msg_res.scalars().all()

        return {
            "id": session.id,
            "car_details": {"manufacturer": session.manufacturer, "model": session.model, "year": session.year},
            "created_at": session.created_at.isoformat(),
            "text_size": session.text_size,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "car_image": m.car_image,
                    "products": json.loads(m.products) if m.products else None
                } for m in messages
            ],
        }
    except Exception as e:
        logger.error(f"Session history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear-history")
async def clear_history(user: UserInfo = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(ChatSession).where(ChatSession.user_id == user.id))
        sessions = res.scalars().all()

        for sess in sessions:
            await db.delete(sess)
        await db.commit()
        return {"success": True}
    except Exception as e:
        logger.error(f"Clear history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8500)

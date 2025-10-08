import os
import csv
from fastapi import (
    FastAPI, Request, UploadFile, Form, File, HTTPException, status
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from google.cloud import firestore
from dotenv import load_dotenv
from gcs_utils import (
    upload_to_gcs,
    save_recording_metadata,
    search_recordings_by_text,
    get_next_unrecorded_text,
    mark_text_as_recorded,
    add_text_entries,
    get_recording_progress,
    ensure_user_text_exists,
    get_text_for_user,
    firestore_client,
)

# -------------------------------------------------
# Environment & App setup
# -------------------------------------------------
load_dotenv()
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "Anaya"))
templates = Jinja2Templates(directory="templates")

if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "youradmin@gmail.com")

# -------------------------------------------------
# Google OAuth configuration
# -------------------------------------------------
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# -------------------------------------------------
# Authentication middleware
# -------------------------------------------------
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = {"/login", "/auth", "/static", "/favicon.ico"}
    if any(request.url.path.startswith(path) for path in public_paths):
        return await call_next(request)

    user = request.session.get("user")
    if not user:
        print(f"⚠️ Unauthorized access to {request.url.path} — redirecting to /login")
        return RedirectResponse(url="/login")

    return await call_next(request)

# -------------------------------------------------
# Auth routes
# -------------------------------------------------
@app.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for("auth")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth")
async def auth(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = token.get("userinfo")
        if not user:
            print("⚠️ No user info returned from Google")
            return RedirectResponse(url="/login")
        request.session["user"] = dict(user)
        print(f"✅ Logged in user: {user['email']}")
        return RedirectResponse(url="/dashboard")
    except Exception as e:
        print(f"❌ Auth error: {e}")
        return RedirectResponse(url="/login")

@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/login")

# -------------------------------------------------
# Helper
# -------------------------------------------------
def get_current_user(request: Request):
    return request.session.get("user")

# -------------------------------------------------
# Core routes
# -------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home_redirect():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    next_text = get_text_for_user(user.get("name") or user.get("email"))
    stats = get_recording_progress()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "next_text": next_text, "stats": stats, "ADMIN_EMAIL": ADMIN_EMAIL},
    )

# -------------------------------------------------
# Audio upload API
# -------------------------------------------------
@app.post("/upload-audio/")
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    text: str = Form(...),
    text_id: str = Form(None)
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")

    data = await file.read()
    url = upload_to_gcs(data, file.filename, file.content_type)
    user_email = user.get("email")
    user_name = user.get("name") or user_email.split("@")[0].replace(".", " ").title()

    save_recording_metadata(
        user_email=user_email,
        user_name=user_name,
        audio_url=url,
        transcript=text
    )

    if text_id:
        mark_text_as_recorded(text_id)

    return {"audio_url": url, "text": text, "uploaded_by": user_name, "user_email": user_email}

# -------------------------------------------------
# Search API
# -------------------------------------------------
@app.get("/search")
async def search_api(query: str = ""):
    results = search_recordings_by_text(query) if query else []
    return {"results": results}

# -------------------------------------------------
# Admin routes
# -------------------------------------------------
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = get_current_user(request)
    if user["email"] != ADMIN_EMAIL:
        return HTMLResponse("<h3>Access denied: Admins only.</h3>", status_code=403)

    recordings = [
        doc.to_dict()
        for doc in firestore_client.collection("recordings")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .stream()
    ]

    return templates.TemplateResponse(
        "admin.html", {"request": request, "recordings": recordings, "user": user},
    )

# -------------------------------------------------
# Text import routes (Admin only)
# -------------------------------------------------
@app.get("/import-texts", response_class=HTMLResponse)
async def import_texts_page(request: Request):
    user = get_current_user(request)
    if user["email"] != ADMIN_EMAIL:
        return HTMLResponse("<h3>Access denied: Admins only.</h3>", status_code=403)
    return templates.TemplateResponse("import_texts.html", {"request": request, "message": None})

@app.post("/import-texts", response_class=HTMLResponse)
async def import_texts_upload(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    if user["email"] != ADMIN_EMAIL:
        return HTMLResponse("<h3>Access denied: Admins only.</h3>", status_code=403)

    content = await file.read()
    text_list = [row.strip() for row in content.decode("utf-8").splitlines() if row]
    add_text_entries(text_list)
    message = f"✅ Imported {len(text_list)} texts successfully."
    return templates.TemplateResponse("import_texts.html", {"request": request, "message": message})

# -------------------------------------------------
# Progress tracking (Admin)
# -------------------------------------------------
@app.get("/progress", response_class=HTMLResponse)
async def progress_page(request: Request):
    user = get_current_user(request)
    if user["email"] != ADMIN_EMAIL:
        return HTMLResponse("<h3>Access denied: Admins only.</h3>", status_code=403)

    stats = get_recording_progress()
    return templates.TemplateResponse("progress.html", {"request": request, "user": user, "stats": stats})

# -------------------------------------------------
# Next text API
# -------------------------------------------------
@app.get("/next-text")
async def next_text_api():
    next_text = get_next_unrecorded_text()
    return JSONResponse(next_text or {"text": None, "id": None})

@app.get("/record", response_class=HTMLResponse)
async def record_page(request: Request):
    user = get_current_user(request)
    ensure_user_text_exists(user.get("name") or user.get("email"))
    next_text = get_text_for_user(user.get("name") or user.get("email"))
    return templates.TemplateResponse("components/record_tab.html", {"request": request, "user": user, "next_text": next_text})

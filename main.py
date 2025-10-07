from fastapi import FastAPI, Request, Depends, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
from authlib.integrations.starlette_client import OAuth
import os

from gcs_utils import upload_audio_to_gcs, save_recording_metadata, get_texts_without_audio

app = FastAPI()

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "supersecret"))

# Templates and static directories
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Google OAuth setup
oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "youradmin@gmail.com")

# --- Authentication routes ---
@app.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for("auth")
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth")
async def auth(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user = token.get("userinfo")
    request.session["user"] = dict(user)
    return RedirectResponse(url="/dashboard")

@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/login")

# --- Main app routes ---
@app.get("/", response_class=HTMLResponse)
async def home_redirect():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": user, "ADMIN_EMAIL": ADMIN_EMAIL}
    )

# --- CSV Import Page ---
@app.get("/import-texts", response_class=HTMLResponse)
async def import_texts_page(request: Request):
    user = request.session.get("user")
    if not user or user["email"] != ADMIN_EMAIL:
        return HTMLResponse("<h3>Access denied: Admins only.</h3>", status_code=403)
    return templates.TemplateResponse("import_texts.html", {"request": request})

# --- Audio Upload API ---
@app.post("/upload-audio/")
async def upload_audio(request: Request, file: UploadFile, text: str = Form(...)):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    url = upload_audio_to_gcs(file)
    save_recording_metadata(user["email"], url, text)
    return RedirectResponse(url="/dashboard")

# --- Helper API for texts without audio ---
@app.get("/next-text")
async def next_text(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    text = get_texts_without_audio(user["email"])
    return {"text": text or "All recordings complete!"}

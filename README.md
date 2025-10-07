# 🎙️ Vaani – Voice Recording App

**Vaani** is a FastAPI-based web app that lets users log in with Google, record their voice, upload and store recordings in Google Cloud, and manage associated text transcripts.  
It includes a modern Tailwind + Alpine.js UI and an admin dashboard for managing imported text data.

---

## 🚀 Features

- 🔐 **Google Login** (OAuth 2.0)
- 🎤 **Voice Recording** via browser
- ☁️ **Cloud Uploads** (Google Cloud Storage)
- 📝 **Text Management** with CSV Import
- 🧩 **Tabbed Dashboard UI** (Record / Search / Progress / Admin)
- 👑 **Admin Tools** – view all recordings and import new texts
- 💾 **Firestore Storage** for metadata (user, text, audio URL)
- 💅 **Tailwind UI** with modern mobile-style layout

---

## 🗂️ Folder Structure



voice-app/
├── main.py # FastAPI app entrypoint
├── gcs_utils.py # Cloud Storage & Firestore utilities
├── config.py # Config & constants
├── requirements.txt # Dependencies
├── static/ # Optional static files (icons, css, js)
└── templates/
├── dashboard.html
├── import_texts.html
├── login.html
└── components/
├── record_tab.html
├── search_tab.html
├── progress_tab.html
└── admin_tab.html


---

## ⚙️ Setup Instructions

1️⃣ **Clone and install**
```bash
git clone git@github.com:mkstmp/vaani.git
cd vaani
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt


2️⃣ Create .env

GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
SESSION_SECRET=your_random_string
ADMIN_EMAIL=youremail@gmail.com
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json


3️⃣ Run the app

uvicorn main:app --reload


Visit 👉 http://127.0.0.1:8000

🌐 Deployment

You can deploy easily on:

Render → simple, free FastAPI hosting

Google Cloud Run → integrates directly with Firestore + GCS

Just set your .env values as environment variables in your deployment settings.
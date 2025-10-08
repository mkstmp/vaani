from google.cloud import storage
import uuid
from google.cloud import firestore
import json, os
from google.cloud import firestore
from google.oauth2 import service_account

BUCKET_NAME = "voice-app-audios"


creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if creds_json:
    creds = service_account.Credentials.from_service_account_info(json.loads(creds_json))
    firestore_client = firestore.Client(credentials=creds, project=creds.project_id, database="audio-database")
else:
    firestore_client = firestore.Client(database="audio-database")


def upload_to_gcs(file_data, filename, content_type):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob_name = f"uploads/{uuid.uuid4()}_{filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(file_data, content_type=content_type)
    blob.make_public()
    return blob.public_url

def save_recording_metadata(user_email, audio_url, transcript, user_name=None):
    doc_ref = firestore_client.collection("recordings").document()
    doc_ref.set({
        "user_email": user_email,
        "user_name": user_name,
        "audio_url": audio_url,
        "transcript": transcript,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })


def search_recordings_by_text(query_text: str):
    """Search Firestore recordings that contain the given text."""
    results = []
    recordings_ref = firestore_client.collection("recordings")

    # Fetch all docs (simple version)
    docs = recordings_ref.stream()
    for doc in docs:
        data = doc.to_dict()
        if query_text.lower() in data.get("transcript", "").lower():
            results.append(data)
    return results

def get_next_unrecorded_text():
    """Fetch the next text that does not yet have an audio recording."""
    docs = firestore_client.collection("texts").where("recorded", "==", False).limit(1).stream()
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None


def mark_text_as_recorded(text_id: str):
    """Mark a text as recorded after the user uploads audio."""
    firestore_client.collection("texts").document(text_id).update({"recorded": True})


def add_text_entries(text_list):
    """Add multiple new texts to Firestore."""
    texts_ref = firestore_client.collection("texts")
    for t in text_list:
        texts_ref.add({"text": t, "recorded": False})

def get_recording_progress():
    """Return counts for total, recorded, and unrecorded texts."""
    texts_ref = firestore_client.collection("texts")
    all_docs = list(texts_ref.stream())
    total = len(all_docs)
    recorded = sum(1 for d in all_docs if d.to_dict().get("recorded"))
    pending = total - recorded

    return {
        "total": total,
        "recorded": recorded,
        "pending": pending,
        "percent": (recorded / total * 100) if total > 0 else 0
    }

def ensure_user_text_exists(user_name: str):
    """Add user's name to texts if it's not already present."""
    texts_ref = firestore_client.collection("texts")
    query = texts_ref.where("text", "==", user_name).limit(1).stream()
    existing = next(query, None)
    if not existing:
        texts_ref.add({"text": user_name, "recorded": False})


def get_text_for_user(user_name: str):
    """Return user's own text if it exists and is not recorded, else next unrecorded text."""
    texts_ref = firestore_client.collection("texts")

    # Check if user's name exists and not recorded
    user_texts = texts_ref.where("text", "==", user_name).where("recorded", "==", False).limit(1).stream()
    for doc in user_texts:
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    # Otherwise fallback to the next unrecorded text
    from gcs_utils import get_next_unrecorded_text
    return get_next_unrecorded_text()

import os
from dotenv import load_dotenv
from google.cloud import storage, firestore

load_dotenv()

# Google Cloud setup
GCP_BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

storage_client = storage.Client()
firestore_client = firestore.Client()

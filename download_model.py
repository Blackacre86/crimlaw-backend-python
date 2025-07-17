# download_model.py
# ----------------------------------
# This script downloads the model once during build
# so runtime start-up is fast.

from sentence_transformers import SentenceTransformer

# Download and cache the model
SentenceTransformer("BAAI/bge-small-en-v1.5")

print("Model downloaded successfully.")

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found. Please check your .env file.")

# Global Settings
MODEL_NAME = "llama-3.3-70b-versatile"
DATA_DIR = "data"
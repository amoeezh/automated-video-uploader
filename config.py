import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
META_PAGE_ACCESS_TOKEN = os.environ["META_PAGE_ACCESS_TOKEN"]
IG_USER_ID = os.environ["IG_USER_ID"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]

WORK_DIR = "work"
STATE_FILE = "state/history.json"
TOPICS_FILE = "topics.json"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
MAX_SENTENCES = 8
GRAPH_API_VERSION = "v21.0"

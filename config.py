import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
META_PAGE_ACCESS_TOKEN = os.environ["META_PAGE_ACCESS_TOKEN"]
IG_USER_ID = os.environ["IG_USER_ID"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]

# Optional: YouTube upload is skipped (not fatal) if these aren't set
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

WORK_DIR = "work"
STATE_FILE = "state/history.json"
TOPICS_FILE = "topics.json"

FACTS_WORK_DIR = "facts_work"
FACTS_STATE_FILE = "state/facts_history.json"
FACTS_TOPICS_FILE = "facts_topics.json"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
MAX_SENTENCES = 9
GRAPH_API_VERSION = "v21.0"

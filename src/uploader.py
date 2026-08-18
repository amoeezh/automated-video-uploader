import os
import time
import uuid

import requests

import config
from retry import with_retry

GITHUB_API = "https://api.github.com"


def _gh_headers():
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def publish_video_publicly(video_path: str) -> str:
    """Upload the rendered video as a GitHub Release asset and return a public URL."""
    owner_repo = config.GITHUB_REPOSITORY
    tag = f"video-{uuid.uuid4().hex[:10]}"

    def create_release():
        resp = requests.post(
            f"{GITHUB_API}/repos/{owner_repo}/releases",
            headers=_gh_headers(),
            json={"tag_name": tag, "name": tag, "draft": False, "prerelease": False},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    release = with_retry(create_release, attempts=3, delay=10, label="GitHub release creation")
    upload_url = release["upload_url"].split("{")[0]
    filename = os.path.basename(video_path)

    def upload_asset():
        with open(video_path, "rb") as f:
            resp = requests.post(
                upload_url,
                headers={**_gh_headers(), "Content-Type": "video/mp4"},
                params={"name": filename},
                data=f,
                timeout=300,
            )
        resp.raise_for_status()
        return resp.json()

    upload = with_retry(upload_asset, attempts=3, delay=15, label="GitHub release asset upload")
    video_url = upload["browser_download_url"]
    _wait_until_url_ready(video_url)
    return video_url


def _wait_until_url_ready(url, attempts=20, delay=10):
    """GitHub's release-asset CDN can take a while to start serving a just-uploaded
    file, longer for bigger files. Instagram fetches video_url itself, so it must
    already be publicly reachable before we hand it over. Uses GET (not HEAD) since
    the signed redirect target doesn't reliably support HEAD."""
    last_status = None
    for _ in range(attempts):
        try:
            with requests.get(url, stream=True, allow_redirects=True, timeout=20) as resp:
                last_status = resp.status_code
                if resp.status_code == 200:
                    return
        except requests.RequestException as exc:
            last_status = str(exc)
        time.sleep(delay)
    raise RuntimeError(f"Video URL never became reachable (last status: {last_status}): {url}")


def _graph_url(path):
    return f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{path}"


def upload_to_instagram(video_url: str, caption: str, hashtags: list[str]) -> str:
    full_caption = caption.strip()
    if hashtags:
        full_caption += "\n\n" + " ".join(f"#{tag.lstrip('#')}" for tag in hashtags)

    def create_container():
        resp = requests.post(
            _graph_url(f"{config.IG_USER_ID}/media"),
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": full_caption,
                "access_token": config.META_PAGE_ACCESS_TOKEN,
            },
            timeout=60,
        )
        if not resp.ok:
            raise RuntimeError(f"Instagram container creation failed: {resp.status_code} {resp.text}")
        return resp.json()["id"]

    creation_id = with_retry(create_container, attempts=3, delay=15, label="Instagram container creation")

    status = "IN_PROGRESS"
    for _ in range(45):
        status_resp = requests.get(
            _graph_url(creation_id),
            params={"fields": "status_code", "access_token": config.META_PAGE_ACCESS_TOKEN},
            timeout=30,
        )
        status_resp.raise_for_status()
        status = status_resp.json()["status_code"]
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram failed to process video container {creation_id}")
        time.sleep(10)
    else:
        raise TimeoutError(f"Instagram container {creation_id} did not finish processing in time")

    if os.environ.get("DRY_RUN") == "true":
        return f"DRY_RUN_OK (container {creation_id} validated, not published)"

    def publish():
        resp = requests.post(
            _graph_url(f"{config.IG_USER_ID}/media_publish"),
            data={"creation_id": creation_id, "access_token": config.META_PAGE_ACCESS_TOKEN},
            timeout=60,
        )
        if not resp.ok:
            raise RuntimeError(f"Instagram publish failed: {resp.status_code} {resp.text}")
        return resp.json()["id"]

    return with_retry(publish, attempts=3, delay=15, label="Instagram publish")


YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def youtube_configured() -> bool:
    return bool(config.YOUTUBE_CLIENT_ID and config.YOUTUBE_CLIENT_SECRET and config.YOUTUBE_REFRESH_TOKEN)


def _youtube_access_token():
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": config.YOUTUBE_CLIENT_ID,
            "client_secret": config.YOUTUBE_CLIENT_SECRET,
            "refresh_token": config.YOUTUBE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload_to_youtube(video_path: str, title: str, caption: str, hashtags: list[str]) -> str:
    """Upload the same rendered video as a YouTube Short."""
    description = caption.strip()
    if hashtags:
        description += "\n\n" + " ".join(f"#{tag.lstrip('#')}" for tag in hashtags)
    description += "\n\n#Shorts"

    access_token = _youtube_access_token()
    is_dry_run = os.environ.get("DRY_RUN") == "true"

    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": [tag.lstrip("#") for tag in hashtags][:500],
            "categoryId": "24",
        },
        "status": {
            "privacyStatus": "private" if is_dry_run else "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    def init_upload():
        resp = requests.post(
            YOUTUBE_UPLOAD_URL,
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=metadata,
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"YouTube upload session init failed: {resp.status_code} {resp.text}")
        return resp.headers["Location"]

    upload_url = with_retry(init_upload, attempts=3, delay=10, label="YouTube upload session init")

    def do_upload():
        with open(video_path, "rb") as f:
            resp = requests.put(
                upload_url,
                headers={"Content-Type": "video/mp4"},
                data=f,
                timeout=600,
            )
        if not resp.ok:
            raise RuntimeError(f"YouTube video upload failed: {resp.status_code} {resp.text}")
        return resp.json()

    result = with_retry(do_upload, attempts=3, delay=15, label="YouTube video upload")
    return result["id"]

import os
import time
import uuid

import requests

import config

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

    create_resp = requests.post(
        f"{GITHUB_API}/repos/{owner_repo}/releases",
        headers=_gh_headers(),
        json={"tag_name": tag, "name": tag, "draft": False, "prerelease": False},
        timeout=30,
    )
    create_resp.raise_for_status()
    release = create_resp.json()
    upload_url = release["upload_url"].split("{")[0]

    filename = os.path.basename(video_path)
    with open(video_path, "rb") as f:
        upload_resp = requests.post(
            upload_url,
            headers={**_gh_headers(), "Content-Type": "video/mp4"},
            params={"name": filename},
            data=f,
            timeout=300,
        )
    upload_resp.raise_for_status()
    video_url = upload_resp.json()["browser_download_url"]
    _wait_until_url_ready(video_url)
    return video_url


def _wait_until_url_ready(url, attempts=10, delay=3):
    """GitHub's release-asset CDN can take a few seconds to start serving a
    just-uploaded file. Instagram fetches video_url itself, so it must already
    be publicly reachable before we hand it over."""
    last_status = None
    for _ in range(attempts):
        try:
            resp = requests.head(url, allow_redirects=True, timeout=15)
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

    container_resp = requests.post(
        _graph_url(f"{config.IG_USER_ID}/media"),
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": full_caption,
            "access_token": config.META_PAGE_ACCESS_TOKEN,
        },
        timeout=60,
    )
    if not container_resp.ok:
        raise RuntimeError(f"Instagram container creation failed: {container_resp.status_code} {container_resp.text}")
    creation_id = container_resp.json()["id"]

    status = "IN_PROGRESS"
    for _ in range(30):
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

    publish_resp = requests.post(
        _graph_url(f"{config.IG_USER_ID}/media_publish"),
        data={"creation_id": creation_id, "access_token": config.META_PAGE_ACCESS_TOKEN},
        timeout=60,
    )
    if not publish_resp.ok:
        raise RuntimeError(f"Instagram publish failed: {publish_resp.status_code} {publish_resp.text}")
    return publish_resp.json()["id"]

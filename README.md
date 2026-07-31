# Daily Instagram Reel Automation

Fully automated daily pipeline, $0 running cost:

```
Gemini (free) writes script
      -> Groq/Llama (free) fact-checks & tightens it
      -> edge-tts (free) narrates it + Pexels (free) stock clips + captions -> rendered vertical video
      -> video published as a GitHub Release asset (free public URL)
      -> Instagram Graph API (free) publishes it as a Reel
```

Runs daily via a GitHub Actions scheduled workflow. GitHub Actions is free with **unlimited
minutes on public repositories**, so keep this repo public.

Note on scope: this does not use Flow. Flow has no public API, so driving it automatically
would mean scripting its web UI, which is fragile and against its terms of use. Everything
here uses official free APIs instead, which is what makes daily unattended runs sustainable.

## What you need to do once (can't be skipped — these require your own accounts)

### 1. Free API keys (5 minutes total)

| Service | Used for | Get a free key |
|---|---|---|
| Google AI Studio (Gemini) | script writing | https://aistudio.google.com/apikey |
| Groq | script review/fact-check | https://console.groq.com/keys |
| Pexels | stock video clips | https://www.pexels.com/api/ |

### 2. Instagram + Meta setup (the only genuinely fiddly part, ~15-20 minutes, one time)

1. In the Instagram app: Settings → Account type → switch to **Professional** (Creator or Business).
2. Link the account to a **Facebook Page** you control (create one if needed): Instagram
   Settings → "Linked accounts", or from the Facebook Page's settings → "Linked accounts".
3. Go to https://developers.facebook.com/apps → **Create App** → type **Business**.
4. In the app dashboard, add the **Instagram** product (Instagram API setup / Instagram Graph API).
5. Under **App roles → Instagram testers**, add your own Instagram account, then open the
   Instagram app → Settings → Apps and Websites → **Tester Invites** → accept it.
   (This lets your own account publish via the API without needing Meta's App Review process.)
6. Open **Graph API Explorer** (developers.facebook.com/tools/explorer), select your app, and
   generate a User Access Token with these permissions: `instagram_basic`,
   `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`.
7. Exchange it for a long-lived token, then fetch your Page Access Token:
   - `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=<APP_ID>&client_secret=<APP_SECRET>&fb_exchange_token=<SHORT_LIVED_TOKEN>`
   - `GET /me/accounts?access_token=<LONG_LIVED_USER_TOKEN>` → copy the Page's `access_token`.
     This is your `META_PAGE_ACCESS_TOKEN`.
8. Get your Instagram business account id:
   - `GET /{page-id}?fields=instagram_business_account&access_token=<PAGE_ACCESS_TOKEN>`
   - The returned id is your `IG_USER_ID`.

Page tokens derived this way generally don't expire on a fixed schedule, but Meta can require
re-generating them occasionally — if the workflow starts failing on the Instagram step, redo
steps 6-8.

### 3. Push this repo to GitHub and add secrets

```bash
cd ig-video-automation
git add -A
git commit -m "Initial automation pipeline"
gh repo create ig-video-automation --public --source=. --remote=origin --push
# or create the repo manually on github.com and: git remote add origin <url> && git push -u origin main
```

Then in the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**,
add:
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `PEXELS_API_KEY`
- `META_PAGE_ACCESS_TOKEN`
- `IG_USER_ID`

(`GITHUB_TOKEN` is provided automatically by Actions — don't add it manually.)

### 4. Test before trusting the schedule

Go to the repo's **Actions** tab → "Daily Instagram Reel" → **Run workflow** to trigger it
manually. Check the run logs and confirm the Reel actually appears on Instagram before letting
the cron run unattended. After that, it runs automatically every day at 14:00 UTC (edit the
`cron:` line in `.github/workflows/daily.yml` to change the time).

## Local testing (optional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the keys above; GITHUB_TOKEN needs a personal access token
                       # with 'repo' scope for local testing of the release-upload step
PYTHONPATH=".:src" python src/pipeline.py
```

## Things worth knowing

- **Content style**: stock footage + AI narration + captions, in the "did you know" faceless
  Reels style. It's a real, common format — not spammy by default — but keep an eye on the
  first week of output for tone/quality.
- **Avoiding repeats**: `state/history.json` tracks previously used titles so Gemini avoids
  repeating the same idea; `topics.json` is the rotating list of content pillars — edit it to
  change your channel's niche.
- **Monetization**: Instagram's in-stream/Reels bonus programs have their own eligibility
  requirements (originality, region, standing) that this pipeline doesn't guarantee — it only
  handles the content + posting.
- **Rate/quota limits**: Gemini, Groq, and Pexels free tiers all have daily request caps. One
  video/day uses a tiny fraction of any of them.

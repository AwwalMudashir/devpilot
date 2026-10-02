import os
import httpx
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
BASE_URL = "https://api.github.com"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2026-03-10",
}

async def github_get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{BASE_URL}{path}", headers=HEADERS, params=params
        )
        response.raise_for_status()
        return response.json()



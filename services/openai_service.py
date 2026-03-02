import asyncio
import logging
import time
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_LEN = 1500
MAX_RETRIES = 3
MIN_REQUEST_INTERVAL = 3.0


class OpenAIService:
    def __init__(self, api_key: str, system_prompt: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._system_prompt = system_prompt
        self._last_request_time: float = 0.0

    async def _rate_limit_wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)

    async def generate_proposal(self, project_title: str, project_description: str) -> str:
        description = project_description[:MAX_DESCRIPTION_LEN]

        for attempt in range(MAX_RETRIES):
            try:
                await self._rate_limit_wait()
                self._last_request_time = time.monotonic()

                response = await self._client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": self._system_prompt},
                        {
                            "role": "user",
                            "content": (
                                f"Project title: {project_title}\n\n"
                                f"Project description: {description}"
                            ),
                        },
                    ],
                    max_tokens=500,
                    temperature=0.7,
                )
                content = response.choices[0].message.content
                del response
                return content or "Failed to generate proposal."
            except asyncio.CancelledError:
                raise
            except Exception as e:
                delay = 2 ** (attempt + 1)
                logger.warning(
                    "OpenAI API error (attempt %d/%d): %s — retrying in %ds",
                    attempt + 1, MAX_RETRIES, e, delay,
                )
                if attempt == MAX_RETRIES - 1:
                    return f"Error generating proposal: {e}"
                await asyncio.sleep(delay)
        return "Error generating proposal."

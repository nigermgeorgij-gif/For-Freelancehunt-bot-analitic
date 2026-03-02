import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self, api_key: str, system_prompt: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._system_prompt = system_prompt

    async def generate_proposal(self, project_title: str, project_description: str) -> str:
        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Project title: {project_title}\n\n"
                            f"Project description: {project_description}"
                        ),
                    },
                ],
                max_tokens=500,
                temperature=0.7,
            )
            content = response.choices[0].message.content
            return content or "Failed to generate proposal."
        except Exception as e:
            logger.exception("OpenAI API error: %s", e)
            return f"Error generating proposal: {e}"

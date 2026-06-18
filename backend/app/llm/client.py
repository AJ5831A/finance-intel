import time
from google import genai
from google.genai import types
from app.config import settings
from app.llm.schema import to_gemini_schema


def _coerce(schema, resp):
    """Turn a Gemini response into a validated instance of `schema`."""
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, schema):
        return parsed
    if isinstance(parsed, dict):
        return schema.model_validate(parsed)
    text = getattr(resp, "text", None)
    if text:
        return schema.model_validate_json(text)
    raise ValueError("Gemini returned no parsable structured output")


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 max_retries: int = 3):
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)
        self.model = model or settings.gemini_model
        self.max_retries = max_retries

    def generate_structured(self, schema, prompt: str, temperature: float = 0.1):
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=to_gemini_schema(schema),
            temperature=temperature,
        )
        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.models.generate_content(
                    model=self.model, contents=prompt, config=config)
                return _coerce(schema, resp)
            except Exception as e:  # noqa: BLE001 - retry transient/parse errors
                last_err = e
                time.sleep(0.5 * (2 ** attempt))
        raise RuntimeError(f"Gemini call failed after {self.max_retries} retries: {last_err}")

    def generate_text(self, prompt: str, temperature: float = 0.3) -> str:
        """Free-form (non-schema) generation, e.g. conversational follow-up answers.
        Higher default temperature than extraction since answers are prose, not data."""
        config = types.GenerateContentConfig(temperature=temperature)
        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.models.generate_content(
                    model=self.model, contents=prompt, config=config)
                text = getattr(resp, "text", None)
                if text:
                    return text
                raise ValueError("Gemini returned no text")
            except Exception as e:  # noqa: BLE001 - retry transient errors
                last_err = e
                time.sleep(0.5 * (2 ** attempt))
        raise RuntimeError(f"Gemini call failed after {self.max_retries} retries: {last_err}")

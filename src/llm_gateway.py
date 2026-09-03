import re
import json
from google import genai
from google.genai import types
from groq import Groq
import src.config as config

def clean_json_response(raw_text: str) -> dict:
    """Strips Markdown fences and safely parses JSON."""
    cleaned = re.sub(r"^```(?:json)?\n?", "", raw_text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned.strip())

class LLMGateway:
    def __init__(self):
        self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.groq_client = Groq(api_key=config.GROQ_API_KEY)

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> dict:
        # Tier 1: Gemini 3.8 Flash
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    response_mime_type="application/json"
                )
            )
            return clean_json_response(response.text)
        except Exception as e:
            print(f"[LLM Gateway] Gemini failed ({e}). Falling back to Groq Llama-3.3-70b...")

        # Tier 2: Groq Llama-3.3-70B
        try:
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            return clean_json_response(completion.choices[0].message.content)
        except Exception as e:
            raise RuntimeError(f"All LLM tiers exhausted: {e}")

import re
import json
import time
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
        
        # Resilient model priority cascades
        self.gemini_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        self.groq_models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> dict:
        # Tier 1: Gemini with retries and model cascade
        for model in self.gemini_models:
            for attempt in range(3):
                try:
                    response = self.gemini_client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=temperature,
                            response_mime_type="application/json"
                        )
                    )
                    return clean_json_response(response.text)
                except Exception as e:
                    err_str = str(e)
                    if "503" in err_str or "429" in err_str:
                        wait_sec = (attempt + 1) * 3
                        print(f"[LLM Gateway] {model} busy (503/429). Retrying in {wait_sec}s...")
                        time.sleep(wait_sec)
                        continue
                    print(f"[LLM Gateway] {model} failed: {e}. Trying next option...")
                    break

        # Tier 2: Groq with supported model cascade
        print("[LLM Gateway] Gemini exhausted. Falling back to Groq...")
        for model in self.groq_models:
            try:
                completion = self.groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
                return clean_json_response(completion.choices[0].message.content)
            except Exception as e:
                print(f"[LLM Gateway] Groq model {model} failed: {e}. Trying next...")

        raise RuntimeError("All LLM providers and fallback tiers failed.")

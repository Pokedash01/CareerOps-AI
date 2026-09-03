import re
import json
import time
from google import genai
from google.genai import types
from groq import Groq
import src.config as config

def clean_json_response(raw_text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\n?", "", raw_text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned.strip())

class LLMGateway:
    def __init__(self):
        self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.groq_client = Groq(api_key=config.GROQ_API_KEY)
        self.gemini_model = "gemini-3.6-flash"
        # Verified active models from runner execution logs
        self.groq_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> dict:
        # Tier 1: Gemini 3.6 Flash with Exponential Backoff
        for attempt in range(4):
            try:
                response = self.gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        response_mime_type="application/json"
                    )
                )
                return clean_json_response(response.text)
            except Exception as e:
                err = str(e)
                if "503" in err or "429" in err:
                    wait_sec = (attempt + 1) * 3
                    print(f"[LLM Gateway] Gemini {self.gemini_model} busy (503/429). Retrying in {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue
                print(f"[LLM Gateway] Gemini {self.gemini_model} failed: {e}")
                break

        # Tier 2: Groq (Verified Production Models)
        print("[LLM Gateway] Falling back to verified Groq models...")
        for model in self.groq_models:
            try:
                completion = self.groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    max_tokens=2048
                )
                return clean_json_response(completion.choices[0].message.content)
            except Exception as e:
                print(f"[LLM Gateway] Groq {model} failed: {e}. Trying next...")

        raise RuntimeError("All LLM providers and fallbacks failed.")

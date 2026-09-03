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
        self.gemini_model = "gemini-2.5-flash"
        self.groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> dict:
        # Tier 1: Gemini
        for attempt in range(3):
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
                    time.sleep((attempt + 1) * 2)
                    continue
                break

        # Tier 2: Groq (Strictly Production Llama Models)
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
                print(f"[LLM Gateway] Groq {model} failed: {e}")

        raise RuntimeError("All LLM providers failed.")

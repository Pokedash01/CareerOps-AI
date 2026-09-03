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
        self.gemini_model = "gemini-3.6-flash"

    def _get_active_groq_models(self) -> list[str]:
        """Dynamically queries Groq to find currently active chat models."""
        try:
            model_list = self.groq_client.models.list()
            # Filter out whisper, tts, and guardrail models
            chat_models = [
                m.id for m in model_list.data 
                if not any(x in m.id.lower() for x in ["whisper", "guard", "vision", "tts", "embed"])
            ]
            return chat_models
        except Exception as e:
            print(f"[LLM Gateway] Could not fetch dynamic Groq model list: {e}")
            return []

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> dict:
        # Tier 1: Gemini 3.6 Flash with retry backoff
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
                err_str = str(e)
                if "503" in err_str or "429" in err_str:
                    wait_sec = (attempt + 1) * 3
                    print(f"[LLM Gateway] Gemini {self.gemini_model} busy (503/429). Retrying in {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue
                print(f"[LLM Gateway] Gemini {self.gemini_model} failed: {e}.")
                break

        # Tier 2: Dynamic Groq Fallback
        print("[LLM Gateway] Gemini exhausted. Falling back to active Groq models...")
        available_groq_models = self._get_active_groq_models()
        
        for model_id in available_groq_models:
            try:
                print(f"[LLM Gateway] Trying Groq model: {model_id}")
                completion = self.groq_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
                return clean_json_response(completion.choices[0].message.content)
            except Exception as e:
                print(f"[LLM Gateway] Groq model {model_id} failed: {e}. Trying next...")

        raise RuntimeError("All LLM providers and dynamic fallback tiers failed.")

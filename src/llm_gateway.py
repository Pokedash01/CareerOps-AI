import os
from google import genai
from google.genai import types
from groq import Groq
import src.config as config

class LLMGateway:
    def __init__(self):
        self.gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.groq_client = Groq(api_key=config.GROQ_API_KEY)

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.2) -> str:
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    response_mime_type="application/json"
                )
            )
            return response.text
        except Exception as e:
            print(f"[Warning] Gemini API failed: {e}. Falling back to Groq...")
            completion = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            return completion.choices[0].message.content

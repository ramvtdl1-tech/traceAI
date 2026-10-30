"""Make one small live completion; print status only, never keys or response text."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
key = os.getenv('NEBIUS_API_KEY', '').strip()
model = os.getenv('NEBIUS_MODEL', '').strip()
if not key or not model:
    print('Missing NEBIUS_API_KEY or NEBIUS_MODEL.')
    sys.exit(1)
try:
    with OpenAI(api_key=key, base_url=os.getenv('NEBIUS_BASE_URL', 'https://api.tokenfactory.nebius.com/v1/'),
                timeout=30.0, max_retries=0) as client:
        result = client.chat.completions.create(
            model=model, messages=[{'role': 'user', 'content': 'Reply with a short greeting.'}],
            max_tokens=256, temperature=0.6,
        )
    if not result.choices or not (result.choices[0].message.content or '').strip():
        print('FAIL: provider returned no visible response; choose a compatible chat model.')
        sys.exit(1)
    print('PASS: configured Nebius key, model, and endpoint returned a real chat response.')
except Exception as error:
    print('FAIL:', type(error).__name__, 'status:', getattr(error, 'status_code', 'unavailable'))
    sys.exit(1)

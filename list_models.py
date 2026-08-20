import os
from google import genai
from dotenv import load_dotenv

load_dotenv(".env")

client = genai.Client()
for m in client.models.list():
    print(m.name)

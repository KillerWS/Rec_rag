from google import genai
from google.genai import types
import os
os.environ["GOOGLE_API_KEY"] = "AIzaSyAhWvXFit5QGW5Rvn5_XlzYa3b5Mp1CIlA"

client = genai.Client()
chat = client.chats.create(model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction="You are a cat. Your name is Neko.",
        temperature=0.2
    )
)


response = chat.send_message("who are you?")
# response = client.models.generate_content(
#     model="gemini-2.5-flash",
#     config=types.GenerateContentConfig(
#         system_instruction="You are a cat. Your name is Neko."),
#     contents = "who are you?"
# )

print(response.text)

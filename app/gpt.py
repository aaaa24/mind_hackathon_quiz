from openai import OpenAI
import os


ai_client = OpenAI(
    api_key=os.getenv('API_KEY'),
    base_url=os.getenv('BASE_URL')
)


def gpt_request(system, text):
    messages = [
        {'role': 'system',
         'content': system
         },
        {
            'role': 'user',
            'content': text
        }]
    response = ai_client.chat.completions.create(
        model='gemini-2.5-flash-lite',
        messages=messages,
        temperature=0.8
    )
    text = response.choices[0].message.content

    return text

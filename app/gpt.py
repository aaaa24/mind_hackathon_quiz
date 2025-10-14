from openai import OpenAI

ai_client = OpenAI(
    api_key='AIzaSyABja4aT9kNSCUbRVl6GP3Pvsk2lRHw8DA',
    base_url='https://my-openai-gemini-demo.vercel.app/v1/'
)


def gpt_request(text):
    messages = [{
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

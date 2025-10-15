from openai import OpenAI
import os
import uuid
import re
import json
from app.models import Question
import random

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


def get_gpt_questions(count_questions, category_ids):
    if len(category_ids) == 1:
        system = "Необходимо придумать n вопросов на тематики: topics по запросу пользователей. Вернуть нужно только список словарей в формате [{'text': (Текст вопроса),'options': {[(ответ_1), (ответ_2), (ответ_3), (ответ_4)]}, 'correct_answer': (правильный ответ), 'time_limit': (Ограничение времени на вопрос от 30 до 60)}]."
        user_text = f"n = {count_questions}, topics = Любая тематика на твое усмотрение"
    else:
        category_ids.remove(os.getenv('GPT_CATEGORY_ID'))
        system = "Необходимо придумать n вопросов на тематики: topics по запросу пользователей. Вернуть нужно только список словарей в формате [{'text': (Текст вопроса),'options': {[(ответ_1), (ответ_2), (ответ_3), (ответ_4)]}, 'correct_answer': (правильный ответ), 'time_limit': (Ограничение времени на вопрос от 30 до 60)}]."
        user_text = f"n = {count_questions}, topics = {category_ids}"
    try:
        data = gpt_request(system, user_text)
        pattern = r'\[[\s\S]*\]'
        match = re.search(pattern, data)
        if match:
            json_string = match.group()
            data = json.loads(json_string)
        questions = []
        if data:
            for question in data:
                options = question['options']
                random.shuffle(options)
                questions.append(
                    Question(id=str(uuid.uuid4()),
                             text=question['text'],
                             options=options,
                             correct_answer=question['correct_answer'],
                             time_limit=question['time_limit'],
                             category_id=os.getenv('GPT_CATEGORY_ID')))
            return {'success': True, 'questions': questions}
        else:
            return {'success': False, 'questions': None}
    except Exception as e:
        print(e)
        return {'success': False, 'questions': None}

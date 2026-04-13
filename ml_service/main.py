from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="ML Service for Home AI")

FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class TaskRequest(BaseModel):
    task_title: str


class SubtasksResponse(BaseModel):
    subtasks: list[str]


def call_yandex_gpt(prompt: str) -> str:
    """Вызов YandexGPT API"""
    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "Content-Type": "application/json"
    }
    
    body = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": 500
        },
        "messages": [
            {
                "role": "system",
                "text": "Ты — помощник по планированию домашних дел. Разбивай сложные задачи на 3-5 простых подзадач. Отвечай только списком подзадач, каждая с новой строки, без нумерации."
            },
            {
                "role": "user",
                "text": f"Разбей задачу '{prompt}' на подзадачи."
            }
        ]
    }
    
    response = requests.post(YANDEX_URL, headers=headers, json=body)
    
    if response.status_code != 200:
        raise Exception(f"YandexGPT error: {response.text}")
    
    result = response.json()
    return result["result"]["alternatives"][0]["message"]["text"]


@app.post("/generate-subtasks/", response_model=SubtasksResponse)
async def generate_subtasks(request: TaskRequest):
    """Генерация подзадач для сложной задачи"""
    try:
        response_text = call_yandex_gpt(request.task_title)
        
        # Разбиваем ответ на строки и убираем пустые
        subtasks = [line.strip() for line in response_text.split('\n') if line.strip()]
        
        # Ограничиваем до 5 подзадач
        subtasks = subtasks[:5]
        
        return SubtasksResponse(subtasks=subtasks)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
import requests
import json
import os
from pathlib import Path

from dataclasses import dataclass, field



@dataclass()
class AppConfig:
    # env: str
    # debug: bool
    work_dir: Path = "work_dir" 
    api_token: str = field(default="", repr=False)
    api_url: str = "https://example.com"

    def __post_init__(self):

        # 1. Приводим work_dir к объекту Path и делаем путь абсолютным
        self.work_dir = Path(self.work_dir).resolve()
        
        # Автоматически создаем папку, если её еще нет (опционально)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        # 2. Подтягиваем токен из окружения, если он не передан в конструктор
        if not self.api_token:
            token_from_env = os.environ.get("API_TOKEN")
            if not token_from_env:
                raise ValueError("Критическая ошибка: Переменная окружения 'API_TOKEN' не задана!")
            
            # Так как класса больше не frozen, пишем напрямую:
            self.api_token = token_from_env
# Конфигурация
#API_KEY = os.environ.get("API_TOKEN")
# URL = "https://wildberries.ru"
URL = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"




def run_request(app_config: AppConfig):
    # Параметры запроса (период макс. до 30 дней за один запрос)
    params = {
        "dateFrom": "2026-10-01",
        "dateTo": "2026-10-31",
        "rrdid": 0,  # Стартовый ID для пагинации (0 с начала)
        "limit": 100000
    }

    headers = {
        "Authorization": app_config.api_token,
        "Accept": "application/json"
    }

    response = requests.get(URL, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        print(f"Получено записей: {len(data)}")
        
        # Пример сохранения в JSON-файл
        with open(app_config.work_dir / "wb_report_detail.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Отчет успешно сохранен в wb_report_detail.json")
    else:
        print(f"Ошибка запроса: {response.status_code}, ответ: {response.text}")

if __name__ == "__main__":
    # print(f"API_KEY {API_KEY}")
    app_config  = AppConfig()
    run_request(app_config)
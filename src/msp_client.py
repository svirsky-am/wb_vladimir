import requests
import json
import os
from pathlib import Path






# Конфигурация
API_KEY = os.environ.get("API_TOKEN")
# URL = "https://wildberries.ru"
URL = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"

# Параметры запроса (период макс. до 30 дней за один запрос)
params = {
    "dateFrom": "2026-10-01",
    "dateTo": "2026-10-31",
    "rrdid": 0,  # Стартовый ID для пагинации (0 с начала)
    "limit": 100000
}

headers = {
    "Authorization": API_KEY,
    "Accept": "application/json"
}


def run_request():
    response = requests.get(URL, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        print(f"Получено записей: {len(data)}")
        
        # Пример сохранения в JSON-файл
        with open("wb_report_detail.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Отчет успешно сохранен в wb_report_detail.json")
    else:
        print(f"Ошибка запроса: {response.status_code}, ответ: {response.text}")

if __name__ == "__main__":
    # print(f"API_KEY {API_KEY}")
    run_request()
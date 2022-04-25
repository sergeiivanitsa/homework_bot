import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv

import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
CODE_OK = 200

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO)

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not PRACTICUM_TOKEN:
        logging.critical("'PRACTICUM_TOKEN' не обнаружен")
        return False
    if not TELEGRAM_TOKEN:
        logging.critical("'TELEGRAM_TOKEN' не обнаружен")
        return False
    if not TELEGRAM_CHAT_ID:
        logging.critical("'TELEGRAM_CHAT_ID' не обнаружен")
        return False
    return True


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logging.error(
            f'Ошибка при попытке сделать запрос к эндпоинту '
            f'(не удалось получить временную метку): {error}'
        )

    if response.status_code != CODE_OK:
        raise exceptions.GetApiAnswer(
            f'Ошибка в статусе ответа: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not response['homeworks']:
        exceptions.KeyError(f'Не найден ключ homeworks: {response}')
    homework = response['homeworks']
    if not homework:
        raise exceptions.IndexError(f'Список {homework[0]} пуст')
    logging.info('Статус проверки проекта обновлён')
    return homework[0]


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = check_response()['homework_name']
    if homework_name is None:
        homework_name = ''
    try:
        homework_status = homework.get('status')
    except Exception as error:
        raise exceptions.ParseStatusHomeworkStatus(f'Ошибка status: {error}')
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
    else:
        raise exceptions.ParseStatusVerdict(
            f'Неожиданный статус проекта: {homework_status}'
        )

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Ошибка при попытке отправить сообщение: {error}')


def main():
    """основная логика работы программы."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status = ''
    check_tokens()
    while True:
        try:
            response = get_api_answer(current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            time.sleep(RETRY_TIME)
            continue
        try:
            if check_response(response):
                homework = check_response(response)
                message = parse_status(homework)
                if message != status:
                    send_message(bot, message)
                    status = message
            current_timestamp = current_timestamp
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != status:
                send_message(bot, message)
                status = message
            time.sleep(RETRY_TIME)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()

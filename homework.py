import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions
import settings

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    try:
        response = requests.get(
            settings.ENDPOINT, headers=settings.HEADERS, params=params
        )
    except Exception as error:
        logging.error(
            f'Ошибка при попытке сделать запрос к эндпоинту '
            f'(не удалось получить временную метку): {error}'
        )

    if response.status_code != HTTPStatus.OK:
        raise exceptions.GetApiAnswer(
            f'Ошибка в статусе ответа: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных')
    if 'homeworks' not in response:
        raise KeyError('Не найден ключ homeworks')
    if 'current_date' not in response:
        raise KeyError('Не найден ключ current_date') 
    homework = response['homeworks']
    if not isinstance(homework, list):
        raise TypeError('Неверный тип данных')
    if not homework:
        raise exceptions.IndexError(f'Список {homework[0]} пуст')
    logging.info('Статус проверки проекта обновлён')
    return homework


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'homework_name' and 'status' not in homework:
        raise KeyError('Отсутствуют искомые ключи')
    else:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    if homework_status not in settings.HOMEWORK_STATUSES:
        raise exceptions.StatusHWException(
            f'Недокументированный статус: {homework_status}'
        )
    verdict = settings.HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка при попытке отправить сообщение: {error}')


def main():
    """основная логика работы программы."""
    if check_tokens():
        logging.critical("Переменные не обнаружены")
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time() - settings.PERIOD)
    status = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            time.sleep(settings.RETRY_TIME)
            continue
        try:
            if check_response(response):
                homework = check_response(response)
                message = parse_status(homework)
                if message != status:
                    send_message(bot, message)
                    status = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
        finally:
            time.sleep(settings.RETRY_TIME)


if __name__ == '__main__':
    main()

import logging
import os
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

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logging.critical("Переменные не обнаружены")
        return False
    return True


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
    homework = response['homeworks']
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных')
    if not response['homeworks']:
        exceptions.KeyError(f'Не найден ключ homeworks: {response}')
    if not response['current_date']:
        exceptions.KeyError(f'Не найден ключ current_date: {response}')
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
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        raise exceptions.StatusHWException(
            f'Недокументированный статус: {homework_status}'
        )
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка при попытке отправить сообщение: {error}')


def main():
    """основная логика работы программы."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time() - 30 * 24 * 60 * 60)
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
            current_timestamp = current_timestamp
            time.sleep(settings.RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
        finally:
            time.sleep(settings.RETRY_TIME)


if __name__ == '__main__':
    main()

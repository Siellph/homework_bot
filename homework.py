import json
import logging
import os
import time

import requests
from dotenv import load_dotenv
from telegram import Bot, error

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s'
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.debug('Бот запущен!')


def send_message(bot, message):
    """Отправка сообщения в Telegram.

    Отправляет сообщение в Telegram чат, определяемый
    переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра:
    экземпляр класса Bot и строку с текстом сообщения.
    """
    message_for_log = message.replace('\n', '')
    logging.debug(f'Отправка сообщения в телеграм: {message_for_log}')
    try:
        return bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except error.Unauthorized:
        logging.error('Telegram API не авторизован. Проверьте токен и id чата')
    except error.BadRequest as telegram_error:
        logging.error(f'Ошибка работы с Telegram: {telegram_error}')
    except error.TelegramError as telegram_error:
        logging.error(f'Ошибка работы с Telegram: {telegram_error}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.

    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    logging.info('Получение ответа от сервера')
    timestamp = current_timestamp or int(time.time(0))
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as answer_error:
        raise logging.error('При попытке запроса возникла '
                            f'ошибка: {answer_error}')
    except ValueError as answer_error:
        raise logging.error(f'Ошибка в значении: {answer_error}')
    except TypeError as answer_error:
        raise logging.error(f'Неверный тип данных: {answer_error}')

    if response.status_code != 200:
        raise logging.error('ошибка ответа от сервера. '
                            f'Статус - {response.status_code}')

    try:
        response = response.json()
    except json.JSONDecodeError:
        raise logging.error('Ответ от сервера должен быть в формате JSON')
    logging.info('Получен ответ от сервера')
    return response


def check_response(response):
    """Проверяет ответ API на корректность.

    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям, то функция
    должна вернуть список домашних работ (он может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    logging.debug('Проверка ответа сервера на корректность')
    if 'error' in response:
        if 'error' in response['error']:
            raise logging.error(response['error']['error'])

    if 'code' in response:
        logging.info(response['message'])

    if response['homeworks'] is None:
        logging.info('Заданий нет')

    if not isinstance(response['homeworks'], list):
        raise logging.error(f'Тип - {type(response)} не является списком')
    logging.debug('Ответ сервера проверен на корректность')
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса работы.

    Извлекает из информации о конкретной домашней работе
    статус этой работы. В качестве параметра функция получает
    только один элемент из списка домашних работ. В случае
    успеха, функция возвращает подготовленную для отправки
    в Telegram строку, содержащую один из вердиктов словаря
    HOMEWORK_STATUSES
    """
    logging.debug('Извлекаю статус домашнего задания')
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_STATUSES:
        logging.error('Недокументированный статус домашней работы')

    verdict = HOMEWORK_STATUSES[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка переменных.

    Проверяет доступность переменных окружения,
    которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная
    окружения — функция должна вернуть False, иначе — True.
    """
    if (PRACTICUM_TOKEN is None
            and TELEGRAM_CHAT_ID is None
            and TELEGRAM_TOKEN is None):
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Проверьте переменные окружения '
                         '(PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID')
        return 0
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            logging.info('Список домашних работ получен')
            if ((type(homeworks) is list)
                    and (len(homeworks) > 0)
                    and homeworks):
                send_message(bot, parse_status(homeworks[0]))
            else:
                logging.info('Задания не обнаружены')
            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)
        except Exception as ex_error:
            logging.critical(f'Сбой в работе программы: {ex_error}')


if __name__ == '__main__':
    main()

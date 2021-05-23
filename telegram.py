import requests
import coloredlogs, logging

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG')

import config

TELEGRAM_BASE_URL = f'https://api.telegram.org/bot{config.BOT_TOKEN}'

def get_me():
    r = requests.get(TELEGRAM_BASE_URL + '/getMe')
    logging.info(f'Code: {r.status_code}. Res: {r.text}')

def send_message(user_id, message):
    params = {'chat_id': user_id,
              'text': message}
    r = requests.get(TELEGRAM_BASE_URL + '/sendMessage',
                     params=params)
    logging.info(f'Code: {r.status_code}. Res: {r.text}')

class TelegramHandler(logging.Handler):
    def __init__(self, user_id):
        self.user_id = user_id
        super().__init__()

    def emit(self, record):
        emoji = ""
        if record.levelname == 'INFO':
            emoji = "ℹ"
        elif record.levelname == 'WARNING':
            emoji = "⚠️"
        elif (record.levelname == 'ERROR' or 
              record.levelname == 'CRITICAL'):
            emoji = "🚨"

        # Purchase events are INFO, but want to change the emoji so they stand out.
        # Override here with proper emoji.
        if record.funcName == 'parse_market_buy':
            emoji = "💸"
        send_message(self.user_id, f'{emoji} {record.msg}')
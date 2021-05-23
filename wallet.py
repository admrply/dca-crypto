import logging, coloredlogs
import telegram, config

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG')
telegram_handler = telegram.TelegramHandler(config.TELEGRAM_USER_ID)
telegram_handler.setLevel(logging.INFO)
logger.addHandler(telegram_handler)

class Wallet:
    SPOT = 0
    EARN = 1

    def __init__(self,
                 base_currency,
                 quote_currency,
                 buffered_dca_quote_value=0):
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        self.symbol = f"{base_currency}{quote_currency}"
        self.buffered_dca_quote_value = buffered_dca_quote_value

    def add_dca(self, amount):
        # Round to account for floating point precision. 4 decimals should be enough given we're working with FIAT.
        # May need upping to 6 if we start using BTC or ETH as the quote currency.
        new_amount = round((self.buffered_dca_quote_value + amount), 4)
        logger.debug(f"Adding {amount} to {self.symbol} buffer. (Current total: {new_amount})")
        self.buffered_dca_quote_value = new_amount
        return self.buffered_dca_quote_value

    def get_buffered_dca_quote_value(self):
        return self.buffered_dca_quote_value

    def get_base_currency_name(self):
        return self.base_currency

    def get_quote_currency_name(self):
        return self.quote_currency

    def get_symbol(self):
        return self.symbol

    def reset_buffer(self):
        self.buffered_dca_quote_value = 0
        return 0
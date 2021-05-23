import telegram
import config

class Error(Exception):
    pass

class InvalidIntervalStringError(Error):
    def __init__(self, interval_string, message="Interval string is invalid"):
        self.interval_string = interval_string
        self.message = message
        super().__init__(self.message)
    
    def __str__(self):
        return f'{self.interval_string} -> {self.message}'

class InsufficientBalanceError(Error):
    def __init__(self, currency, available, requested):
        self.currency = currency
        self.available = available
        self.requested = requested
        self.message = (f'Insufficient {currency} balance.\n\n'
                       f'Requested: {self.requested}\n'
                       f'Available: {self.available}')

    def __str__(self):
        telegram.send_message(config.TELEGRAM_USER_ID, f"🚨 {self.message}")
        return f'{self.message}'
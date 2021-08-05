import abc

class ExchangeInterface(metaclass=abc.ABCMeta):
    BASE_URL = abc.abstractproperty()
    MINIMUM_ORDER_VALUE = abc.abstractproperty()
    TRADING_FEE_PERCENTAGE = abc.abstractproperty()

    @abc.abstractmethod
    def _get_srv_time(self):
        pass

    @abc.abstractmethod
    def _place_market_buy(self, coin_symbol, quot_order_qty):
        pass

    @abc.abstractmethod
    def transact(self, wallet, side, quote_order_quantity):
        pass

    @abc.abstractmethod
    def create_wallet(self, base_currency, quote_currency):
        pass
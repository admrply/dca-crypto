import requests
from requests.auth import AuthBase
import json
import logging, coloredlogs
import base64
import hmac, hashlib
import time

from datetime import datetime, date
from enum import Enum, unique

import config, utils, telegram
from const import *
from exchange import ExchangeInterface
from wallet import Wallet

class CoinbaseExchangeAuth(AuthBase):
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def __call__(self, request):
        timestamp = str(time.time())
        body = ''
        if request.body:
            body = request.body.decode()
        message = timestamp + request.method + request.path_url + body
        message_bytes = bytes(message, 'utf-8')
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message_bytes, hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode().rstrip('\n')

        request.headers.update({
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        })
        return request

class CoinbasePro(ExchangeInterface):
    logger = logging.getLogger(__name__)
    coloredlogs.install(level='DEBUG')
    telegram_handler = telegram.TelegramHandler(config.TELEGRAM_USER_ID)
    telegram_handler.setLevel(logging.INFO)
    logger.addHandler(telegram_handler)

    MINIMUM_ORDER_VALUE = 10
    TRADING_FEE_PERCENTAGE = 0.005
    # BASE_URL = "https://api.pro.coinbase.com"
    BASE_URL = "https://api-public.sandbox.pro.coinbase.com"
    auth = CoinbaseExchangeAuth(config.COINBASE_API_KEY, config.COINBASE_API_SECRET, config.COINBASE_API_PASSWORD)
    

    def create_wallet(self, base_currency, quote_currency):
        symbol = f"{base_currency}-{quote_currency}"
        return Wallet(base_currency, quote_currency, symbol)

    def _get_srv_time(self):
        pass

    def __sign(self, method, request_path, body):
        req_timestamp = str(time.time())
        self.headers['CB-ACCESS-TIMESTAMP'] = req_timestamp
        if len(body) > 0:
            body = str(body)
        message = bytes(req_timestamp +
                        method + 
                        request_path + 
                        (body or ''),
                        'utf-8')
        key = base64.b64decode(config.COINBASE_API_SECRET)
        hashed = hmac.new(key, message, hashlib.sha256)
        signature = base64.b64encode(hashed.digest()).decode().rstrip('\n')
        self.headers['CB-ACCESS-SIGN'] = signature
        return 0

    def _place_market_buy(self, coin_symbol, quot_order_qty):
        body = {'type': 'market',
                'side': 'buy',
                'product_id': coin_symbol,
                'funds': quot_order_qty}
        r = requests.post(self.BASE_URL + '/orders',
                          json=body,
                          auth=self.auth)
        if r.ok:
            buy_res = json.loads(r.text)
            return buy_res
        else:
            logger.error(f'Error buying {coin_symbol}. HTTP {r.status_code}: Message: {r.text}')
            return None

    def __get_spot_coins(self, filter=None):
        r = requests.get(self.BASE_URL + '/accounts',
                         auth=self.auth)
        
        if r.ok:
            wallet = json.loads(r.text)
            if filter is not None:
                filtered_coins = []
                for asset in wallet:
                    if asset['currency'] in filter:
                        filtered_coins.append(asset)
                return filtered_coins
            return wallet
        else:
            self.logger.error(f'HTTP {r.status_code}: {r.text}')
            return None

    def __get_spot_value(self, coin_symbol):
        filtered_wallet = self.__get_spot_coins([coin_symbol])
        if filtered_wallet is not None:
            single_wallet = utils.get_single_asset(filtered_wallet, coin_symbol, 'currency')
            single_spot_value = float(single_wallet['available'])
            return single_spot_value
        else:
            return None

    # def _parse_market_buy(response):
    #     append_to_file(response)
    #     if response['status'] == ''
    #     price_pre_mean = 0
    #     quantity = 0
    #     commission = 0
    #     for fill in response['fills']:
    #         price_pre_mean += float(fill['price'])
    #         quantity += float(fill['qty'])
    #         commission += float(fill['commission'])
    #     avg_fill_price = price_pre_mean / len(response['fills'])
    #     logger.warning(f"Purchased {quantity} {response['symbol']} @ {avg_fill_price} ({response['cummulativeQuoteQty']})")
    #     return response['cummulativeQuoteQty']

    def transact(self, wallet, side, quote_order_quantity):
        if side is Side.BUY:
            current_quote_holdings = self.__get_spot_value(wallet.quote_currency)
            if current_quote_holdings is None:
                self.logger.critical(f'Failed to get current spot value for quote currency. {wallet.symbol} trade failed.')
                return TRADE.FAILURE
            if current_quote_holdings <= 3 * quote_order_quantity:
                self.logger.warning(f'Only {current_quote_holdings} {wallet.quote_currency} left in account.')
            if current_quote_holdings < quote_order_quantity:
                self.logger.error(f'Insufficient balance on account to execute {wallet.symbol} trade.')
                return TRADE.FAILURE

            response = self._place_market_buy(wallet.symbol, quote_order_quantity)
            if response is not None:
                utils.coinbase_parse_market_buy(response)
                return TRADE.SUCCESS
            else:
                self.logger.critical(f'Failed to execute {wallet.symbol} trade.')
                return TRADE.FAILURE
        
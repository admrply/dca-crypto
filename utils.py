import hmac
import hashlib
import urllib
import re
import time
import logging, coloredlogs
import json
import sys

from datetime import timedelta, datetime, date

from config import *
import telegram

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG')
telegram_handler = telegram.TelegramHandler(TELEGRAM_USER_ID)
telegram_handler.setLevel(logging.INFO)
logger.addHandler(telegram_handler)

def filter_coins(wallet, coins):
    filtered_coins = []
    for asset in wallet:
        if asset['coin'] in coins:
            filtered_coins.append(asset)
    return filtered_coins

def get_single_asset(coin_array, coin_to_get, key):
    for coin in coin_array:
        if coin[key] == coin_to_get:
            return coin

def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end

def parse_timedelta_string(interval_string):
    regex = re.compile(r'((?P<weeks>\d+?)w)?((?P<days>\d+?)d)?((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')
    time_parts = regex.match(interval_string)
    if not time_parts:
        logger.critical('The timedelta string interval is invalid.')
        exit(-1)
    timedelta_parts = {name: float(param) for name, param in time_parts.groupdict().items() if param}
    if len(timedelta_parts) == 0:
        logger.critical('The timedelta string interval is invalid.')
        sys.exit('The timedelta string interval is invalid.')
    return timedelta(**timedelta_parts)


def open_trades_file():
    with open('trades.json') as json_file:
        data = json.load(json_file)
        return data


def append_to_file(json_buy_res):
    data = open_trades_file()
    current_trades = data['trades']
    current_trades.append(json_buy_res)

    with open('trades.json','w') as f:
        json.dump(data, f)


def get_last_trade_datetime(trade_symbol):
    data = open_trades_file()
    filtered_trades = []
    if len(data['trades']) > 0:
        for trade in data['trades']:
            # TODO, make this exchange agnostic. product_id is CB, symbol is Binance.
            if trade['product_id'] == trade_symbol:
                filtered_trades.append(trade)
        if len(filtered_trades) > 0:
            # TODO, CB 'created_at'. Binance 'transactTime'
            max_date_trade_entry = max(filtered_trades, key=lambda x:x['created_at'])
            # max_date = datetime.fromtimestamp(max_date_trade_entry['transactTime']/1000)
            max_date = datetime.strptime(max_date_trade_entry['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
            return max_date
    return datetime.min

    
def binance_parse_market_buy(response):
    append_to_file(response)
    price_pre_mean = 0
    quantity = 0
    commission = 0
    for fill in response['fills']:
       price_pre_mean += float(fill['price'])
       quantity += float(fill['qty'])
       commission += float(fill['commission'])
    avg_fill_price = price_pre_mean / len(response['fills'])
    logger.warning(f"Purchased {quantity} {response['symbol']} @ {avg_fill_price} ({response['cummulativeQuoteQty']})")
    return response['cummulativeQuoteQty']

def coinbase_parse_market_buy(response):
    append_to_file(response)
    funds = response['funds']
    symbol = response['product_id']
    if response['status'] == 'pending':
        logger.warning(f"Posted a purchase of {symbol} ({funds}). Purchase is pending.")
    elif response['status'] == 'done':
        quantity = response['size']
        price = response['price']
        logger.warning(f"Purchased {quantity} {symbol} @ {price} ({funds})")
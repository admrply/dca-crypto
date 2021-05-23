import requests
import json
import logging, coloredlogs

from datetime import datetime, time, date
from enum import Enum, unique

import config, utils, telegram
from const import *

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG')
telegram_handler = telegram.TelegramHandler(config.TELEGRAM_USER_ID)
telegram_handler.setLevel(logging.INFO)
logger.addHandler(telegram_handler)

MINIMUM_ORDER_VALUE = 10


class Speed():
    FAST = 'FAST'
    NORMAL = 'NORMAL'


@unique
class TIME(Enum):
    BEFORE_MIDNIGHT = 0
    AFTER_MIDNIGHT = 1

BASE_URL = "https://api.binance.com"
headers = {
    'X-MBX-APIKEY': config.API_KEY
}


def get_current_price(symbol=None):
    params = {}
    if symbol:
        params['symbol'] = symbol
    r = requests.get(BASE_URL + '/api/v3/ticker/price',
                     params=params,
                     headers=headers)
    if r.ok:
        price = json.loads(r.text)
        return price
    else:
        logger.error(f'Symbol: {symbol}. HTTP {r.status_code}: {r.text}')
        return None


def get_spot_coins(filter=None):
    params = {'recvWindow': 5000}
    r = requests.get(BASE_URL + '/sapi/v1/capital/config/getall',
                     params=utils.sign(params),
                     headers=headers)
    if r.ok:
        wallet = json.loads(r.text)
        if filter is not None:
            return utils.filter_coins(wallet, filter)
        return wallet
    else:
        logger.error(f'HTTP {r.status_code}: {r.text}')
        return None


def get_spot_value(coin_symbol):
    filtered_wallet = get_spot_coins([coin_symbol])
    if filtered_wallet is not None:
        single_wallet = utils.get_single_asset(filtered_wallet, coin_symbol)
        single_spot_value = float(single_wallet['free'])
        return single_spot_value
    else:
        return None


def get_earn_coin(asset_symbol):
    params = {'recvWindow': 5000,
              'asset': asset_symbol}
    r = requests.get(BASE_URL + '/sapi/v1/lending/daily/token/position',
                     params=utils.sign(params),
                     headers=headers)
    if r.ok:
        earn_asset = json.loads(r.text)
        return earn_asset
    else:
        logger.error(f'Symbol: {asset_symbol}. HTTP {r.status_code}: {r.text}')
        return None


def get_earn_value(asset_symbol):
    earn_details = get_earn_coin(asset_symbol)
    if earn_details is not None:
        product_id = earn_details[0]['productId']
        earn_value = float(earn_details[0]['freeAmount'])
        return product_id, earn_value
    else:
        return None, None
    

def get_srv_time():
    r = requests.get(BASE_URL + '/api/v3/time')
    logger.debug(r.text)


def place_market_buy(coin_symbol, quot_order_qty):
    params = {'recvWindow': 5000,
              'symbol': coin_symbol,
              'side': 'BUY',
              'type': 'MARKET',
              'quoteOrderQty': quot_order_qty
              }
    r = requests.post(BASE_URL + '/api/v3/order/test',
                      data=utils.sign(params),
                      headers=headers)
    if r.ok:
        buy_res = json.loads(r.text)
        return buy_res
    else:
        logger.error(f'Error buying {coin_symbol}. HTTP {r.status_code}: Message: {r.text}')
        return None

def redeem_flexible_product(product_id, amount, speed):
    params = {'productId': product_id,
              'amount': amount,
              'type': speed
              }
    r = requests.post(BASE_URL + '/sapi/v1/lending/daily/redeem',
                      data=utils.sign(params),
                      headers=headers)

    if r.ok:
        redeem_res = json.loads(r.text)
        return redeem_res
    else:
        logger.error(f'Product ID: {product_id}. HTTP {r.status_code}: {r.text}')
        return None
    

def estimate_bnb_fee(trade_amount):
    current_price = get_current_price('BNBGBP')
    if current_price is not None:
        fee_in_fiat = trade_amount * config.TRADING_FEE
        fee_in_bnb = fee_in_fiat / float(current_price['price'])
        return fee_in_bnb
    else:
        return None


def check_and_move_bnb_for_fees(fee_est):
    safe_fee_buffer = fee_est * 5
    # Check current BNB Spot holdings
    bnb_spot_available = get_spot_value('BNB')
    if bnb_spot_available is None:
        logger.error(f'Attempted to get BNB spot value but failed. Will attempt trade anyway.')
        return

    # If there's not enough balance in Spot, then attempt a withdraw
    if bnb_spot_available < safe_fee_buffer:
        # Get current BNB Vault holdings
        bnb_earn_product_id, bnb_earn_available = get_earn_value('BNB')
        if bnb_earn_product_id is None or bnb_earn_available is None:
            logger.error(f'Attempted to get BNB earn value (and ID) but failed. Will attempt trade anyway.')
            return
        # Figure out number of remaining trade buffers for alerting on low balance
        number_of_remaining_safe_trades = ((bnb_earn_available + bnb_spot_available) / 
                                            safe_fee_buffer)
        # Alert if too low
        if number_of_remaining_safe_trades < 20:
            logger.warning(f'Only enough BNB for less than 20 trades. Top up soon! '
                           f'Balance: {bnb_earn_available + bnb_spot_available}. '
                           f'Safe trades: {round(number_of_remaining_safe_trades)}')
        if (bnb_earn_available + bnb_spot_available) < safe_fee_buffer:
            logger.warning(f'BNB value is lower than safe fee limit. '
                           f'Fees may come from trading currency')

        # Minimum withdrawal from BNB vault is 0.001 BNB, so increase the amount if required
        withdraw_amount = max(safe_fee_buffer, 0.001)
        # Withdraw whichever is larger: safe_fee_buffer or the minimum of 0.001 BNB
        if bnb_earn_available >= withdraw_amount:
            if redeem_flexible_product(bnb_earn_product_id,
                                       withdraw_amount,
                                       Speed.FAST) is None:
                logger.error(f'Failed to redeem BNB for fees. Will attempt trade anyway.')
                return
        # If there isn't enough to withdraw the full amount, attempt to withdraw all earn holdings
        elif bnb_earn_available < withdraw_amount and bnb_earn_available != 0:
            if redeem_flexible_product(bnb_earn_product_id,
                                       bnb_earn_available,
                                       Speed.FAST) is None:
                logger.error('Failed to redeem BNB for fees. Will attempt trade anyway.')
                return
        else:
            logger.warning(f'No savings in BNB account to withdraw. '
                           f'Trading currency will be used for fees')


def savings_lock_check():
    time_to_unlock = None
    lock_start = time(23, 48, 0)
    lock_end = time(0, 10, 0)
    time_now = datetime.utcnow().time()
    is_locked = utils.time_in_range(lock_start, lock_end, time_now)
    if is_locked:
        if utils.time_in_range(lock_start, time(23, 59, 59), time_now):
            time_to_unlock = (datetime.combine(date.min, time(23, 59, 59)) - 
                              datetime.combine(date.min, time_now) + 
                              datetime.timedelta(minutes=10, seconds=30))
        else:
            time_to_unlock = (datetime.combine(date.min, time(0, 10, 30)) - 
                              datetime.combine(date.min, time_now))
    return is_locked, time_to_unlock
        

def transact(wallet, side, quote_order_quantity):
    if side is Side.BUY:
        fee_est = estimate_bnb_fee(quote_order_quantity)
        check_and_move_bnb_for_fees(fee_est)

        current_quote_holdings = get_spot_value(wallet.quote_currency)
        if current_quote_holdings is None:
            logger.critical(f'Failed to get current spot value for quote currency. {wallet.symbol} trade failed.')
            return TRADE.FAILURE

        if current_quote_holdings < quote_order_quantity:
            earn_product_id, earn_available = get_earn_value(wallet.quote_currency)
            if earn_product_id is None or earn_available is None:
                logger.critical(f'Failed to get earn value for {wallet.quote_currency}. {wallet.symbol} trade failed.')
                return TRADE.FAILURE
            if earn_available <= 30:
                logger.warning(f"Only {earn_available} left in Earn wallet. Top up today so trades don't fail tomorrow.")
            if (earn_available + current_quote_holdings) < quote_order_quantity:
                logger.critical(f'Insufficient {wallet.quote_currency} to make trade. '
                                 f'Availble: {earn_available}. {wallet.symbol} trade failed.')
                return TRADE.FAILURE
            did_redeem = redeem_flexible_product(earn_product_id, quote_order_quantity - current_quote_holdings, Speed.FAST)
            if did_redeem is None:
                logger.critical(f'Failed to redeem quote currency for trade. {wallet.symbol} trade failed.')
                return TRADE.FAILURE
        
        response = place_market_buy(wallet.symbol, quote_order_quantity)
        if response is not None:
            utils.parse_market_buy(response)
            return TRADE.SUCCESS
        else:
            logger.critical(f'Failed to execute {wallet.symbol} trade.')
            return TRADE.FAILURE

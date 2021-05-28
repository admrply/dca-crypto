#!/usr/bin/env python
import asyncio
import coloredlogs, logging

from datetime import timedelta, datetime, date

import utils, binance, config, telegram
from wallet import Wallet
from const import *

logger = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG')
telegram_handler = telegram.TelegramHandler(config.TELEGRAM_USER_ID)
telegram_handler.setLevel(logging.INFO)
logger.addHandler(telegram_handler)


async def dca(base_currency, quote_currency, amount, interval):
    # Create wallet instance to track the symbol and DCA bufferred amount
    wallet = Wallet(base_currency, quote_currency)
    # Reduce oversized DCA schedules to the minimum allowed order size
    min_tick_denominator = 1
    if amount > binance.MINIMUM_ORDER_VALUE:
        min_tick_denominator = amount / binance.MINIMUM_ORDER_VALUE
    # Calculate the delta (in seconds) between DCA ticks
    full_requested_timedelta = utils.parse_timedelta_string(interval)
    full_requested_seconds_interval = full_requested_timedelta.total_seconds()
    timedelta_interval = full_requested_timedelta / min_tick_denominator
    seconds_interval = timedelta_interval.total_seconds()
    logger.info(f"Adding {amount/min_tick_denominator} {quote_currency} to {base_currency} "
                f"pool at an interval of {timedelta_interval}")
    # Check if next tick is within last trade timestamp to prevent buying too soon after a restart
    last_trade_datetime = utils.get_last_trade_datetime(wallet.symbol)
    if last_trade_datetime == datetime.min:
        trade_status = TRADE.NO_TRADE_YET
    else:
        trade_status = TRADE.SUCCESS
        date_of_next_tick = last_trade_datetime + timedelta_interval
        time_now = datetime.utcnow()
        # If the time until next tick is after 'now', then calculate seconds to wait and async wait them.
        if not utils.time_in_range(datetime.min, time_now, date_of_next_tick):
            timedelta_to_next_tick = date_of_next_tick - time_now
            logger.info(f'Trade on {wallet.symbol} already occurred recently. Pausing until next tick at {date_of_next_tick}')
            await asyncio.sleep(timedelta_to_next_tick.total_seconds())
    while True:
        # If the previous trade did not fail (was a success or hasn't started yet), then add the full amount to the buffer
        if trade_status is not TRADE.FAILURE:
            wallet.add_dca(amount/min_tick_denominator)
        # Check if we have enough in the buffer to trade
        if wallet.buffered_dca_quote_value >= binance.MINIMUM_ORDER_VALUE:
            # Check we're not in the Binance Earn rewards period where you can't withdraw. If we are, wait until it's finished.
            is_locked, timedelta_to_unlock = binance.savings_lock_check()
            if is_locked:
                logger.info(f'Savings withdraw unavailable. Waiting until unlock.')
                await asyncio.sleep(timedelta_to_unlock.total_seconds())
            # Make the trade
            trade_status = binance.transact(wallet, Side.BUY, wallet.buffered_dca_quote_value)
        # If it succeeds, we need to reset the buffer so we don't buy double next time!
        if trade_status is TRADE.SUCCESS:
            wallet.reset_buffer()
        # It could have failed for a number of reasons, commonly, the global FAST withdrawal limit was hit for the day.
        if trade_status is TRADE.FAILURE:
            # Figure out amount extra to buy for the hour delay
            extra_hour_tick_amount = amount / full_requested_seconds_interval * 60 * 60
            logger.warning(f'Setting next dca tick to 1 hour to set trade backoff. '
                           f'Adding {round(extra_hour_tick_amount, 4)} {wallet.quote_currency} to compensate for trade delay.')
            wallet.add_dca(extra_hour_tick_amount)
            await asyncio.sleep(timedelta(hours=1).total_seconds())
        else:
            trade_status = TRADE.NO_TRADE_YET
            await asyncio.sleep(seconds_interval)


async def main():
    # Schedule three calls concurrently:
    await asyncio.gather(
        dca("BTC", "GBP", 0.25, "1h"),
        dca("ETH", "GBP", 0.25, "1h"),
        dca("ZIL", "USDT", 65, "30d"),
        dca("XTZ", "USDT", 65, "30d"),
        dca("VET", "GBP", 45, "30d")
    )


if __name__ == "__main__":
    asyncio.run(main())
# DCA Crypto Bot
This python script uses asyncio and is designed to be run constantly to buy cryptocurrencies on Binance at a set time interval.
This script automatically calculates the lowest possible timeframe for buying based on your schedule. For example, if you wanted to buy £70 of BTC every week, the script would automatically convert this to £10 a day as Binance's minimum order threshold is 10 GBP or 10 USDT. This works the other way too and it will store small amounts of DCA in a buffer and buy when the minimum order threshold is reached.
Logs are streamed out to Telegram and systemd units are provided to watch for and report crashes.

# Prerequisites
- Assumes Ubuntu 1804+, but this should work on any system with python. The service files section at the bottom may differ on different systems.
- Python 3.7+
- Binance API tokens (see below)
- Telegram API tokens (see below)

## Getting started
### Installing prerequisites
```bash
sudo apt install -y python3 python3-venv
python3 -V # Version *must* be 3.7+ in order for asyncio to work
git clone https://github.com/admrply/dca-crypto.git
cd dca-crypto
python3 -m venv env
. ./env/bin/activate
pip install -r requirements.txt
```

### Creating the config
1. Rename (or copy) `config.py.template`{:.bash} to `config.py`{:.bash}.
2. Create your Binance API keys ([guide](https://www.binance.com/en/support/faq/360002502072))
    - Make sure it has the 'Enable Spot & Margin Trading' option ticked.
3. Add your Binance API key and secret key to `config.py`
4. Create a Telegram bot by talking to the [BotFather](https://t.me/botfather)
5. Use the `/newbot` command in the BotFather chat to create a new bot and get a token.
6. Add this token to `BOT_TOKEN` in `config.py`{:.bash}.
7. Find your Telegram user ID to add to the `config.py`{:.bash} (Here's a [guide](https://medium.com/@tabul8tor/how-to-find-your-telegram-user-id-6878d54acafa) on how to find your ID)
8. Make sure the trading fee is correct. This should be the decimal form of your trading percentage taker fee. You can find your fees [here](https://www.binance.com/en/fee/schedule)
    - Even if you get 20% kickback, use the fee schedule for the 25% off with BNB *only*. This is because the 20% kickback is refunded *after* the trade and you may end up with not enough BNB to pay for the fees if you use the full discount percentages.
    - e.g. If you use BNB for fees (which you should be!) and trade less than 50 BTC a month, your taker fee is 0.075%. When converted to decimal form, this is 0.00075 (the default value shown in the template)
    
### Setting your DCA amounts
In `main.py`, set your DCA amounts in the asyncio entrypoint:
```python
async def main():
    await asyncio.gather(
        dca("BTC", "GBP", 120, "1w"),
        dca("ETH", "GBP", 0.3, "1h")
    )
```
- The first param should be the base currency code as a string (the one you're buying, i.e. BTC)
- The second param should be the quote currency code as a string (the one you're spending to buy the base currency, i.e. GBP)
- The third param should be a float representing the amount to spend each 'tick'.
- The fourth param is a string indicating the tick length.
    - The format for this 'time string' can contain any combination of weeks (w), days (d), hours (h), minutes (m) and seconds (s).
    - The following strings are examples of valid time tick strings:
        - `"1w"`{:.python}
        - `"1d"`{:.python}
        - `"3d12h"`{:.python}
        - `"1w3d8h3m24s"`{:.python}
- `dca("BTC", "GBP", 120, "1w")`{:.python}
    - This line will buy £120 of BTC every week.
    - The script will automatically convert this into buying £10 every 14 hours
- `dca("ETH", "GBP", 0.3, "1h")`{:.python}
    - This line will attempt to buy 30p of ETH every hour.
    - This value is too small to trade on Binance every hour, so the script will add this to a buffer each hour and then execute the trade when the value meets or exceeds the minimum trade value.
    - Note that the buffer is only added to on each 'tick', therefore the script will execute a larger buy of £10.20 after 34 hours instead of buying £10 worth after 33 hours and 20 minutes. This has no meaningful effect on your DCA as it ends up still being the same as buying 30p an hour.


### Setting up as a service
Whilst at this point you can now just run `python3 main.py`{:.bash}, it's recommended to set it up as a service so you can get a crash notification if it fails and get your logs into syslog.
Service files have been provided for your convenience in the systemd-units folder!
- Copy these files to `/etc/systemd/system/`{:.bash}
- Change the folder path in the unit files (`/home/ubuntu/dca-crypto`{:.bash}) to where your repo is stored.
- Make the entrypoint executable (`chmod +x /path/to/dca-crypto/main.py`{:.bash})
- `systemctl daemon-reload`{:.bash}
- `systemctl start dca`{:.bash}
- This service will not restart if it crashes to prevent duplicate and/or overspending.
- To see logs: `systemctl status dca`{:.bash} or `journalctl -u dca`{:.bash}
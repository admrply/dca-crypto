#!/usr/bin/env python
import telegram, config

telegram.send_message(config.TELEGRAM_USER_ID, f"🔌 The system has rebooted. DCA is not running!")
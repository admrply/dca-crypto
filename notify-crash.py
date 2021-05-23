#!/usr/bin/env python
import sys
import telegram, config

service_name = '<unknown>'
if len(sys.argv) >= 2:
  service_name = sys.argv[1]

telegram.send_message(config.TELEGRAM_USER_ID, f"💥 The {service_name} service has crashed!")

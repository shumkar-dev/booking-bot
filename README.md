# Booking Bot for Small Businesses

A Telegram bot that books clients into free time slots while the owner is busy working.
The client books in a few taps, the owner approves the request in their own chat, and the
bot reminds the client 24 hours and 2 hours before the visit — so fewer no-shows and no
appointments lost in DMs.

Built for salons, barbershops and studios, but the service list and working hours are
configuration, not code: point it at a different business and it works there too.

Python · aiogram 3 · SQLite (aiosqlite) · pytest

## What it does

- Books in five steps: service → day → time → contacts → confirmation
- Checks slot availability — double booking of the same time is impossible
- Returning clients book without re-entering their contacts
- Sends the owner a request card with Accept / Decline / Call back / Message buttons
- Two-way chat between the client and the owner
- Automatic reminders 24 hours and 2 hours before the visit
- Info sections: prices, address, Instagram

## Project layout

```
bot.py            entry point: Bot/Dispatcher setup, graceful shutdown
config.py         configuration from the environment, services, working hours
scheduling.py     day and slot generation, time validation
database.py       data access layer (aiosqlite)
keyboards.py      inline keyboards
states.py         FSM states
utils.py          input validation, escaping, safe sending
middlewares.py    anti-flood
reminders.py      background reminder loop
handlers/
  client.py       client flows
  admin.py        owner flows
tests/            validation and scheduling tests
```

Slots are not hardcoded — they are generated from the working hours
(`WORK_START_HOUR`, `WORK_END_HOUR`, `SLOT_STEP_MINUTES`). Because of that, a visit is
stored as a full timezone-aware `datetime`, and reminders are calculated straight from it.

## Technical decisions worth noting

- **Double booking is blocked by a partial `UNIQUE INDEX`** on `visit_at` for active
  statuses. The check in the code only exists to show a readable message; the race
  condition is stopped by the database.
- **Admin rights are enforced by a router filter**, not by an `if` in every handler.
- **User input is escaped** before it goes into HTML messages.
- **The timezone is explicit** via `TIMEZONE` — system time on a VPS is usually UTC, and
  silently booking clients in UTC is a bug you find the hard way.
- **FSM lives in memory**, so state is lost on restart. Under load it can be swapped for
  `RedisStorage` without touching a single handler.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in BOT_TOKEN and ADMIN_ID
python bot.py
```

Get a token from [@BotFather](https://t.me/BotFather) and your Telegram ID from
[@userinfobot](https://t.me/userinfobot).

`.env` is not committed (see `.gitignore`). If a token has ever been in the code, revoke
it with `/revoke` in BotFather — deleting the file does not clean the commit history.

## Tests

```bash
pytest
```

## Adapting it to another business

Services are the `SERVICES` dictionary in `config.py`. Working hours, slot step and how
far ahead clients can book are set in `.env`.

## Deployment (systemd)

`/etc/systemd/system/booking-bot.service`:

```ini
[Unit]
Description=Booking bot
After=network.target

[Service]
Type=simple
User=bot
WorkingDirectory=/opt/booking-bot
EnvironmentFile=/opt/booking-bot/.env
ExecStart=/opt/booking-bot/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now booking-bot
sudo journalctl -u booking-bot -f
```

systemd rather than `screen`: it starts on boot, restarts on crash and logs to journald.

## Possible improvements

- Move the FSM to Redis
- Let clients cancel and reschedule
- Take service duration into account when checking availability (one slot is booked today)
- Export appointments to the owner's calendar

Russian version of this document: [README.ru.md](README.ru.md)

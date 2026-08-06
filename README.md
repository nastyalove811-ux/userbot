# Telegram Userbot + веб-панель

Юзербот на Telethon с веб-панелью на FastAPI, PostgreSQL и Redis, готовый к
деплою на Railway (двумя процессами: `web` и `worker`).

## Реализованные модули

- **Core** — `.help`, `.settings`, `.setprefix`, `.lang`, `.preset`, `.restart`, `.addalias/.delalias/.aliases`
- **Chat** — `.id`, `.invite`, `.kickme`, `.members`, `.admins`, `.bots`, `.link`, `.common`, `.chats`, `.chat`, `.send`, `.reply`
- **ChatStats** — `.chatstats`
- **Info** — `.info`, `.who`, `.chatinfo`
- **Kurs** — `.kurs`, `.crypto` (ExchangeRate-API + CoinGecko)
- **MessageToFile** — `.mtf`, `.ftm`
- **Test** — `.ping`, `.dump`
- **Admin** — `.promote`, `.demote`, `.pin`, `.unpin`, `.kick`, `.ban`, `.tban`, `.unban`, `.mute`, `.unmute`
- **Purger** — `.del`, `.purge`, `.rpurge`, `.delshit`, `.delme`, `.delmenow`, `.delsys`, `.delword`, `.kickall`
- **Clone** — `.clone`, `.unclone`
- **Contacts** — `.block`, `.unblock`, `.addcontact`, `.delcontact`, `.report`
- **PingBot** — `.addpingbot`, `.delpingbot`, `.pingbots`, `.pingnow` (+ фоновый цикл проверки)
- **Quotes** — `.quote`, `.fakequote` (рендер изображений через Pillow)
- **Screenshot** — `.screenshot` (уведомление в ЛС)
- **Streak** — `.streak`, `.streaks`, `.streakinfo` (+ полуночный пересчёт)
- **SwMute** — `.swmute`, `.swmutelist`, `.swmuteclear` (тихое автоудаление сообщений)
- **TypingWatch** — `.typingwatch`, `.typingstat`
- **UrlDl** — `.urldl`, `.urldlbig`
- **Voicy** — `.voicy`, `.autovoice` (нужен внешний STT-сервис, настраивается через `.settings voicy api_url ...`)
- **WebShot** — `.shot` (нужен внешний сервис скриншотов, `.settings webshot api_url ...`), `.fileshot` (подсветка кода локально через Pygments)
- **Welcome** — `.welcome`, `.goodbye`
- **Wordle** — `.wordle`

### Сознательно исключено

По требованию заказчика в проект **не включены**: модуль массовой рассылки
(Spam/cspam/wspam/delayspam), модуль авто-троллинга по триггеру (Toxic),
модуль скрытого перехвата чужих правок/удалений и файлов (StealMan),
массовые упоминания (TagAll) и авто-реакции на конкретных пользователей
(ZaebReactions) — все они автоматизируют нежелательное для третьих лиц
воздействие без их согласия.

Все модули из исходного промта реализованы, кроме сознательно исключённых выше.

## Установка

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполните переменные, сгенерируйте ENCRYPTION_KEY:
python -c "from app.utils import generate_encryption_key; print(generate_encryption_key())"
```

## Локальный запуск

```bash
# терминал 1 — веб-панель / API
uvicorn app.main:app --reload

# терминал 2 — воркер (Telethon-клиенты, обработка команд)
python -m app.worker
```

## Подключение аккаунта

1. `POST /api/auth/login` с `ADMIN_LOGIN`/`ADMIN_PASSWORD` — получаете cookie-сессию.
2. `POST /api/accounts/send-code` с номером телефона — Telegram присылает код.
3. `POST /api/accounts/confirm-code` с кодом (и паролем 2FA, если включён).
4. Воркер автоматически подхватывает новый аккаунт через Redis pub/sub (`account_added`).

## Деплой на Railway

1. Создайте проект, подключите PostgreSQL и Redis плагины — Railway сам
   пропишет `DATABASE_URL`/`REDIS_URL`.
2. Задайте остальные переменные из `.env.example` в настройках проекта.
3. Railway обнаружит `Procfile` и поднимет два процесса: `web` и `worker`.

## Права команд

Все команды доступны только владельцу (`ADMIN_ID`), это проверяется в
диспетчере (`worker.py`). Команды, требующие административных прав в
конкретном чате (модерация), дополнительно проверяются через
`check_chat_permission()` перед выполнением — при нехватке прав
пользователь получает понятную ошибку вместо падения воркера.

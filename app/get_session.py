from telethon import TelegramClient, sessions
import asyncio

API_ID = 31580348  # ваш api_id из переменных
API_HASH = 'd053644c96e8ad64fe93eab7bcf42675'

async def main():
    # Создаём клиент с пустой строкой сессии (новая сессия)
    client = TelegramClient(sessions.StringSession(), API_ID, API_HASH)
    await client.start()
    # Сохраняем строку сессии
    session_str = client.session.save()
    print("Ваша сессионная строка:")
    print(session_str)
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())

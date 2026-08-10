from telethon import TelegramClient, sessions
import asyncio

api_id = 31580348
api_hash = 'd053644c96e8ad64fe93eab7bcf42675'

async def main():
    client = TelegramClient(sessions.StringSession(), api_id, api_hash)
    await client.start()
    print(client.session.save())  # выведет строку сессии
    await client.disconnect()

asyncio.run(main())

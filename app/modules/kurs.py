"""
Модуль Kurs — конвертер валют/криптовалют через внешние API,
результаты кэшируются в Redis на 5 минут.
"""
from __future__ import annotations

import re

import httpx

from app.modules.base import CommandContext, command
from app.modules.core import get_setting
from app.redis_client import cache_get, cache_set

CACHE_TTL = 300  # 5 минут

_MULTIPLIERS = {
    "к": 1_000, "тыс": 1_000,
    "кк": 1_000_000, "млн": 1_000_000,
    "млрд": 1_000_000_000,
    "трлн": 1_000_000_000_000,
}

_SYMBOLS = {"$": "USD", "€": "EUR", "₽": "RUB", "₿": "BTC", "£": "GBP", "¥": "JPY"}

_CRYPTO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether", "BNB": "binancecoin",
    "SOL": "solana", "XRP": "ripple", "TON": "the-open-network", "DOGE": "dogecoin",
}


def _normalize_amount(token: str) -> float | None:
    token = token.lower().replace(",", ".")
    for suffix, mult in sorted(_MULTIPLIERS.items(), key=lambda kv: -len(kv[0])):
        if token.endswith(suffix):
            num_part = token[: -len(suffix)] or "1"
            try:
                return float(num_part) * mult
            except ValueError:
                return None
    try:
        return float(token)
    except ValueError:
        return None


def _normalize_currency(token: str) -> str:
    token = token.strip()
    if token in _SYMBOLS:
        return _SYMBOLS[token]
    return token.upper()


async def _get_fiat_rate(base: str, target: str) -> float:
    cache_key = f"kurs:fiat:{base}"
    rates = await cache_get(cache_key)
    if rates is None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://api.exchangerate-api.com/v4/latest/{base}")
            resp.raise_for_status()
            rates = resp.json()["rates"]
        await cache_set(cache_key, rates, CACHE_TTL)
    if target not in rates:
        raise ValueError(f"Валюта {target} не найдена")
    return rates[target]


async def _get_crypto_price_usd(symbol: str) -> float:
    coingecko_id = _CRYPTO_IDS.get(symbol)
    if not coingecko_id:
        raise ValueError(f"Криптовалюта {symbol} не поддерживается")
    cache_key = f"kurs:crypto:{symbol}"
    price = await cache_get(cache_key)
    if price is None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": coingecko_id, "vs_currencies": "usd"},
            )
            resp.raise_for_status()
            price = resp.json()[coingecko_id]["usd"]
        await cache_set(cache_key, price, CACHE_TTL)
    return price


@command("kurs", module="kurs", description="Конвертер валют/криптовалют")
async def cmd_kurs(ctx: CommandContext) -> None:
    default_currency = await get_setting(ctx.account_id, "kurs", "default_currency", "USD")

    amount = 1.0
    tokens = list(ctx.args)

    if tokens and (parsed := _normalize_amount(tokens[0])) is not None:
        amount = parsed
        tokens = tokens[1:]

    if not tokens:
        await ctx.event.reply(f"Использование: {ctx.prefix}kurs [сумма] <из> [в]")
        return

    from_cur = _normalize_currency(tokens[0])
    to_cur = _normalize_currency(tokens[1]) if len(tokens) > 1 else default_currency

    try:
        if from_cur in _CRYPTO_IDS:
            price_usd = await _get_crypto_price_usd(from_cur)
            usd_amount = amount * price_usd
            if to_cur == "USD":
                result = usd_amount
            else:
                rate = await _get_fiat_rate("USD", to_cur)
                result = usd_amount * rate
        else:
            rate = await _get_fiat_rate(from_cur, to_cur)
            result = amount * rate

        await ctx.event.reply(f"💱 {amount:g} {from_cur} = {result:,.2f} {to_cur}")
    except (ValueError, KeyError, httpx.HTTPError) as exc:
        await ctx.event.reply(f"❌ Не удалось выполнить конвертацию: {exc}")


@command("crypto", module="kurs", description="Топ-10 криптовалют")
async def cmd_crypto(ctx: CommandContext) -> None:
    default_currency = (await get_setting(ctx.account_id, "kurs", "default_currency", "USD")).lower()
    cache_key = f"kurs:top10:{default_currency}"
    data = await cache_get(cache_key)
    if data is None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={"vs_currency": default_currency, "order": "market_cap_desc", "per_page": 10, "page": 1},
            )
            resp.raise_for_status()
            data = resp.json()
        await cache_set(cache_key, data, CACHE_TTL)

    lines = [f"📈 Топ-10 криптовалют ({default_currency.upper()}):"]
    for coin in data:
        change = coin["price_change_percentage_24h"] or 0
        arrow = "🟢" if change >= 0 else "🔴"
        lines.append(
            f"{arrow} {coin['symbol'].upper()}: {coin['current_price']:,.2f} ({change:+.2f}%)"
        )
    await ctx.event.reply("\n".join(lines))

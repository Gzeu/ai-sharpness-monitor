"""Single-process launcher — starts both the API and Telegram bot together.

Usage:
    python run.py          # starts API + bot (if TELEGRAM_BOT_TOKEN is set)
    python run.py --api    # API only
    python run.py --bot    # Bot only
"""
import asyncio
import sys
import structlog
from monitor.db import init_db
from monitor.config import settings

log = structlog.get_logger()


async def run_api():
    import uvicorn
    config = uvicorn.Config(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_bot():
    from bot.telegram_bot import create_bot
    bot = create_bot()
    await bot.initialize()
    await bot.start()
    await bot.updater.start_polling(allowed_updates=["message"])
    log.info("telegram_bot_running")
    # Keep running
    await asyncio.Event().wait()


async def main():
    init_db()

    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"

    if mode == "--api":
        log.info("starting_api_only")
        await run_api()
    elif mode == "--bot":
        log.info("starting_bot_only")
        await run_bot()
    else:
        log.info("starting_all")
        tasks = [asyncio.create_task(run_api())]
        if settings.telegram_bot_token:
            tasks.append(asyncio.create_task(run_bot()))
        else:
            log.warning("no_telegram_token", hint="Set TELEGRAM_BOT_TOKEN in .env to enable bot")
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())

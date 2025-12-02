import asyncio
from traceback import format_exc

# Setup uvloop and create event loop BEFORE importing Pyrogram
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

# Create the event loop before any imports that might need it
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from asyncio import sleep as asleep, gather
from aiohttp import web
from pyrogram import idle

from bot import __version__, LOGGER
from bot.config import Telegram
from bot.server import web_server
from bot.telegram import StreamBot
from bot.telegram.clients import initialize_clients

async def start_services():
    LOGGER.info(f'Initializing Surf TG - Helium v-{__version__}')
    await asleep(1.2)
    
    await StreamBot.start()
    StreamBot.username = StreamBot.me.username
    LOGGER.info(f"Bot Client : [@{StreamBot.username}]")
    
    await asleep(1.2)
    LOGGER.info("Initializing Multi Clients")
    await initialize_clients()
    
    await asleep(2)
    LOGGER.info('Initalizing Surf Web Server..')
    server = web.AppRunner(await web_server())
    LOGGER.info("Server CleanUp!")
    await server.cleanup()
    
    await asleep(2)
    LOGGER.info("Server Setup Started !")
    
    await server.setup()
    await web.TCPSite(server, '0.0.0.0', Telegram.PORT).start()

    LOGGER.info("Surf TG - Helium Started Revolving !")
    await idle()

async def stop_clients():
    await StreamBot.stop()


if __name__ == '__main__':
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        LOGGER.info('Service Stopping...')
    except Exception:
        LOGGER.error(format_exc())
    finally:
        loop.run_until_complete(stop_clients())
        loop.stop()

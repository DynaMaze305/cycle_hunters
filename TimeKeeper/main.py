import asyncio
import logging
import os

import colorlog
from .agent import TimeKeeperAgent

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(levelname)-8s%(reset)s %(name)s: %(message)s",
    log_colors={
        "DEBUG":    "cyan",
        "INFO":     "green",
        "WARNING":  "yellow",
    },
))
logging.basicConfig(level=logging.INFO, handlers=[handler])

async def main() -> None:
    jid      = os.environ["XMPP_JID"]
    password = os.environ["XMPP_PASSWORD"]

    agent = TimeKeeperAgent(jid=jid, password=password)
    await agent.start(auto_register=True)

    logging.info(f"[Main] -- TimeKeeper running as {jid}")

    try:
        await asyncio.Event().wait() 
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await agent.stop()
        logging.info("[Main] -- TimeKeeper stopped")

asyncio.run(main())

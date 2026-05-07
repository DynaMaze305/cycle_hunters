import logging

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from .coordinator import TimeKeeperCoordinator

logger = logging.getLogger("TimeKeeperAgent")

CMD_START = "Hello TimeKeeper ! Please initialise a race."
CMD_READY = "I'm ready to race !"

class TimeKeeperAgent(Agent):

    def __init__(self, jid: str, password: str, verify_security: bool = False):
        """Initialize the TimeKeeper SPADE agent.

            Args:
                jid (str): Jabber ID (XMPP address) of this agent
                password (str): XMPP account password for authentication.
                verify_security (bool, optional): Whether to enforce TLS certificate verification. Defaults to False.
        """
        super().__init__(jid, password, verify_security=verify_security)
        self.coordinator = TimeKeeperCoordinator(send=self._send_message)

    async def _send_message(self, recipient: str, body: str) -> None:
        """Send message async to a specific recipient
        """
        msg = Message(to=recipient, body=body)
        await self._listener.send(msg)

    class CommandListener(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if not msg:
                return

            sender = str(msg.sender).split("/")[0]
            body   = msg.body.strip()
            logger.info(f"[TimeKeeper Agent] -- Recieved : '{body}' from {sender}")

            if body == CMD_START:
                await self.agent.coordinator.on_start(sender)
            elif body == CMD_READY:
                await self.agent.coordinator.on_ready(sender)
            else:
                logger.warning(f"[TimeKeeper Agent] -- Unknown recieved message: '{body}' from {sender}")

    async def setup(self) -> None:
        """Spade agent life-cycle called once at agent start
        """
        logger.info(f"[TimeKeeper Agent] -- TimeKeeper start as {self.jid}")
        self._listener = self.CommandListener()
        self.add_behaviour(self._listener)

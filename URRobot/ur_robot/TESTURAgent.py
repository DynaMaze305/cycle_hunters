import asyncio
import json
import os
import logging

from spade.agent import Agent, Template
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("TEST URAgent")

# Enable SPADE and XMPP specific logging
for log_name in ["spade", "aioxmpp", "xmpp"]:
    log = logging.getLogger(log_name)
    log.setLevel(logging.DEBUG)
    log.propagate = True


TEST_PICK_POSITION = {"x": 0.0971, "y": -0.337}
# The place position is not used any more.

class TESTURAgent(Agent):
    class XMPPCommandListener(CyclicBehaviour):
        """
        Command Listener for the TESTURAgent.

        Logger the received message.
        """
        async def on_start(self):
            """
            Start the Command Listener
            """
            logger.info("[TEST] Command listener started")

        async def run(self):
            """
            Listen for incoming XMPP messages.
            """
            logger.info("[TEST] Waiting for messages...")
            msg = await self.receive(timeout=1)

            if msg:
                logger.info(f"[TEST] Received message: {msg}")
            else:
                logger.debug("[TEST] No message received")

    class TESTRequest(OneShotBehaviour):
        async def on_start(self):
            self.to_agent = os.environ.get("UR_AGENT", "ur-agent@isc-coordinator2.lan")
            self.data = json.dumps({
                "pick": TEST_PICK_POSITION
            })

        async def run(self):
            reply = Message(to=self.to_agent)
            reply.set_metadata("performative", "request")
            reply.body = f"pick {self.data}"
            await self.send(reply)
            logger.info(f"[Behaviour] Sent request {reply}")
            


    # -----------------------------
    # AGENT SETUP
    # -----------------------------
    async def setup(self):
        """
        Setup the TEST URAgent
        """
        logger.info("[Agent] TEST URAgent starting setup...")
        logger.info(f"[Agent] Will connect as {self.jid}")

        self.register_list = []
        self.running = True

        template = Template()
        template.set_metadata("performative", "inform")
        self.add_behaviour(self.XMPPCommandListener(), template=template)

        self.add_behaviour(self.TESTRequest())

        logger.info("[Agent] Behaviours added, setup complete.")

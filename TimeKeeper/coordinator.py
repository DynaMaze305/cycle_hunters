import asyncio
import logging
import time

from dataclasses import dataclass, field
from typing import Awaitable, Callable
from .gatePairer import gates_finder, gates_configurator
from .gate import Gate

logger = logging.getLogger("TimeKeeperCoordinator")

async def _run_race(start_gate: Gate, end_gate: Gate) -> tuple[float, float]:
    """Full race running process"""

    # initialization
    await start_gate.connect()
    await end_gate.connect()
    start_gate.reset_crossed()
    end_gate.reset_crossed()

    # start process
    await start_gate.wait_crossed()
    t0 = time.monotonic()
    #race signalitics
    blink_task = asyncio.create_task(start_gate.running_blink())
    await end_gate.set_led(255, 255, 255)

    # finish process
    await end_gate.wait_crossed()
    finish_time = time.monotonic()
    elapsed = finish_time - t0

    blink_task.cancel()
    try:
        await blink_task
    except asyncio.CancelledError:
        pass

    await end_gate.finish_blink()
    await start_gate.disconnect()
    await end_gate.disconnect()

    return elapsed, finish_time

SendFn = Callable[[str, str], Awaitable[None]]

@dataclass
class Session:
    ready:      asyncio.Event = field(default_factory=asyncio.Event)
    start_gate: Gate | None   = None
    end_gate:   Gate | None   = None


class TimeKeeperCoordinator:

    def __init__(self, send: SendFn):
        self._send = send
        self.sessions: dict[str, Session] = {}
        self._pairing_lock = asyncio.Lock()
        self._launch_lock  = asyncio.Lock()
        self._race_start_time: float = 0.0
        self._pair_color : int = 0

    # command handlers
    async def on_start(self, sender_jid: str) -> None:
        """Create a new session for the specific sender and launch gate pairing

        Args:
            sender_jid (str): XMPP address of the Logger that initiated the race.
        """
        # check if multiple/false commands
        if sender_jid in self.sessions:
            logger.warning(f"[Coordinator] Session already exists for {sender_jid} -- ignoring request...")
            return

        self.sessions[sender_jid] = Session()
        asyncio.create_task(self._pair_and_setup(sender_jid))

    async def on_ready(self, sender_jid: str) -> None:
        """Note the sender's session as ready and try to start all active sessions

        Args:
            sender_jid (str): XMPP address of the sender
        """
        # check that sender has a session
        if sender_jid not in self.sessions:
            logger.warning(f"[Coordinator] No session for {sender_jid} -- ignoring 'ready'")
            return

        self.sessions[sender_jid].ready.set()
        asyncio.create_task(self._launch_race())

        # check to wait if other session exist but team not ready
        waiting_for = [jid for jid, session in self.sessions.items() if not session.ready.is_set()]
        if waiting_for:
            await self._send(sender_jid, "Waiting for the other team to announce themselve as ready to race...")

    # internal coroutines
    async def _pair_and_setup(self, sender_jid: str) -> None:
        """Scan, pair gates and store them in the session, then notify the sender

        Args:
            sender_jid (str):  XMPP address of the sender
        """
        logger.info(f"[Coordinator] -- Starting pairing for {sender_jid}...")

        # handling multiple pairing demands (first one, then the other)
        in_waiting_line = self._pairing_lock.locked()
        if in_waiting_line:
            logger.info(f"[Coordinator] -- Pairing busy, {sender_jid} is queued")
            await self._send(sender_jid, "A pairing is already in progress. Please wait...")

        async with self._pairing_lock:
            if in_waiting_line:
                logger.info(f"[Coordinator] -- It's now {sender_jid}'s turn to pair")
                await self._send(sender_jid, "The pairing for your gates is now starting...")

            gates = await gates_finder()
            gates = await gates_configurator(gates, self._pair_color)
            self._pair_color +=1

        self.sessions[sender_jid].start_gate = gates[0]
        self.sessions[sender_jid].end_gate   = gates[1]

        await self._send(sender_jid, "Pairing successful !")
        logger.info(f"[Coordinator] Pairing done -- {sender_jid} can now send 'ready'")

        if self.sessions[sender_jid].ready.is_set():
            asyncio.create_task(self._launch_race())


    async def _launch_race(self) -> None:
        """Try to start races in all active sessions"""
        if self._launch_lock.locked():
            return
        async with self._launch_lock:
            for session in self.sessions.values():
                if session.start_gate is None or not session.ready.is_set():
                    return

            sender_jids = list(self.sessions.keys())
            sessions    = list(self.sessions.values())

            logger.info("[Coordinator] Every session are ready : launching the race...")

            async def _countdown():
                """Countdown procedure
                """
                for count in ("3", "2", "1", "Go !!!"):
                    await asyncio.gather(*[self._send(jid, count) for jid in sender_jids])
                    if count == "Go !!!":
                        self._race_start_time = time.monotonic()
                    else:
                        await asyncio.sleep(1)

            start_gates = [session.start_gate for session in sessions]
            await asyncio.gather(_countdown(), *[gate.starting_blink() for gate in start_gates])

            results: list[tuple[float, float]] = await asyncio.gather(*[
                _run_race(session.start_gate, session.end_gate) for session in sessions
            ])

            individual_times = [result[0] for result in results]
            # total time = time of the race from go!! to last racer finished
            total_time = max(result[1] for result in results) - self._race_start_time
            logger.info(f"[Coordinator] Total race time: {total_time:.3f}s")

            # Time results transmission
            await asyncio.gather(*[
                self._send(jid, f"Total race time: {total_time:.3f}s") for jid in sender_jids
            ])
            await asyncio.gather(*[
                self._send(jid, f"The race is finished! Your race time is: {t:.3f}s")
                for jid, t in zip(sender_jids, individual_times)
            ])
            # cleanup session
            self.sessions.clear()

            await asyncio.sleep(3)
            logger.info("[Coordinator] Race complete — all sessions closed, waiting for new connections to start a new race")

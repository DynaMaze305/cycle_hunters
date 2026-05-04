import asyncio
import logging
import time
from typing import Awaitable, Callable

from .gatePairer import find_two_gates, configure_pair_of_gates
from .race_session import RaceSession

logger = logging.getLogger("TimeKeeperCoordinator")

SendFn = Callable[[str, str], Awaitable[None]]

class TimeKeeperCoordinator:
    """Coordinator : manage the full timekeeper process :
        1 - handle commands from received XMPP messages
        2 - handle gate and raceSession configuration
        3 - handle time keeping and transmission
    """

    def __init__(self, send: SendFn):
        self._send = send
        # sessions dict structure: sender_jid -> {"race_session": RaceSession | None,
        #                                         "ready": asyncio.Event,
        #                                         "result": asyncio.Future}
        self.sessions: dict[str, dict] = {}
        self._pairing_lock = asyncio.Lock()
        self._launch_lock  = asyncio.Lock()

    # command handlers
    async def on_start(self, sender_jid: str) -> None:
        """Register a new race session for the specific sender and launch gate pairing.

        Args:
            sender_jid (str): XMPP address of the Logger that initiated the race.
        """
        # check if sender already has a session
        if sender_jid in self.sessions:
            logger.warning(f"[Coordinator] Session already exists for {sender_jid} >> so, ignoring request...")
            return
        
        session_id = len(self.sessions)

        loop = asyncio.get_running_loop()
        self.sessions[sender_jid] = {"race_session": None, 
                                     "ready": asyncio.Event(), 
                                     "result": loop.create_future()}

        asyncio.create_task(self._pair_and_setup(sender_jid, session_id))

    async def on_ready(self, sender_jid: str) -> None:
        """Note that the sender's session is ready and try to start all active raceSessions (must have all been ready)

        Args:
            sender_jid (str): XMPP address of the Logger that signal being ready.
        """
        # Check that the sender possess a session
        if sender_jid not in self.sessions:
            logger.warning(f"[Coordinator] No session for {sender_jid} -- ignoring 'ready'")
            return
        
        self.sessions[sender_jid]["ready"].set()
        asyncio.create_task(self._launch_race())

        # To inform the 1rst team to announce ready that the opponent one isn't and explaining why they wait
        waiting_for = [jid for jid,
                       value in self.sessions.items() 
                            if not value["ready"].is_set()]
        if waiting_for:
            await self._send(sender_jid, "Waiting for the other team to announce themselve as ready to race...")

    # internal coroutines
    async def _pair_and_setup(self, sender_jid: str, session_id: int) -> None:
        """Scan, pair gates, create a RaceSession and then notify the sender."""
        logger.info(f"[Coordinator] -- Starting pairing for {sender_jid}...")

        in_waiting_line = self._pairing_lock.locked()
        # True if pairing already in progress from another Logger
        if in_waiting_line:
            logger.info(f"[Coordinator] -- Pairing busy, {sender_jid} is queued")
            await self._send(sender_jid, "A pairing is already in progress. Please wait...")

        # 1rst launching the pairing process acquier the lock
        async with self._pairing_lock:
            if in_waiting_line:
                logger.info(f"[Coordinator] -- It's now {sender_jid}'s turn to pair")
                await self._send(sender_jid, "The pairing for your gates is now starting...")

            pair  = await find_two_gates()
            gates = await configure_pair_of_gates(pair)

        session = RaceSession(
            session_id = session_id,
            start_gate = gates[0],
            end_gate   = gates[1],
        )

        async def on_event(event: str, raceSession: RaceSession) -> None:
            """Save race time, and stop raceSession at race end.
            """
            if event != "race_finish":
                return
            individual_time = raceSession.time
            self.sessions.pop(sender_jid)["result"].set_result(individual_time)
            await raceSession.end_gate.finish_blink()
            logger.info(f"[Coordinator] -- Race done for {sender_jid}: {individual_time:.3f}s")
            await raceSession.stop()

        session.subscribe(on_event)
        self.sessions[sender_jid]["race_session"] = session

        await self._send(sender_jid, f"paired start:{gates[0].color} end:{gates[1].color}")
        logger.info(f"[Coordinator] Pairing done -- {sender_jid} can now send 'ready'")

        # "ready" may have arrived while pairing was running -- re-check the barrier
        if self.sessions[sender_jid]["ready"].is_set():
            asyncio.create_task(self._launch_race())

    async def _launch_race(self) -> None:
        """Try to start races in all active sessions"""
        if self._launch_lock.locked():
            return
        async with self._launch_lock:
            for value in self.sessions.values():
                if value["race_session"] is None or not value["ready"].is_set():
                    return

            sender_jids    = list(self.sessions.keys())
            session_list   = [values["race_session"] for values in self.sessions.values()]
            start_gates    = [values["race_session"].start_gate for values in self.sessions.values()]
            results = [self.sessions[jid]["result"] for jid in sender_jids]

            logger.info("[Coordinator] Every session are ready : launching the race")

            global_race_start_time: float = 0.0

            async def _countdown():
                nonlocal global_race_start_time
                for count in ("3", "2", "1", "Go !!!"):
                    await asyncio.gather(*[self._send(jid, count) for jid in sender_jids])
                    if count == "Go !!!":
                        global_race_start_time = time.monotonic()
                    else:
                        await asyncio.sleep(1)

            await asyncio.gather(_countdown(), *[gate.starting_blink() for gate in start_gates])
            await asyncio.gather(*[raceSession.start() for raceSession in session_list])

            individual_times: list[float] = list(await asyncio.gather(*results))

            total_time = time.monotonic() - global_race_start_time
            logger.info(f"[Coordinator] Total race time: {total_time:.3f}s")

            await asyncio.gather(*[
                self._send(jid, f"Total race time: {total_time:.3f}s") for jid in sender_jids])
            
            await asyncio.gather(*[
                self._send(jid, f"The race is finished! Your race time is: {t:.3f}s")
                for jid, t in zip(sender_jids, individual_times)
            ])

            await asyncio.sleep(3)
            logger.info("[Coordinator] Race complete — all sessions closed, waiting for new connections to start a new race")

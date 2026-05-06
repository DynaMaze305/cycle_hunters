import asyncio
import logging
import time
from enum import Enum
from .gate import Gate

logger = logging.getLogger("RaceSession")

# https://stackoverflow.com/questions/37601644/python-whats-the-enum-type-good-for
class RaceState(Enum):
    WAITING  = "waiting"
    RUNNING  = "running"
    FINISHED = "finished"

class RaceSession:

    def __init__(self, session_id: int, start_gate: Gate, end_gate: Gate):
        self.session_id = session_id
        self.start_gate = start_gate
        self.end_gate   = end_gate
        self.state      = RaceState.WAITING
        self.time: float | None = None
        self._observers: list      = []
        self._task: asyncio.Task | None = None

# Observer pattern : https://refactoring.guru/design-patterns/observer/python/example
    def subscribe(self, callback) -> None:
        """Register an observer — callback(event: str, session: RaceSession)"""
        self._observers.append(callback)

    def unsubscribe(self, callback) -> None:
        """Remove a registered observer"""
        self._observers.remove(callback)

    def _notify(self, event: str) -> None:
        """Dispatch an event to all observers"""
        for cb in self._observers:
            return_value = cb(event, self)

            if asyncio.iscoroutine(return_value):
                asyncio.create_task(return_value)

    async def start(self) -> None:
        """Connect gates and launch the time loop"""
        await self.start_gate.connect()
        await self.end_gate.connect()
        logger.debug(f"[RaceSession {self.session_id}] -- Initialized & waiting for start_gate to be triggered...")
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Cancel the time loop, disconnect gates and notify the observers"""
        if self._task:
            self._task.cancel()
            # https://stackoverflow.com/questions/56052748/python-asyncio-task-cancellation
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self.start_gate.disconnect()
        await self.end_gate.disconnect()

        self._notify("session_ended")

    async def _run_loop(self) -> None:
        while True:
            # Starting procedures
            self.start_gate.reset_crossed()
            self.end_gate.reset_crossed()
            self.state = RaceState.WAITING

            # When start_gate is crossed -> start race
            await self.start_gate.wait_crossed()
            t0 = time.monotonic()
            self.state = RaceState.RUNNING
            logger.info(f"[RaceSession {self.session_id}] -- Race started")
            self._notify("race_start")

            blink_task = asyncio.create_task(self.start_gate.running_blink())
            await self.end_gate.set_led(255, 255, 255)

            # When end_gate is crossed -> end race
            await self.end_gate.wait_crossed()
            blink_task.cancel()
            try:
                await blink_task
            except asyncio.CancelledError:
                pass

            self.time = time.monotonic() - t0
            self.state = RaceState.FINISHED
            logger.info(f"[RaceSession {self.session_id}] -- Race finished: {self.time:.3f}s")
            self._notify("race_finish")

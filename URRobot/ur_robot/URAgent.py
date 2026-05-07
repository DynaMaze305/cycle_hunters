import asyncio
import json
import os
import logging
import math

# from urbasic.URBasic -> does not work when running
from URBasic import ISCoin
from URBasic import Joint6D, TCP6D

from spade.agent import Agent, Template
from spade.behaviour import CyclicBehaviour, State, FSMBehaviour
from spade.message import Message

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("URAgent")

# Enable SPADE and XMPP specific logging
# for log_name in ["spade", "aioxmpp", "xmpp"]:
#     log = logging.getLogger(log_name)
#     log.setLevel(logging.DEBUG)
#     log.propagate = True

# Joint in radians and distance in meters
def load_joint_env(name: str) -> Joint6D:
    raw = os.environ.get(name)
    if raw is None:
        raise RuntimeError(f"Missing environment variable: {name}")
    logger.info(f"{raw}")
    try:
        vals = raw.split(' ')
        if len(vals) != 6:
            raise ValueError(f"{name} must contain 6 joint values")
        return Joint6D.createFromRadians(*[math.radians(float(v)) for v in vals])
    except Exception as e:
        raise RuntimeError(f"Invalid joint definition in {name}: {e}")

UR_HOMEJ = load_joint_env("UR_HOMEJ")
UR_WORK_POSEJ = load_joint_env("UR_WORK_POSEJ")
UR_DROP_POSITION = load_joint_env("UR_DROP_POSITION")

UR_ABOVE_DISTANCE = float(os.environ.get("UR_ABOVE_DISTANCE", "0.12"))
UR_PICK_DISTANCE = float(os.environ.get("UR_PICK_DISTANCE", "0.09"))


class URAgent(Agent):
    class XMPPCommandListener(CyclicBehaviour):
        """
        Command Listener for the URAgent.

        Hold the UR robot and process the message receive by the agent

        Commands
        --------
        register
            Register the agent for broadcast.
        pick <data>
            - Make the UR robot remove an object by launching the FSM, dimension in meters
            {
                "pick": {"x": float, "y": float},
            }
        """
        async def on_start(self):
            """
            Start the Command Listener
            """
            robot_ip = os.environ.get("UR_ROBOT_IP", "10.30.5.158")
            self.ur_robot = ISCoin(robot_ip)
            self.agent.running = False
            logger.info("[Behaviour] Command listener started")

        async def run(self):
            """
            Listen for incoming XMPP messages and process messages.
            """
            logger.info("[Behaviour] Waiting for messages...")
            msg = await self.receive(timeout=1)

            if msg:
                logger.info(f"[Behaviour] Received message: {msg.body}")
                await self.process_message(msg)
            else:
                logger.debug("[Behaviour] No message received")

        async def process_message(self, msg: Message):
            """
            Function to process message.
            """
            command = msg.body

            if command == "register":
                if str(msg.sender) not in self.agent.register_list:
                    self.agent.register_list.append(str(msg.sender))
                    await self.agent.send_message(self, msg, "ur_robot register done")
                else:
                    await self.agent.send_message(self, msg, "ur_robot register already")

            elif command.startswith("pick "):
                if self.agent.running:
                    await self.agent.send_message(self, msg, "ur_robot busy")
                    return
                self.agent.running = True
                try:
                    raw = command.split(" ", 1)
                    logger.error(f"RAW COMMAND: {repr(raw[1])}")
                    data = json.loads(raw[1])
                    pick = data["pick"]
                except Exception as e:
                    logger.error(f"Invalid message format: {e}")
                    await self.agent.send_error(self, msg, f"ur_robot invalid data {e}")
                    return
                fsm = self.agent.URBasicGrab(self.ur_robot, msg, pick)
                self.agent.behaviour = fsm
                self.agent.add_behaviour(fsm)

    # -----------------------------
    # FSM BEHAVIOUR
    # -----------------------------
    class URBasicGrab(FSMBehaviour):
        def __init__(self, ur_robot: ISCoin, msg: Message, pick: dict):
            """
            Init the State machine to grab an object.

            Parameters
            ----------
            ur_robot: ISCoin
                The robot that will execute the command.
            msg: Message
                The message that launch the process -> to retrive sender.
            pick: dict
                A dictionnary storying the x and y coordinates of the object to pick.
            place: dict
                A dictionnary storying the x and y coordinates wher to drop the object.
            """
            super().__init__()
            self.ur_robot = ur_robot.robot_control
            self.gripper = ur_robot.gripper

            if not self.gripper.isActivated():
                self.gripper.activate()

            self.msg = msg
            self.pick = pick

            self.z_hover = os.environ.get("UR_ABOVE_DISTANCE", 0.25)
            self.z_table = os.environ.get("UR_PICK_DISTANCE", 0.10)
            self.error = None
            self.picked = False

        async def on_start(self):
            """
            Initialisation of the state machine workflow
            """
            logger.info("[FSM] Starting URBasicGrab FSM")
            self.add_state("move_home", self.MoveHome(), initial=True)
            self.add_state("move_work_pose", self.MoveWorkPose())
            self.add_state("move_above_pick", self.MoveAbovePick())
            self.add_state("descend_pick", self.DescendPick())
            self.add_state("grab", self.Grab())
            self.add_state("grab_fallback", self.GrabFallback())
            self.add_state("lift_pick", self.LiftPick())
            self.add_state("move_above_place", self.MoveAbovePlace())
            self.add_state("release", self.Release())
            self.add_state("return_work_pose", self.MoveWorkPose())
            self.add_state("return_home", self.MoveHome())
            self.add_state("finish", self.Finish())

            self.add_transition("move_home", "move_work_pose")
            self.add_transition("move_work_pose", "move_above_pick")
            self.add_transition("move_above_pick", "descend_pick")
            self.add_transition("descend_pick", "grab")
            self.add_transition("grab", "lift_pick")
            self.add_transition("grab", "grab_fallback")
            self.add_transition("grab_fallback", "return_work_pose")
            self.add_transition("lift_pick", "move_above_place")
            self.add_transition("move_above_place", "release")
            self.add_transition("release", "return_work_pose")
            self.add_transition("return_work_pose", "return_home")
            self.add_transition("return_home", "finish")

            self.add_state("error", self.ErrorState())
            self.add_transition("*", "error")

        async def on_end(self):
            """
            Last action executed at the end of the State Machine.
            """
            self.gripper.deactivate()
            logger.info("[FSM] URBasicGrab finished")
            self.agent.running = False
            await self.agent.broadcast(self, "ur_robot free")

        def _tcp(self, x, y, z):
            """
            Conversion XYZ coordinate in TCP6D to grab object on a table.
            """
            return TCP6D.createFromMetersRadians(x, y, z, 0, 3.14, 0)

        async def safe_call(self, func, pos: TCP6D|Joint6D = None):
            """
            Safe call function to process robot function without blocking the Agent.
            """
            try:
                logger.info(f"[SAFE] {func.__name__}")
                loop = asyncio.get_running_loop()
                if pos:
                    logger.info(f"[SAFE] {pos}")
                    await loop.run_in_executor(None, lambda: func(pos))
                else:
                    await loop.run_in_executor(None, lambda: func())
            except Exception as e:
                logger.error(f"[FSM] Robot error: {e}")
                self.error = str(e)
                self.set_next_state("error")


        # -----------------------------
        # STATES
        # -----------------------------
        class ErrorState(State):
            """
            Error state in case of derangement during robot execution.
            """
            async def run(self):
                """
                Send error message and kill FMS wihtout re-activate the robot.
                """
                logger.error("[FSM] Entered error state")
                await self.agent.send_error(self, self.agent.behaviour.msg, f"ur_robot error execution {self.agent.behaviour.error}")

                # Kill FSM
                self.kill()

        class MoveHome(State):
            """
            State to move to home position
            """
            async def run(self):
                """
                Move robot to home position
                """
                logger.info(f"[FSM] Moving to home {type(UR_HOMEJ)}")
                await self.agent.behaviour.safe_call(self.agent.behaviour.ur_robot.movej, UR_HOMEJ)
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(0.1)
                # Next state depends on where we are in the sequence
                if self.agent.behaviour.picked:
                    self.set_next_state("finish")
                else:
                    self.set_next_state("move_work_pose")

        class MoveWorkPose(State):
            """
            State to move to the initial work position
            """
            async def run(self):
                """
                Move robot to work position
                """
                logger.info("[FSM] Moving to work pose")
                await self.agent.behaviour.safe_call(self.agent.behaviour.ur_robot.movej, UR_WORK_POSEJ)
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(0.1)
                # Next state depends on where we are in the sequence
                if self.agent.behaviour.picked:
                    self.set_next_state("return_home")
                else:
                    self.set_next_state("move_above_pick")

        class MoveAbovePick(State):
            """
            State to move above the pick position
            """
            async def run(self):
                """
                Move robot above the pick position
                """
                x, y = self.agent.behaviour.pick["x"], self.agent.behaviour.pick["y"]
                logger.info(f"[FSM] Moving above pick: {x}, {y}")
                await self.agent.behaviour.safe_call(self.agent.behaviour.ur_robot.movel, self.agent.behaviour._tcp(x, y, self.agent.behaviour.z_hover))
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(0.1)
                self.set_next_state("descend_pick")

        class DescendPick(State):
            """
            State to descend pick the object
            """
            async def run(self):
                """
                Move robot to pick the object
                """
                x, y = self.agent.behaviour.pick["x"], self.agent.behaviour.pick["y"]
                logger.info("[FSM] Descending to pick")
                await self.agent.behaviour.safe_call(self.agent.behaviour.gripper.open)
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(0.1)
                await self.agent.behaviour.safe_call(self.agent.behaviour.ur_robot.movel, self.agent.behaviour._tcp(x, y, self.agent.behaviour.z_table))
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(0.1)
                self.set_next_state("grab")

        class Grab(State):
            """
            State to grab the object
            """
            async def run(self):
                """
                Close the gripper and test if it effectively grab the object
                """
                logger.info("[FSM] Closing gripper")
                await self.agent.behaviour.safe_call(self.agent.behaviour.gripper.close)
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(1.0)
                self.agent.behaviour.picked = True
                if True:# self.agent.behaviour.gripper.hasDetectedObject():
                    self.set_next_state("lift_pick")
                else:
                    self.set_next_state("grab_fallback")

        class GrabFallback(State):
            """
            State if no object was grab
            """
            async def run(self):
                """
                Open the gripper and send error message
                """
                logger.info("[FSM] No object grab")
                await self.agent.behaviour.safe_call(self.agent.behaviour.gripper.open)
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(0.1)
                await self.agent.send_error(self, self.agent.behaviour.msg, f"ur_robot error grab nothing")
                await asyncio.sleep(0.1)

                self.set_next_state("return_work_pose")

        class LiftPick(State):
            """
            State to lift the picked object
            """
            async def run(self):
                """
                Move robot above to deplace the object
                """
                x, y = self.agent.behaviour.pick["x"], self.agent.behaviour.pick["y"]
                logger.info("[FSM] Lifting object")
                await self.agent.behaviour.safe_call(self.agent.behaviour.ur_robot.movel, self.agent.behaviour._tcp(x, y, self.agent.behaviour.z_hover))
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(0.1)
                self.set_next_state("move_above_place")

        class MoveAbovePlace(State):
            """
            State to move the above the dropping place
            """
            async def run(self):
                """
                Move robot above the dropping place
                """
                logger.info("[FSM] Moving above place")
                await self.agent.behaviour.safe_call(self.agent.behaviour.ur_robot.movej, UR_DROP_POSITION)
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(0.1)
                self.set_next_state("release")

        class Release(State):
            """
            State to drop the object
            """
            async def run(self):
                """
                Open the gripper
                """
                logger.info("[FSM] Opening gripper")
                await self.agent.behaviour.safe_call(self.agent.behaviour.gripper.open)
                if self.agent.behaviour.error:
                    return
                await asyncio.sleep(1.0)
                self.set_next_state("return_work_pose")

        class Finish(State):
            """
            State finnal of the State Machine
            """
            async def run(self):
                """
                Send message as the robotr complet is task
                """
                logger.info("[FSM] Sending completion message")
                await self.agent.send_message(self, self.agent.behaviour.msg, "ur_robot complet")
                await asyncio.sleep(0.1)

                # Kill FSM
                self.kill()

    # -----------------------------
    # MESSAGE HELPER
    # -----------------------------
    async def send_message(self, behaviour, msg: Message, text: str):
        """
        Helper function to send message to sender

        Parameters
        ----------
        msg: Message
            Message to respond from
        text: str
            The reply body
        """
        reply = Message(to=str(msg.sender))
        reply.set_metadata("performative", "inform")
        reply.body = text
        await behaviour.send(reply)
        logger.info(f"[Behaviour] Sent message ({text}) to {msg.sender}")

    async def send_error(self, behaviour, msg: Message, text:str):
        """
        Helper function to send message to sender: used to send error message

        Parameters
        ----------
        msg: Message
            Message to respond from
        text: str
            The reply body
        """
        reply = Message(to=str(msg.sender))
        reply.set_metadata("performative", "inform")
        reply.body = text
        await behaviour.send(reply)
        logger.info(f"[Behaviour] Sent error ({text}) to {msg.sender}")

    async def broadcast(self, behaviour, body: str):
        """
        Helper to broadcast message to all regiseter agents

        Parameters
        ----------
        body: str
            The message to broadcast.
        """
        for jid in self.register_list:
            msg = Message(to=jid)
            msg.set_metadata("performative", "inform")
            msg.body = body
            await behaviour.send(msg)

    # -----------------------------
    # AGENT SETUP
    # -----------------------------
    async def setup(self):
        """
        Setup the URAgent
        """
        logger.info("[Agent] URAgent starting setup...")
        logger.info(f"[Agent] Will connect as {self.jid}")

        self.register_list = []
        self.running = True
        self.behaviour: FSMBehaviour = None

        template = Template()
        template.set_metadata("performative", "request")
        self.add_behaviour(self.XMPPCommandListener(), template=template)

        logger.info("[Agent] Behaviours added, setup complete.")

import asyncio
import os
import logging

from spade.agent import Agent

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("Main")

# Enable SPADE and XMPP specific logging
for log_name in ["spade", "aioxmpp", "xmpp"]:
    log = logging.getLogger(log_name)
    log.setLevel(logging.DEBUG)
    log.propagate = True

from ur_robot.URAgent import URAgent
async def start_ur_agent(run_agent: bool) -> Agent:
    # Read XMPP credentials and configuration from environment variables
    xmpp_jid = os.environ.get("UR_AGENT")
    xmpp_password = os.environ.get("XMPP_PASSWORD", "top_secret")
        
    # Log the configuration for debugging purposes (masking the password)
    logger.info("Starting Test Camera Receiver XMPP Agent")
    logger.info(f"XMPP JID: {xmpp_jid}")
    logger.info(f"XMPP Password: {'*' * len(xmpp_password)}")
    
    try:
        # Create and start the agent
        test_agent = URAgent(
            jid=xmpp_jid,
            password=xmpp_password,
            verify_security=False
        )
        
        if run_agent:
            logger.info("URAgent created, attempting to start...")
            await test_agent.start(auto_register=True)
            logger.info("URAgent started successfully!")
        else:
            logger.info("URAgent created, but will not run!")
        return test_agent

    except Exception as e:
        logger.error(f"Error starting agent: {str(e)}", exc_info=True)
        raise e

from ur_robot.TESTURAgent import TESTURAgent
async def start_test_ur_agent(run_agent: bool) -> Agent:
    # Read XMPP credentials and configuration from environment variables
    xmpp_domain = os.environ.get("XMPP_DOMAIN", "isc-coordinator2.lan")
    xmpp_jid = f"test@{xmpp_domain}"
    xmpp_password = os.environ.get("XMPP_PASSWORD", "top_secret")
        
    # Log the configuration for debugging purposes (masking the password)
    logger.info("Starting Test Camera Receiver XMPP Agent")
    logger.info(f"XMPP JID: {xmpp_jid}")
    logger.info(f"XMPP Password: {'*' * len(xmpp_password)}")
    
    try:
        # Create and start the agent
        test_agent = TESTURAgent(
            jid=xmpp_jid,
            password=xmpp_password,
            verify_security=False
        )
        
        if run_agent:
            logger.info("URAgent created, attempting to start...")
            await test_agent.start(auto_register=True)
            logger.info("URAgent started successfully!")
        else:
            logger.info("URAgent created, but will not run!")
        return test_agent

    except Exception as e:
        logger.error(f"Error starting agent: {str(e)}", exc_info=True)
        raise e


async def main():
    ur_agent = await start_ur_agent(True)
    test_ur_agent = None
    if os.environ.get("RUN_TEST_UR_AGENT", "0") == "1":
        test_ur_agent = await start_test_ur_agent(True)

    if ur_agent is None:
        logger.error("One or more agents failed to start. Exiting.")
        return

    logger.info("Agents started successfully")

    try:
        while True:
            await asyncio.sleep(5)
            running = False
            logger.info("Display alive agents:")
            if ur_agent:
                if ur_agent.is_alive():
                    logger.info("URAgent is alive and running...")
                    running = True

            if not running:
                break

    except asyncio.CancelledError:
        logger.warning("Main loop cancelled")

    finally:
        logger.info("Stopping agents...")
        await ur_agent.stop()
        if test_ur_agent:
            await test_ur_agent.stop()
        logger.info("All agents stopped cleanly")
        
if __name__ == "__main__":
    try:
      asyncio.run(main())
    except Exception as e:
        logger.critical(f"Critical error in main loop: {str(e)}", exc_info=True)

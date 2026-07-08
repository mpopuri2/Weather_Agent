import logging
import time

logging.basicConfig(filename = "agent.log", level = logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s" )
current_log_time = time.strftime("%Y%m%d_%H%M%S")
logging.info("\n\n"+"---------"*5 + current_log_time +"---------"*5 + "\n\n")

def log_info(message : str):

    logging.info(message)

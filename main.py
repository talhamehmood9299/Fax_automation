import sys
import time
import logging
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from process_fax import process_fax
from talkehr_agent import TalkEHRBot
from doc_agent import convert_document


CHROMEDRIVER_PATH = "/home/talha-mehmood/Documents/Fax_automation/chromedriver"
DEBUGGER_ADDRESS  = "localhost:9222"
SLEEP_BETWEEN_OK_RUNS = 3


def build_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", DEBUGGER_ADDRESS)
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    time.sleep(2)
    return driver


def run_once(bot: TalkEHRBot) -> bool:
    try:
        link = bot.get_url()
        if not link:
            logging.error("No URL returned by bot.get_url(); aborting.")
            return False
        md = convert_document(link)
        response = process_fax(md)
        logging.info("LLM response: %s", response)
        date_of_birth = response.get("date_of_birth", "")
        patient_name  = response.get("patient_name", "")
        provider_name = response.get("provider_name", "")
        doc_type      = response.get("doc_type", "")
        doc_subtype   = response.get("doc_subtype", "")
        comment       = response.get("comment", "")

        if not all([patient_name, doc_type, provider_name]):
            logging.error("One or more required fields missing after correction. Skipping fax.")
            bot.cancel_button()
            return True

        comment_with_subtype = f"**{doc_subtype}**\n\n{comment}" if doc_subtype else comment
        logging.info("Proceeding with possibly corrected values…")


        # 1) Patient
        if not bot.select_patient(date_of_birth, patient_name):
            logging.warning("Patient selection failed. Saving and continuing to next fax.")
            try:
                bot.cancel_button()
                logging.info("Saved without patient.")
                return True   # success for the loop; move on to next
            except Exception as e:
                logging.error("Save after patient failure also failed: %s", e)
                return False

        time.sleep(1)
        # 2) Doc type
        if not bot.select_doc_type(doc_type):
            logging.error("Doc type '%s' not found. Aborting.", doc_type)
            return False

        time.sleep(1)
        # 3) Doc subtype (optional—only check if provided)
        if doc_subtype and not bot.select_doc_sub_type(doc_subtype):
            logging.error("Doc subtype '%s' not found. Aborting.", doc_subtype)
            return False

        time.sleep(1)
        # 4) Assigned To
        if not bot.select_assigned_to(provider_name):
            logging.error("Provider '%s' not found in Assigned To options. Aborting.", provider_name)
            return False

        time.sleep(1)
        # 5) Comments
        if not bot.add_comments(comment_with_subtype):
            logging.error("Failed to add comments. Aborting.")
            return False

        # 6) Save without further confirmation (data already reviewed)
        bot.save_button()
        time.sleep(3)
        logging.info("All selections completed successfully (after correction stage).")
        return True

    except Exception as e:
        logging.error("Unhandled exception in run_once(): %s", e)
        traceback.print_exc()
        return False

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    driver = None
    try:
        time.sleep(2)
        driver = build_driver()
        bot = TalkEHRBot(driver)

        while True:
            ok = run_once(bot)
            if not ok:
                logging.info("Stopping immediately due to failure.")
                sys.exit(1)
            # success → start again
            logging.info("Cycle finished successfully. Restarting after %ss…", SLEEP_BETWEEN_OK_RUNS)
            time.sleep(SLEEP_BETWEEN_OK_RUNS)

    except KeyboardInterrupt:
        logging.info("Interrupted by user. Shutting down…")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        logging.error("Fatal error in main(): %s", e)
        traceback.print_exc()
        sys.exit(2)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

if __name__ == "__main__":
    main()

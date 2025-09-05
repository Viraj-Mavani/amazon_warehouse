# amazon_job_bot.py
import os
import re
import time
import logging
import random
from bs4 import BeautifulSoup
import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException,NoSuchElementException,StaleElementReferenceException,ElementClickInterceptedException


# -------------------------------
# CONFIGURATION
# -------------------------------
# URL = "https://hiring.amazon.com/search/warehouse-jobs"
URL = "https://hiring.amazon.ca/search/warehouse-jobs?cmpid=ATLTBX1796H10"
JOB_TITLE = "Delivery Station Warehouse Associate"
REFRESH_INTERVAL = (5, 8)   # Random refresh interval (min, max seconds)
MAX_ATTEMPTS = 100  # Maximum refresh attempts before giving up
BLOCK_WAIT_TIME = 3600  # 1 hour wait if blocked (in seconds)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("amazon_job_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------------------------
# HELPER FUNCTIONS
# -------------------------------
def setup_driver():
    """Initialize Selenium WebDriver with required options."""

    chromedriver_autoinstaller.install()
   
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # options.add_argument('--window-size=1920,1080') 
    # options.add_argument('--headless')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--incognito')
    options.add_argument("--no-sandbox")
    # options.add_argument("--disable-infobars")
    # options.add_argument("--disable-dev-shm-usage")
    # options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)


    ########### Auto chromedriver ###########
    # chromedriver_autoinstaller.install()
    driver = webdriver.Chrome(options=options)
    # driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    ########## Manual chromedriver ##########
    # service = Service(Driver_path)
    # driver = webdriver.Chrome(service=service, options=options)

    return driver


def safe_click(driver, by, locator, timeout=10):
    """Wait and click an element safely."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, locator))
        )
        scroll(driver, element)
        element.click()
        return True
    except (TimeoutException, ElementClickInterceptedException, NoSuchElementException) as e:
        logger.warning(f"[!] Could not click element {locator}: {str(e)}")
        return False
    
    
def scroll(driver, input_element):
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center', inline: 'center'});", input_element)
    time.sleep(0.2)


# def is_blocked(driver):
#     """Check if we've been blocked by Amazon."""
#     blocked_indicators = [
#         "captcha",
#         "blocked",
#         "access denied",
#         "too many requests",
#         "security check"
#     ]
    
#     page_source = driver.page_source.lower()
#     return any(indicator in page_source for indicator in blocked_indicators)


def refresh_page(driver):
    """Refresh the page with random delay to avoid detection."""
    wait_time = random.randint(*REFRESH_INTERVAL)
    logger.info(f"Waiting {wait_time} sec before next check...)")
    time.sleep(wait_time)

    # # Check if we're blocked before refreshing
    # if is_blocked(driver):
    #     logger.warning("Block detected! Waiting for 1 hour before continuing...")
    #     time.sleep(BLOCK_WAIT_TIME)
    #     # Start fresh session
    #     driver.quit()
    #     return setup_driver()

    driver.refresh()


def check_jobs_available(driver):
    """
    Check if jobs are available or not.
    Returns:
        "none" -> no jobs
        "found" -> jobs available
    """
    try:
        # Case 1: No jobs container
        not_found = driver.find_elements(By.ID, "jobNotFoundContainer")
        if not_found:
            logger.info("[-] No jobs available right now...")
            return "none"

        # Case 2: Jobs found header
        results_header = driver.find_elements(By.XPATH, "//h1[contains(text(),'Total')]")
        if results_header:
            logger.info("[+] Jobs found, proceeding to parse job cards...")
            return "found"

        return "none"  # fallback
    except Exception as e:
        logger.warning(f"[!] Error checking jobs availability: {e}")
        return "none"


def find_job_and_apply(driver):
    """
    Parse job cards and apply if matching criteria.
    """
    try:
        job_cards = driver.find_elements(By.CSS_SELECTOR, "div[data-test-id='JobCard']")
        logger.info(f"[*] Found {len(job_cards)} job cards.")

        for card in job_cards:
            try:
                # --- Extract job fields ---
                name = card.find_element(By.CSS_SELECTOR, "div.jobDetailText strong").text.strip()
                basse_details = card.text

                details = card.find_elements(By.CSS_SELECTOR, "div.jobDetailText")
                job_type = shift_text = duration = pay = location = ""

                for d in details:
                    txt = d.text.strip()
                    if txt.startswith("Type:"):
                        job_type = txt
                    elif txt.startswith("Duration:"):
                        duration = txt
                    elif txt.startswith("Pay rate:"):
                        pay = txt
                    elif "shift available" in txt.lower():
                        shift_text = txt
                    elif not any(x in txt for x in ["Type:", "Duration:", "Pay rate:"]):
                        location = txt

                # Extract shift availability
                shift_text = ""
                try:
                    shift_text = card.find_element(By.XPATH, ".//div[contains(text(),'shift available')]").text
                except Exception as e:
                    logger.error(f"[!] Error in shift_text: {e}")
                    pass

                # --- Apply Rules ---
                if not job_type or ("full time" not in job_type.lower() and "flex time" not in job_type.lower()):
                    logger.info(f"[-] Skipping {name}: invalid type -> {job_type}")
                    continue

                if not shift_text or "0 shift" in shift_text.lower():
                    logger.info(f"[-] Skipping {name}: no available shifts.")
                    continue

                logger.info(f"[+] Found valid job: {name} | {job_type} | {shift_text}")

                # --- Click & Apply ---
                scroll(driver, card)
                card.click()
                # time.sleep(0.2)  # small wait for job detail page
    
                try:
                    no_shift = driver.find_elements(By.XPATH, "//div[contains(text(),'No work shift found')]")
                    if no_shift:
                        logger.info("[!] No work shift available. Going back and refreshing...")
                        driver.back()
                        refresh_page(driver)  # your existing refresh function
                        continue  # skip to next iteration/job
                except Exception as e:
                    logger.warning(f"[!] Error checking shifts: {e}")

                safe_click(driver, By.CSS_SELECTOR, "div.jobDetailScheduleDropdown")
                safe_click(driver, By.CSS_SELECTOR, "div[data-test-id='schedulePanel'] div[data-test-component='StencilReactCard'][role='button']")
                safe_click(driver, By.CSS_SELECTOR, "button[data-test-id='jobDetailApplyButtonDesktop']")
                driver.switch_to.window(driver.window_handles[-1])
                safe_click(driver, By.XPATH, "//button[.//div[text()='Next']]")

                # Finally, click "Create application"
                safe_click(driver, By.XPATH, "//button[.//div[normalize-space(text())='Create Application']]")

                logger.info("[+] Application submitted successfully!")
                return True

            except Exception as inner_e:
                logger.warning(f"[!] Failed processing job card: {inner_e}")
                continue

        return False

    except Exception as e:
        logger.error(f"[!] Error in find_job_and_apply: {e}")
        return False


# -------------------------------
# MAIN LOOP
# -------------------------------
def main():
    logger.info("[+] Starting Amazon Job Bot...")
    driver = setup_driver()
    driver.get(URL)
    time.sleep(2)
    wait = WebDriverWait(driver, 100)


    consent_element = driver.find_element(By.XPATH, "//button[@data-test-id='consentBtn']")
    if consent_element:
        # consentModal_element = driver.find_element(By.XPATH, "//div[@data-test-id='consentModal']/div/button")
        safe_click(driver, By.XPATH, "//button[@data-test-id='consentBtn']")
        safe_click(driver, By.XPATH, "//div[@data-test-id='consentModal']/div/button")
    safe_click(driver, By.XPATH, "//div[@aria-label='Close guided search']")

    # Check login
    try:
        # driver.find_element(By.ID, "ap_email")  # login field
        logger.info("[!] Login required. Please sign in manually.")
        input("Press Enter here after completing login in the browser...")
    except NoSuchElementException:
        logger.info("[+] Already logged in, continuing...")

    while True:
        status = check_jobs_available(driver)

        if status == "none":
            refresh_page(driver)
            continue

        if status == "found":
            job_found = find_job_and_apply(driver)
            if job_found:
                break
            else:
                logger.info("[-] Target job not in current listing. Refreshing...")
                refresh_page(driver)

    print("[*] Script finished.")
    driver.quit()


if __name__ == "__main__":
    main()

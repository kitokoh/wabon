from PyQt5.QtCore import pyqtSignal, QThread
from selenium import webdriver
import json
import os
import platform
import time
import random
import pyperclip
import subprocess
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, WebDriverException,
    ElementClickInterceptedException, StaleElementReferenceException
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from subprocess import CREATE_NO_WINDOW
import chromedriver_autoinstaller
from appLog import log


try:
    log.info("browserCTRL start to dl")
    chromedriver_autoinstaller.install()
except Exception as e:
    log.exception(f"Error during chromedriver_autoinstaller.install(): {e}")
CHROME = 1
FIREFOX = 2
WAIT_TIMEOUT = 15


class Web(QThread):
    __URL = 'https://web.whatsapp.com/'
    driverNum = 0
    lcdNumber_reviewed = pyqtSignal(int)
    lcdNumber_nwa = pyqtSignal(int)
    lcdNumber_wa = pyqtSignal(int)
    LogBox = pyqtSignal(str)
    wa = pyqtSignal(str)
    nwa = pyqtSignal(str)
    EndWork = pyqtSignal(str)
    # WAIT_TIMEOUT = 15 # This is a class attribute, accessed by self.WAIT_TIMEOUT or Web.WAIT_TIMEOUT

    def __init__(self, parent=None, counter_start=0, step='A', numList=None, sleepMin=3, sleepMax=6, text='', path='',
                 Remember=False, browser=1):
        super(Web, self).__init__(parent)

        self.selectors = {}
        try:
            # browserCtrl.py is in the root, selectors.json is in src/
            selector_file_path = os.path.join("src", "selectors.json")
            with open(selector_file_path, "r", encoding="utf-8") as f:
                self.selectors = json.load(f)
            log.info(f"Successfully loaded selectors from {selector_file_path}")
        except FileNotFoundError:
            log.error(f"'{selector_file_path}' not found. Using hardcoded fallback selectors.")
            self.selectors = {
                "login_check_element": "*[data-icon=new-chat-outline]",
                "message_textbox": "//div[@title='Type a message']", # Old selector as fallback
                "attach_button": "//span[@data-icon='attach-menu-plus']", # Old selector
                "media_file_input": "//input[@accept='image/*,video/mp4,video/3gpp,video/quicktime']", # Old selector
                "media_caption_textbox": "//div[@role='textbox'][contains(@class,'selectable-text')]", # Old selector
                "navigation_link": "/html/head/a[@id='whatsappLink']"
            }
            log.warning("Using hardcoded fallback selectors due to missing selectors.json.")
        except json.JSONDecodeError as e:
            log.error(f"Error decoding '{selector_file_path}': {e}. Using hardcoded fallback selectors.")
            self.selectors = {
                "login_check_element": "*[data-icon=new-chat-outline]",
                "message_textbox": "//div[@title='Type a message']",
                "attach_button": "//span[@data-icon='attach-menu-plus']",
                "media_file_input": "//input[@accept='image/*,video/mp4,video/3gpp,video/quicktime']",
                "media_caption_textbox": "//div[@role='textbox'][contains(@class,'selectable-text')]",
                "navigation_link": "/html/head/a[@id='whatsappLink']"
            }
            log.warning("Using hardcoded fallback selectors due to JSON decode error.")
        except Exception as e:
            log.exception(f"Unexpected error loading '{selector_file_path}': {e}")
            self.selectors = {}
            log.error("Selectors could not be loaded. Operations will use hardcoded defaults or may fail if defaults not provided in code.")

        self.counter_start = counter_start
        self.Numbers = numList
        self.step = step
        self.sleepMin = sleepMin
        self.sleepMax = sleepMax
        self.text = text
        self.path = path
        self.remember = Remember
        self.isRunning = True
        try:
            # exist_ok=True prevents error if directory already exists
            os.makedirs('./temp/cache/', exist_ok=True)
        except OSError as e:
            log.error(f"__init__: Error creating ./temp/cache/ directory: {e}")
        # Save Session Section
        self.__platform = platform.system().lower()
        if self.__platform != 'windows' and self.__platform != 'linux':
            raise OSError('Only Windows and Linux are supported for now.')

        self.__browser_choice = 0
        self.__browser_options = None
        self.__browser_user_dir = None
        self.__driver = None
        self.service = Service()
        self.service.creation_flags = CREATE_NO_WINDOW
        if browser == 1:
            self.set_browser(CHROME)
        elif browser == 2:
            self.set_browser(FIREFOX)

        self.__init_browser()

    def driverBk(self):
        option = webdriver.ChromeOptions()
        option.add_argument("--disable-notifications")
        # option.add_argument(fr"--user-data-dir={userDataPath}")
        try:
            try:
                self.__driver = webdriver.Chrome(options=option, service=self.service)
                log.debug("webDriver")
            except WebDriverException as e:
                log.warning(f"WebDriverException during initial Chrome setup with user data dir: {e}. Trying without user data dir.")
                self.__driver = webdriver.Chrome(service=self.service)
        except WebDriverException as e:
            log.error(f"WebDriverException setting up Chrome: {e}. Attempting Firefox.")
            # if not os.path.exists('temp/F.Options'):
            #     os.mkdir('temp/F.Options')
            # optionsF = webdriver.FirefoxOptions()
            # optionsF.add_argument('-headless')  ## hidden Browser
            try:
                self.__driver = webdriver.Firefox()
            except WebDriverException as e_firefox:
                log.critical(f"WebDriverException setting up Firefox as fallback: {e_firefox}. Driver not initialized.")
                self.__driver = None # Ensure driver is None if all attempts fail
        except Exception as e:
            log.exception(f"Unexpected error in driverBk Chrome setup: {e}")
            self.__driver = None # Ensure driver is None if all attempts fail

        if self.__driver: # Only proceed if driver was initialized
            try:
                self.__driver.set_window_position(0, 0)
                self.__driver.set_window_size(1080, 840)
            except WebDriverException as e:
                log.warning(f"Error setting window size/position: {e}")

    def is_logged_in(self):
        status = self.__driver.execute_script(
            "if (document.querySelector('*[data-icon=new-chat-outline]') !== null) { return true } else { return false }"
        )
        return status

    def copyToClipboard(self, text):
        try:  # Copy Text To clipboard
            try:
                subprocess.run("pbcopy", universal_newlines=True, input=text)
            except Exception:
                pyperclip.copy(text)
        except Exception:
            subprocess.run("pbcopy", universal_newlines=True, input=text)
        finally:
            pyperclip.copy(text)

    def ANALYZ(self):
        log.debug("ANALYZ method started.")
        analysis_completed_successfully = False
        try:
            if self.remember:
                log.debug("ANALYZ: remember is True. Checking cache.")
                cacheList = os.listdir('temp/cache/')
                if len(cacheList) != 0:
                    # TODO: Consider adding try-except for access_by_file if it can fail
                    self.access_by_file(f"./temp/cache/{cacheList[0]}")
                    log.debug('ANALYZ: Session recovered from cache.')
                else:
                    log.debug("ANALYZ: Cache empty. Initializing new browser session.")
                    self.driverBk()
                    if not self.__driver: # driverBk failed
                        log.critical("ANALYZ: WebDriver not initialized by driverBk.")
                        self.EndWork.emit("-- Analysis failed: Browser could not start --")
                        return # self.isRunning will be handled by finally
                    self.__driver.get(self.__URL)
            else:
                log.debug("ANALYZ: remember is False. Initializing new browser session.")
                self.driverBk()
                if not self.__driver: # driverBk failed
                    log.critical("ANALYZ: WebDriver not initialized by driverBk.")
                    self.EndWork.emit("-- Analysis failed: Browser could not start --")
                    return # self.isRunning will be handled by finally
                self.__driver.get(self.__URL)

            log.debug(f"ANALYZ: Waiting for login. Step: {self.step}")
            try:
                login_selector = self.selectors.get("login_check_element", "*[data-icon=new-chat-outline]")
                WebDriverWait(self.__driver, 60).until(
                    lambda driver: driver.execute_script(
                        f"return document.querySelector('{login_selector}') !== null;"
                    )
                )
                log.info("ANALYZ: Login successful.")
                self.LogBox.emit("Login Success")
            except TimeoutException:
                log.error(f"ANALYZ: Login timeout: Could not detect WhatsApp Web main interface for step {self.step}.")
                self.EndWork.emit(f"-- Analysis failed: Login timeout --") # step variable might not be 'ANALYZ'
                # self.stop() is called in finally
                return

            log.debug(f"ANALYZ: Processing numbers. Counter start: {self.counter_start}")
            i = 0
            f = 0
            nf = 0
            for num_idx, num in enumerate(self.Numbers):
                logtxt = ""
                nav_link_selector_key = "navigation_link"
                message_textbox_selector_key = "message_textbox"
                try:
                    target_url = f"https.wa.me/{num}"
                    nav_link_xpath = self.selectors.get(nav_link_selector_key, "/html/head/a[@id='whatsappLink']")

                    if not nav_link_xpath:
                        log.error(f"{self.step}: Selector key '{nav_link_selector_key}' not found in selectors.json or config is invalid. Number: {num}.")
                        logtxt = f"Number::{num} => Config error for '{nav_link_selector_key}'."
                        # Manual finally parts before continue
                        i += 1; self.lcdNumber_reviewed.emit(i);
                        if logtxt: self.LogBox.emit(logtxt)
                        nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                        continue

                    if num_idx == 0:
                        execu_create = f"""
                                var whatsappLink = document.createElement('a');
                                whatsappLink.id = 'whatsappLink';
                                whatsappLink.href = "{target_url}";
                                document.head.appendChild(whatsappLink);
                                """
                        self.__driver.execute_script(execu_create)

                    user_element = WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                        EC.presence_of_element_located((By.XPATH, nav_link_xpath))
                    )
                    self.__driver.execute_script(f"arguments[0].setAttribute('href','{target_url}');", user_element)
                    self.__driver.execute_script("arguments[0].click();", user_element)

                    message_textbox_xpath_for_check = self.selectors.get(message_textbox_selector_key, '//div[@title="Type a message"]')
                    if not message_textbox_xpath_for_check:
                        log.error(f"{self.step}: Selector key '{message_textbox_selector_key}' not found for page check. Number: {num}.")
                        logtxt = f"Number::{num} => Config error for '{message_textbox_selector_key}'."
                        i += 1; self.lcdNumber_reviewed.emit(i);
                        if logtxt: self.LogBox.emit(logtxt)
                        nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                        continue

                    WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                        lambda d: "Phone number shared via url is invalid" in d.page_source or \
                                  d.find_elements(By.XPATH, message_textbox_xpath_for_check)
                    )
                    time.sleep(1.5)
                    sourceWeb = self.__driver.page_source

                    if "Phone number shared via url is invalid" in sourceWeb:
                        log.info(f"ANALYZ: Number {num} is invalid.")
                        nf += 1
                        self.lcdNumber_nwa.emit(nf)
                        logtxt = f"Number::{num} => Invalid"
                        self.nwa.emit(f"{num}")
                    else:
                        WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                            EC.presence_of_element_located((By.XPATH, message_textbox_xpath_for_check))
                        )
                        log.info(f"ANALYZ: Number {num} is valid.")
                        f += 1
                        self.lcdNumber_wa.emit(f)
                        logtxt = f"Number::{num} => Valid"
                        self.wa.emit(f"{num}")

                    time.sleep(random.randint(self.sleepMin, self.sleepMax) if self.sleepMin < self.sleepMax else self.sleepMin)

                except TimeoutException as e:
                    log.error(f"ANALYZ: Timeout waiting for element (e.g. '{nav_link_selector_key}' or '{message_textbox_selector_key}') for number {num}. WhatsApp Web UI may have changed, or the selector in 'selectors.json' may need an update. Details: {e}")
                    logtxt = f"Number::{num} => Timeout. Check UI/selectors."
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except (NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e_selenium:
                    log.error(f"ANALYZ: Selenium error ({type(e_selenium).__name__}) with element (e.g. '{nav_link_selector_key}' or '{message_textbox_selector_key}') for number {num}. WhatsApp Web UI may have changed, or a selector in 'selectors.json' may need an update. Details: {e_selenium}")
                    logtxt = f"Number::{num} => Error with element. Check UI/selectors."
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except WebDriverException as e:
                    log.error(f"ANALYZ: WebDriver error processing number {num}: {e}")
                    logtxt = f"Number::{num} => WebDriver Error!"
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except Exception as e:
                    log.exception(f"ANALYZ: Unexpected error processing number {num}: {e}")
                    logtxt = f"Number::{num} => Unexpected Error!"

            analysis_completed_successfully = True # Mark as successful if loop completes

        except WebDriverException as e:
            log.critical(f"ANALYZ: Fatal WebDriverException: {e}")
            self.EndWork.emit("-- Analysis failed: Browser session error --")
        except Exception as e:
            log.exception(f"ANALYZ: Unexpected critical error in main process: {e}")
            self.EndWork.emit("-- Analysis failed: Unexpected error --")
        finally:
            if analysis_completed_successfully:
                log.info("ANALYZ: Analysis completed successfully.")
                self.EndWork.emit("-- analysis completed --")
            # If EndWork was already emitted with failure, it won't be overridden here
            # unless analysis_completed_successfully is True, which it wouldn't be in case of prior fatal error.

            self.isRunning = False
            self.stop() # Ensure driver quits
            log.debug("ANALYZ method finished.")

    def SendTEXT(self):
        log.debug("SendTEXT method started.")
        send_text_completed_successfully = False
        try:
            if self.remember:
                log.debug("SendTEXT: remember is True. Checking cache.")
                cacheList = os.listdir('temp/cache/')
                if len(cacheList) != 0:
                    # TODO: Consider adding try-except for access_by_file
                    self.access_by_file(f"./temp/cache/{cacheList[0]}")
                    log.debug('SendTEXT: Session recovered from cache.')
                else:
                    log.debug("SendTEXT: Cache empty. Initializing new browser session.")
                    self.driverBk()
                    if not self.__driver:
                        log.critical("SendTEXT: WebDriver not initialized by driverBk.")
                        self.EndWork.emit("-- Send Message failed: Browser could not start --")
                        return
                    self.__driver.get(self.__URL)
            else:
                log.debug("SendTEXT: remember is False. Initializing new browser session.")
                self.driverBk()
                if not self.__driver:
                    log.critical("SendTEXT: WebDriver not initialized by driverBk.")
                    self.EndWork.emit("-- Send Message failed: Browser could not start --")
                    return
                self.__driver.get(self.__URL)

            log.debug(f"SendTEXT: Waiting for login. Step: {self.step}")
            try:
                login_selector = self.selectors.get("login_check_element", "*[data-icon=new-chat-outline]")
                WebDriverWait(self.__driver, 60).until(
                    lambda driver: driver.execute_script(
                        f"return document.querySelector('{login_selector}') !== null;"
                    )
                )
                log.info("SendTEXT: Login successful.")
                self.LogBox.emit("Login Success")
            except TimeoutException:
                log.error(f"SendTEXT: Login timeout: Could not detect WhatsApp Web main interface for step {self.step}.")
                self.EndWork.emit(f"-- Send Message failed: Login timeout --") # step variable might not be 'SendTEXT'
                # self.stop() is called in finally
                return

            i = 0
            f = 0
            nf = 0
            log.debug(f"SendTEXT: Processing numbers: {self.Numbers}")
            for num_idx, num in enumerate(self.Numbers):
                logtxt = ""
                nav_link_selector_key = "navigation_link"
                message_textbox_selector_key = "message_textbox"
                try:
                    target_url = f"https.wa.me/{num}"
                    nav_link_xpath = self.selectors.get(nav_link_selector_key, "/html/head/a[@id='whatsappLink']")

                    if not nav_link_xpath:
                        log.error(f"{self.step}: Selector key '{nav_link_selector_key}' not found in selectors.json or config is invalid. Number: {num}.")
                        logtxt = f"Number::{num} => Config error for '{nav_link_selector_key}'."
                        i += 1; self.lcdNumber_reviewed.emit(i);
                        if logtxt: self.LogBox.emit(logtxt)
                        nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                        continue

                    if num_idx == 0:
                        execu_create = f"""
                                var whatsappLink = document.createElement('a');
                                whatsappLink.id = 'whatsappLink';
                                whatsappLink.href = "{target_url}";
                                document.head.appendChild(whatsappLink);
                                """
                        self.__driver.execute_script(execu_create)

                    user_element = WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                        EC.presence_of_element_located((By.XPATH, nav_link_xpath))
                    )
                    self.__driver.execute_script(f"arguments[0].setAttribute('href','{target_url}');", user_element)
                    self.__driver.execute_script("arguments[0].click();", user_element)

                    message_textbox_xpath_for_check = self.selectors.get(message_textbox_selector_key, "//div[@data-testid='compose-box']//div[@role='textbox'][@aria-label='Type a message']")
                    if not message_textbox_xpath_for_check:
                        log.error(f"{self.step}: Selector key '{message_textbox_selector_key}' not found for page check. Number: {num}.")
                        logtxt = f"Number::{num} => Config error for '{message_textbox_selector_key}'."
                        i += 1; self.lcdNumber_reviewed.emit(i);
                        if logtxt: self.LogBox.emit(logtxt)
                        nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                        continue

                    WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                        lambda d: "Phone number shared via url is invalid" in d.page_source or \
                                  d.find_elements(By.XPATH, message_textbox_xpath_for_check)
                    )
                    time.sleep(1.5)
                    sourceWeb = self.__driver.page_source

                    if "Phone number shared via url is invalid" in sourceWeb:
                        log.info(f"SendTEXT: Number {num} is invalid. Not sending.")
                        nf += 1
                        self.lcdNumber_nwa.emit(nf)
                        logtxt = f"Number::{num} => Invalid (No Send)"
                        self.nwa.emit(f"{num}")
                    else:
                        log.info(f"SendTEXT: Number {num} is valid. Attempting to send message.")

                        # This is the same key as message_textbox_xpath_for_check, but re-get for clarity or if it could differ
                        actual_message_textbox_xpath = self.selectors.get(message_textbox_selector_key, "//div[@data-testid='compose-box']//div[@role='textbox'][@aria-label='Type a message']")
                        if not actual_message_textbox_xpath:
                             log.error(f"{self.step}: Selector key '{message_textbox_selector_key}' for sending message not found. Number: {num}.")
                             logtxt = f"Number::{num} => Config error for send textbox '{message_textbox_selector_key}'."
                             i += 1; self.lcdNumber_reviewed.emit(i);
                             if logtxt: self.LogBox.emit(logtxt)
                             nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                             continue

                        textBox = WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                            EC.element_to_be_clickable((By.XPATH, actual_message_textbox_xpath))
                        )
                        textBox.send_keys(Keys.CONTROL, 'v')
                        time.sleep(0.5)
                        textBox.send_keys(Keys.RETURN)
                        time.sleep(1)

                        f += 1
                        self.lcdNumber_wa.emit(f)
                        logtxt = f"Number::{num} => Sent."
                        self.wa.emit(f"{num}")

                    time.sleep(random.randint(self.sleepMin, self.sleepMax) if self.sleepMin < self.sleepMax else self.sleepMin)

                except TimeoutException as e:
                    log.error(f"SendTEXT: Timeout waiting for element (e.g. '{nav_link_selector_key}' or '{message_textbox_selector_key}') for number {num}. WhatsApp Web UI may have changed, or the selector in 'selectors.json' may need an update. Details: {e}")
                    logtxt = f"Number::{num} => Timeout. Check UI/selectors."
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except (NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e_selenium:
                    log.error(f"SendTEXT: Selenium error ({type(e_selenium).__name__}) with element (e.g. '{nav_link_selector_key}' or '{message_textbox_selector_key}') for number {num}. WhatsApp Web UI may have changed, or a selector in 'selectors.json' may need an update. Details: {e_selenium}")
                    logtxt = f"Number::{num} => Error with element. Check UI/selectors."
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except WebDriverException as e:
                    log.error(f"SendTEXT: WebDriver error for number {num}: {e}")
                    logtxt = f"Number::{num} => WebDriver Error (No Send)!"
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except Exception as e:
                    log.exception(f"SendTEXT: Unexpected error for number {num}: {e}")
                    logtxt = f"Number::{num} => Unexpected Error (No Send)!"
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                finally:
                    i += 1
                    self.lcdNumber_reviewed.emit(i)
                    if logtxt:
                        self.LogBox.emit(logtxt)

            send_text_completed_successfully = True

        except WebDriverException as e:
            log.critical(f"SendTEXT: Fatal WebDriverException: {e}")
            self.EndWork.emit("-- Send Message failed: Browser session error --")
        except Exception as e:
            log.exception(f"SendTEXT: Unexpected critical error: {e}")
            self.EndWork.emit("-- Send Message failed: Unexpected error --")
        finally:
            if send_text_completed_successfully:
                log.info("SendTEXT: Message sending process completed.")
                self.EndWork.emit("-- Send Message completed --")

            self.isRunning = False
            self.stop()
            log.debug("SendTEXT method finished.")

    def SendIMG(self):
        log.debug("SendIMG method started.")
        send_img_completed_successfully = False
        try:
            if self.remember:
                log.debug("SendIMG: remember is True. Checking cache.")
                cacheList = os.listdir('temp/cache/')
                if len(cacheList) != 0:
                    # TODO: Consider adding try-except for access_by_file
                    self.access_by_file(f"./temp/cache/{cacheList[0]}")
                    log.debug('SendIMG: Session recovered from cache.')
                else:
                    log.debug("SendIMG: Cache empty. Initializing new browser session.")
                    self.driverBk()
                    if not self.__driver:
                        log.critical("SendIMG: WebDriver not initialized by driverBk.")
                        self.EndWork.emit("-- Send Image failed: Browser could not start --")
                        return
                    self.__driver.get(self.__URL)
            else:
                log.debug("SendIMG: remember is False. Initializing new browser session.")
                self.driverBk()
                if not self.__driver:
                    log.critical("SendIMG: WebDriver not initialized by driverBk.")
                    self.EndWork.emit("-- Send Image failed: Browser could not start --")
                    return
                self.__driver.get(self.__URL)

            log.debug(f"SendIMG: Waiting for login. Step: {self.step}")
            try:
                login_selector = self.selectors.get("login_check_element", "*[data-icon=new-chat-outline]")
                WebDriverWait(self.__driver, 60).until(
                    lambda driver: driver.execute_script(
                        f"return document.querySelector('{login_selector}') !== null;"
                    )
                )
                log.info("SendIMG: Login successful.")
                self.LogBox.emit("Login Success")
            except TimeoutException:
                log.error(f"SendIMG: Login timeout: Could not detect WhatsApp Web main interface for step {self.step}.")
                self.EndWork.emit(f"-- Send Image failed: Login timeout --") # step variable might not be 'SendIMG'
                # self.stop() is called in finally
                return

            i = 0
            f = 0
            nf = 0
            log.debug(f"SendIMG: Processing numbers: {self.Numbers}")
            for num_idx, num in enumerate(self.Numbers):
                logtxt = ""
                nav_link_selector_key = "navigation_link"
                message_textbox_selector_key = "message_textbox" # For page check
                attach_button_selector_key = "attach_button"
                media_file_input_selector_key = "media_file_input"
                media_caption_textbox_selector_key = "media_caption_textbox"
                try:
                    target_url = f"https.wa.me/{num}"
                    nav_link_xpath = self.selectors.get(nav_link_selector_key, "/html/head/a[@id='whatsappLink']")

                    if not nav_link_xpath:
                        log.error(f"{self.step}: Selector key '{nav_link_selector_key}' not found. Number: {num}.")
                        logtxt = f"Number::{num} => Config error for '{nav_link_selector_key}'."
                        i += 1; self.lcdNumber_reviewed.emit(i);
                        if logtxt: self.LogBox.emit(logtxt)
                        nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                        continue

                    if num_idx == 0:
                        execu_create = f"""
                                var whatsappLink = document.createElement('a');
                                whatsappLink.id = 'whatsappLink';
                                whatsappLink.href = "{target_url}";
                                document.head.appendChild(whatsappLink);
                                """
                        self.__driver.execute_script(execu_create)

                    user_element = WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                        EC.presence_of_element_located((By.XPATH, nav_link_xpath))
                    )
                    self.__driver.execute_script(f"arguments[0].setAttribute('href','{target_url}');", user_element)
                    self.__driver.execute_script("arguments[0].click();", user_element)

                    message_textbox_xpath_for_check = self.selectors.get(message_textbox_selector_key, '//div[@title="Type a message"]')
                    if not message_textbox_xpath_for_check:
                        log.error(f"{self.step}: Selector key '{message_textbox_selector_key}' not found for page check. Number: {num}.")
                        logtxt = f"Number::{num} => Config error for '{message_textbox_selector_key}'."
                        i += 1; self.lcdNumber_reviewed.emit(i);
                        if logtxt: self.LogBox.emit(logtxt)
                        nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                        continue

                    WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                        lambda d: "Phone number shared via url is invalid" in d.page_source or \
                                  d.find_elements(By.XPATH, message_textbox_xpath_for_check)
                    )
                    time.sleep(1.5)
                    sourceWeb = self.__driver.page_source

                    if "Phone number shared via url is invalid" in sourceWeb:
                        log.info(f"SendIMG: Number {num} is invalid. Not sending image.")
                        nf += 1
                        self.lcdNumber_nwa.emit(nf)
                        logtxt = f"Number::{num} => Invalid (No Send)"
                        self.nwa.emit(f"{num}")
                    else:
                        log.info(f"SendIMG: Number {num} is valid. Attempting to send image.")

                        attach_button_xpath = self.selectors.get(attach_button_selector_key, "//button[@aria-label='Attach' or @aria-label='Attach file']//span[@data-icon='attach-menu-plus']")
                        if not attach_button_xpath:
                            log.error(f"{self.step}: Selector key '{attach_button_selector_key}' not found. Number: {num}.")
                            logtxt = f"Number::{num} => Config error for '{attach_button_selector_key}'."
                            i += 1; self.lcdNumber_reviewed.emit(i);
                            if logtxt: self.LogBox.emit(logtxt)
                            nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                            continue
                        attach_button = WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                            EC.element_to_be_clickable((By.XPATH, attach_button_xpath))
                        )
                        attach_button.click()

                        file_input_xpath = self.selectors.get(media_file_input_selector_key, "//input[@type='file'][@accept='image/*,video/mp4,video/3gpp,video/quicktime']")
                        if not file_input_xpath:
                            log.error(f"{self.step}: Selector key '{media_file_input_selector_key}' not found. Number: {num}.")
                            logtxt = f"Number::{num} => Config error for '{media_file_input_selector_key}'."
                            i += 1; self.lcdNumber_reviewed.emit(i);
                            if logtxt: self.LogBox.emit(logtxt)
                            nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                            continue
                        file_input = WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                            EC.presence_of_element_located((By.XPATH, file_input_xpath))
                        )
                        file_input.send_keys(self.path)

                        caption_textbox_xpath = self.selectors.get(media_caption_textbox_selector_key, "//div[@data-testid='media-preview-caption-input']//div[@role='textbox']")
                        if not caption_textbox_xpath:
                            log.error(f"{self.step}: Selector key '{media_caption_textbox_selector_key}' not found. Number: {num}.")
                            logtxt = f"Number::{num} => Config error for '{media_caption_textbox_selector_key}'."
                            i += 1; self.lcdNumber_reviewed.emit(i);
                            if logtxt: self.LogBox.emit(logtxt)
                            nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                            continue
                        caption_textbox = WebDriverWait(self.__driver, self.WAIT_TIMEOUT).until(
                            EC.element_to_be_clickable((By.XPATH, caption_textbox_xpath))
                        )

                        if self.text.strip():
                            caption_textbox.send_keys(Keys.CONTROL, 'v')
                            time.sleep(0.5)

                        caption_textbox.send_keys(Keys.RETURN)
                        time.sleep(2)

                        f += 1
                        self.lcdNumber_wa.emit(f)
                        logtxt = f"Number::{num} => Image Sent."
                        self.wa.emit(f"{num}")

                    time.sleep(random.randint(self.sleepMin, self.sleepMax) if self.sleepMin < self.sleepMax else self.sleepMin)

                except TimeoutException as e:
                    log.error(f"SendIMG: Timeout waiting for element (e.g. '{nav_link_selector_key}', '{attach_button_selector_key}', etc.) for number {num}. WhatsApp Web UI may have changed, or a selector in 'selectors.json' may need an update. Details: {e}")
                    logtxt = f"Number::{num} => Timeout. Check UI/selectors."
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except (NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e_selenium:
                    # Selector key in log message will be the last one assigned if multiple were used.
                    current_selector_key = caption_textbox_selector_key # Or the last one attempted.
                    log.error(f"SendIMG: Selenium error ({type(e_selenium).__name__}) with element '{current_selector_key}' for number {num}. WhatsApp Web UI may have changed, or the selector in 'selectors.json' may need an update. Details: {e_selenium}")
                    logtxt = f"Number::{num} => Error with element '{current_selector_key}'. Check UI/selectors."
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except WebDriverException as e:
                    log.error(f"SendIMG: WebDriver error for image to {num}: {e}")
                    logtxt = f"Number::{num} => WebDriver Error (No Send)!"
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                except Exception as e:
                    log.exception(f"SendIMG: Unexpected error for image to {num}: {e}")
                    logtxt = f"Number::{num} => Unexpected Error (No Send)!"
                    nf += 1; self.lcdNumber_nwa.emit(nf); self.nwa.emit(f"{num}")
                finally:
                    i += 1
                    self.lcdNumber_reviewed.emit(i)
                    if logtxt:
                        self.LogBox.emit(logtxt)

            send_img_completed_successfully = True

        except WebDriverException as e:
            log.critical(f"SendIMG: Fatal WebDriverException: {e}")
            self.EndWork.emit("-- Send Image failed: Browser session error --")
        except Exception as e:
            log.exception(f"SendIMG: Unexpected critical error: {e}")
            self.EndWork.emit("-- Send Image failed: Unexpected error --")
        finally:
            if send_img_completed_successfully:
                log.info("SendIMG: Image sending process completed.")
                self.EndWork.emit("-- Send Image completed --")

            self.isRunning = False
            self.stop()
            log.debug("SendIMG method finished.")

    def addAcc(self):
        log.debug("addAcc method started.")
        account_added_successfully = False
        try:
            if self.remember:
                if not self.path: # Check if path is empty or None
                    cacheName = str(random.randint(1, 9999999))
                    self.path = cacheName

                active_session = self.get_active_session() # This might involve browser interaction
                if active_session: # Ensure session was retrieved
                    self.save_profile(active_session, f"./temp/cache/{self.path}")
                    log.info(f"addAcc: Profile saved to ./temp/cache/{self.path}")
                    account_added_successfully = True
                else:
                    log.error("addAcc: Could not get active session to save.")
            else:
                log.info("addAcc: 'Remember me' is not checked. No account profile saved.")
                # It's debatable if this is a success or not, but the operation as defined (not saving) completed.
                # For clarity, let's assume "completed" means no errors, even if nothing was saved.
                account_added_successfully = True

            log.debug(f"addAcc: Counter start value: {self.counter_start}")

        except (IOError, OSError) as e:
            log.error(f"addAcc: File saving/IO error: {e}")
            self.EndWork.emit("-- Add Account failed: File error --")
        except WebDriverException as e: # If get_active_session caused a browser issue
            log.critical(f"addAcc: WebDriverException during account addition: {e}")
            self.EndWork.emit("-- Add Account failed: Browser error --")
        except Exception as e:
            log.exception(f"addAcc: Unexpected error: {e}")
            self.EndWork.emit("-- Add Account failed: Unexpected error --")
        finally:
            if account_added_successfully and self.remember: # Only emit success if we intended to save and did
                 self.EndWork.emit("-- Add Account completed --")
            elif account_added_successfully and not self.remember:
                 self.EndWork.emit("-- Add Account skipped (Remember Me unchecked) --")
            # else an error message would have been emitted by except blocks.

            self.isRunning = False
            # self.stop() # Call stop if a browser instance might be lingering from get_active_session
            # get_active_session internally calls self.__driver.quit(), so stop() here might be redundant
            # or try to quit an already quit driver. Let's be cautious.
            # If get_active_session guarantees cleanup, explicit stop here is not needed.
            # For now, assume get_active_session cleans up its own driver instance if it creates one.
            log.debug("addAcc method finished.")

    def run(self):
        while self.isRunning == True:
            if self.step == 'A':
                self.ANALYZ()
            elif self.step == 'M':
                self.SendTEXT()
            elif self.step == 'I':
                self.SendIMG()
            elif self.step == 'Add':
                self.addAcc()

    def stop(self):
        self.isRunning = False # Ensure isRunning is set to False
        log.debug('stop: Attempting to stop thread and quit WebDriver...')
        try:
            if self.__driver:
                self.__driver.quit()
                log.info("stop: WebDriver quit successfully.")
        except WebDriverException as e:
            log.warning(f"stop: WebDriverException during driver.quit(): {e}")
        except Exception as e:
            log.exception(f"stop: Unexpected error during driver.quit(): {e}")
        # self.terminate() # Generally avoid terminate, prefer graceful shutdown.

    def __init_browser(self):
        try:
            if self.__browser_choice == CHROME:
                self.__browser_options = webdriver.ChromeOptions()
                if self.__platform == 'windows':
                    self.__browser_user_dir = os.path.join(os.environ['USERPROFILE'],
                                                           'Appdata', 'Local', 'Google', 'Chrome', 'User Data')
                elif self.__platform == 'linux':
                    self.__browser_user_dir = os.path.join(os.environ['HOME'], '.config', 'google-chrome')
                else: # Should have been caught by init, but defensive
                    log.error("__init_browser: Unsupported platform for Chrome profile path.")
                    self.__browser_user_dir = None
            elif self.__browser_choice == FIREFOX:
                self.__browser_options = webdriver.FirefoxOptions()
                if self.__platform == 'windows':
                    self.__browser_user_dir = os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', 'Profiles')
                elif self.__platform == 'linux':
                    self.__browser_user_dir = os.path.join(os.environ['HOME'], '.mozilla', 'firefox')
                else: # Should have been caught by init, but defensive
                    log.error("__init_browser: Unsupported platform for Firefox profile path.")
                    self.__browser_user_dir = None
            else:
                log.error(f"__init_browser: Invalid browser choice: {self.__browser_choice}")
                return

            if self.__browser_user_dir and not os.path.isdir(self.__browser_user_dir):
                log.warning(f"__init_browser: Browser user directory not found: {self.__browser_user_dir}. Profile features may fail.")
                # Consider creating it or handling this more strictly if profiles are essential from the start
                # For now, it will likely lead to an empty __browser_profile_list.

            # self.__browser_options.headless = True # This seems to be set by default or handled elsewhere. Revisit if needed.
            self.__refresh_profile_list()

        except KeyError as e: # For os.environ access
            log.error(f"__init_browser: Environment variable not found: {e}. Profile features may be unavailable.")
            self.__browser_user_dir = None # Cannot proceed with profile listing
            self.__browser_profile_list = []
        except Exception as e:
            log.exception(f"__init_browser: Unexpected error initializing browser profile settings: {e}")
            self.__browser_user_dir = None
            self.__browser_profile_list = []


    def __refresh_profile_list(self):
        self.__browser_profile_list = [] # Initialize to empty list
        if self.__browser_choice == CHROME:
            self.__browser_profile_list.append('') # Default profile option
            if self.__browser_user_dir and os.path.isdir(self.__browser_user_dir):
                try:
                    for profile_dir in os.listdir(self.__browser_user_dir):
                        if 'profile' in profile_dir.lower() and profile_dir != 'System Profile':
                            self.__browser_profile_list.append(profile_dir)
                except OSError as e:
                    log.error(f"__refresh_profile_list: Error reading Chrome profile directory {self.__browser_user_dir}: {e}")
            elif not self.__browser_user_dir:
                 log.warning("__refresh_profile_list: Chrome user directory not set. Cannot list profiles.")
        elif self.__browser_choice == FIREFOX:
            # TODO: consider reading out the profiles.ini for Firefox
            if self.__browser_user_dir and os.path.isdir(self.__browser_user_dir):
                try:
                    for profile_dir in os.listdir(self.__browser_user_dir):
                        if not profile_dir.endswith('.default') and \
                           os.path.isdir(os.path.join(self.__browser_user_dir, profile_dir)):
                            self.__browser_profile_list.append(profile_dir)
                except OSError as e:
                    log.error(f"__refresh_profile_list: Error reading Firefox profile directory {self.__browser_user_dir}: {e}")
            elif not self.__browser_user_dir:
                log.warning("__refresh_profile_list: Firefox user directory not set. Cannot list profiles.")

    def __get_indexed_db(self):
        self.__driver.execute_script('window.waScript = {};'
                                     'window.waScript.waSession = undefined;'
                                     'function getAllObjects() {'
                                     'window.waScript.dbName = "wawc";'
                                     'window.waScript.osName = "user";'
                                     'window.waScript.db = undefined;'
                                     'window.waScript.transaction = undefined;'
                                     'window.waScript.objectStore = undefined;'
                                     'window.waScript.getAllRequest = undefined;'
                                     'window.waScript.request = indexedDB.open(window.waScript.dbName);'
                                     'window.waScript.request.onsuccess = function(event) {'
                                     'window.waScript.db = event.target.result;'
                                     'window.waScript.transaction = window.waScript.db.transaction('
                                     'window.waScript.osName);'
                                     'window.waScript.objectStore = window.waScript.transaction.objectStore('
                                     'window.waScript.osName);'
                                     'window.waScript.getAllRequest = window.waScript.objectStore.getAll();'
                                     'window.waScript.getAllRequest.onsuccess = function(getAllEvent) {'
                                     'window.waScript.waSession = getAllEvent.target.result;'
                                     '};'
                                     '};'
                                     '}'
                                     'getAllObjects();')
        while not self.__driver.execute_script('return window.waScript.waSession != undefined;'):
            time.sleep(1)
        wa_session_list = self.__driver.execute_script(
            'return window.waScript.waSession;')
        return wa_session_list

    def __get_profile_storage(self, profile_name=None):
        self.__refresh_profile_list()

        if profile_name is not None and profile_name not in self.__browser_profile_list:
            raise ValueError(
                'The specified profile_name was not found. Make sure the name is correct.')

        if profile_name is None:
            self.__start_visible_session()
        else:
            self.__start_invisible_session(profile_name)

        indexed_db = self.__get_indexed_db()

        self.__driver.quit()

        return indexed_db

    def __start_session(self, options, profile_name=None, wait_for_login=True):
        if profile_name is None:
            if self.__browser_choice == CHROME:
                self.__driver = webdriver.Chrome(options=options, service_args=["hide_console", ], service=self.service)
                self.__driver.set_window_position(0, 0)
                self.__driver.set_window_size(670, 800)
            elif self.__browser_choice == FIREFOX:
                self.__driver = webdriver.Firefox(options=options)

            self.__driver.get(self.__URL)

            if wait_for_login:
                verified_wa_profile_list = False
                while not verified_wa_profile_list:
                    time.sleep(1)
                    verified_wa_profile_list = False
                    for object_store_obj in self.__get_indexed_db():
                        if 'WASecretBundle' in object_store_obj['key']:
                            verified_wa_profile_list = True
                            break
        else:
            if self.__browser_choice == CHROME:
                options.add_argument(
                    'user-data-dir=%s' % os.path.join(self.__browser_user_dir, profile_name))
                self.__driver = webdriver.Chrome(options=options, service_args=["hide_console", ], service=self.service)
            elif self.__browser_choice == FIREFOX:
                fire_profile = webdriver.FirefoxProfile(
                    os.path.join(self.__browser_user_dir, profile_name))
                self.__driver = webdriver.Firefox(
                    fire_profile, options=options)

            self.__driver.get(self.__URL)

    def __start_visible_session(self, profile_name=None, wait_for_login=True):
        options = self.__browser_options
        options.headless = False
        self.__refresh_profile_list()

        if profile_name is not None and profile_name not in self.__browser_profile_list:
            raise ValueError(
                'The specified profile_name was not found. Make sure the name is correct.')

        self.__start_session(options, profile_name, wait_for_login)

    def __start_invisible_session(self, profile_name=None):
        self.__refresh_profile_list()
        if profile_name is not None and profile_name not in self.__browser_profile_list:
            raise ValueError(
                'The specified profile_name was not found. Make sure the name is correct.')

        self.__start_session(self.__browser_options, profile_name)

    def set_browser(self, browser):
        if type(browser) == str:
            if browser.lower() == 'chrome':
                self.__browser_choice = CHROME
            elif browser.lower() == 'firefox':
                self.__browser_choice = FIREFOX
            else:
                raise ValueError(
                    'The specified browser is invalid. Try to use "chrome" or "firefox" instead.')
        else:
            if browser == CHROME:
                pass
            elif browser == FIREFOX:
                pass
            else:
                raise ValueError(
                    'Browser type invalid. Try to use WaWebSession.CHROME or WaWebSession.FIREFOX instead.')

            self.__browser_choice = browser

    def get_active_session(self, use_profile=None):
        profile_storage_dict = {}
        use_profile_list = []
        self.__refresh_profile_list()

        if use_profile and use_profile not in self.__browser_profile_list:
            raise ValueError('Profile does not exist: %s', use_profile)
        elif use_profile is None:
            return self.__get_profile_storage()
        elif use_profile and use_profile in self.__browser_profile_list:
            use_profile_list.append(use_profile)
        elif type(use_profile) == list:
            use_profile_list.extend(self.__browser_profile_list)
        else:
            raise ValueError(
                "Invalid profile provided. Make sure you provided a list of profiles or a profile name.")

        for profile in use_profile_list:
            profile_storage_dict[profile] = self.__get_profile_storage(profile)

        return profile_storage_dict

    def create_new_session(self):
        return self.__get_profile_storage()

    def access_by_obj(self, wa_profile_list):
        verified_wa_profile_list = False
        for object_store_obj in wa_profile_list:
            if 'WASecretBundle' in object_store_obj['key']:
                verified_wa_profile_list = True
                break

        if not verified_wa_profile_list:
            raise ValueError(
                'This is not a valid profile list. Make sure you only pass one session to this method.')

        self.__start_visible_session(wait_for_login=False)
        self.__driver.execute_script('window.waScript = {};'
                                     'window.waScript.insertDone = 0;'
                                     'window.waScript.jsonObj = undefined;'
                                     'window.waScript.setAllObjects = function (_jsonObj) {'
                                     'window.waScript.jsonObj = _jsonObj;'
                                     'window.waScript.dbName = "wawc";'
                                     'window.waScript.osName = "user";'
                                     'window.waScript.db;'
                                     'window.waScript.transaction;'
                                     'window.waScript.objectStore;'
                                     'window.waScript.clearRequest;'
                                     'window.waScript.addRequest;'
                                     'window.waScript.request = indexedDB.open(window.waScript.dbName);'
                                     'window.waScript.request.onsuccess = function(event) {'
                                     'window.waScript.db = event.target.result;'
                                     'window.waScript.transaction = window.waScript.db.transaction('
                                     'window.waScript.osName, "readwrite");'
                                     'window.waScript.objectStore = window.waScript.transaction.objectStore('
                                     'window.waScript.osName);'
                                     'window.waScript.clearRequest = window.waScript.objectStore.clear();'
                                     'window.waScript.clearRequest.onsuccess = function(clearEvent) {'
                                     'for (var i=0; i<window.waScript.jsonObj.length; i++) {'
                                     'window.waScript.addRequest = window.waScript.objectStore.add('
                                     'window.waScript.jsonObj[i]);'
                                     'window.waScript.addRequest.onsuccess = function(addEvent) {'
                                     'window.waScript.insertDone++;'
                                     '};'
                                     '}'
                                     '};'
                                     '};'
                                     '}')
        self.__driver.execute_script(
            'window.waScript.setAllObjects(arguments[0]);', wa_profile_list)

        while not self.__driver.execute_script(
                'return (window.waScript.insertDone == window.waScript.jsonObj.length);'):
            time.sleep(1)

        self.__driver.refresh()

        # while True:
        #     try:
        #         _ = self.__driver.window_handles
        #         time.sleep(1)
        #     except WebDriverException:
        #         break

    def access_by_file(self, profile_file):
        profile_file = os.path.normpath(profile_file)
        try:
            with open(profile_file, 'r') as file:
                wa_profile_list = json.load(file)

            verified_wa_profile_list = False
            # Check if wa_profile_list is actually a list and not None, before iterating
            if isinstance(wa_profile_list, list):
                for object_store_obj in wa_profile_list:
                    if isinstance(object_store_obj, dict) and 'key' in object_store_obj and \
                       'WASecretBundle' in object_store_obj['key']:
                        verified_wa_profile_list = True
                        break

            if verified_wa_profile_list:
                self.access_by_obj(wa_profile_list) # This method might also need error handling
            else:
                # Log instead of raising ValueError directly, or make it more specific
                log.error(f"access_by_file: Profile data in {profile_file} is not in expected format or WASecretBundle missing.")
                # Optionally re-raise a more specific error if needed for upstream handling
                raise ValueError('Invalid profile data format or missing WASecretBundle.')

        except FileNotFoundError:
            log.error(f"access_by_file: Profile file not found: {profile_file}")
            raise # Re-raise FileNotFoundError to be handled by caller if necessary
        except json.JSONDecodeError as e:
            log.error(f"access_by_file: Error decoding JSON from profile file {profile_file}: {e}")
            raise # Re-raise to be handled by caller
        except Exception as e:
            log.exception(f"access_by_file: Unexpected error processing profile file {profile_file}: {e}")
            raise # Re-raise for upstream handling


    def save_profile(self, wa_profile_list, file_path):
        file_path = os.path.normpath(file_path)

        try:
            # Determine if it's a single profile list or a dict of profiles
            is_single_profile = False
            if isinstance(wa_profile_list, list):
                for object_store_obj in wa_profile_list:
                    if isinstance(object_store_obj, dict) and 'key' in object_store_obj and \
                       'WASecretBundle' in object_store_obj['key']:
                        is_single_profile = True
                        break
            elif isinstance(wa_profile_list, dict): # It's a dictionary of profiles
                # We'll iterate through this dict later
                pass
            else: # Not a list or dict, or not the expected structure
                log.error(f"save_profile: wa_profile_list is not a valid list or dictionary of profiles.")
                raise ValueError('Invalid profile data provided to save_profile.')

            if is_single_profile:
                with open(file_path, 'w') as file:
                    json.dump(wa_profile_list, file, indent=4)
                log.info(f"save_profile: Successfully saved single profile to {file_path}")
            else: # It's a dictionary of profiles (or should be)
                saved_profiles_count = 0
                if isinstance(wa_profile_list, dict):
                    for profile_name, profile_storage in wa_profile_list.items():
                        # Verify this specific profile_storage before saving
                        current_profile_valid = False
                        if isinstance(profile_storage, list):
                            for obj_store_obj_item in profile_storage: # Renamed to avoid conflict
                                if isinstance(obj_store_obj_item, dict) and 'key' in obj_store_obj_item and \
                                   'WASecretBundle' in obj_store_obj_item['key']:
                                    current_profile_valid = True
                                    break

                        if current_profile_valid:
                            # Construct a unique filename for this profile part
                            base_dir = os.path.dirname(file_path)
                            base_name = os.path.basename(file_path)
                            # Remove potential existing extensions to avoid things like file.json-profileName
                            base_name_no_ext, _ = os.path.splitext(base_name)

                            # Ensure profile_name is a string and valid for filenames
                            safe_profile_name = str(profile_name).replace(os.sep, "_").replace(" ", "_")
                            single_profile_filename = f"{base_name_no_ext}-{safe_profile_name}.json" # Add .json extension

                            full_single_profile_path = os.path.join(base_dir, single_profile_filename)

                            # Recursive call to save this individual profile
                            self.save_profile(profile_storage, full_single_profile_path)
                            saved_profiles_count += 1
                        else:
                            log.warning(f"save_profile: Profile data for '{profile_name}' in dict is invalid. Skipping.")

                if saved_profiles_count > 0:
                    log.info(f"save_profile: Successfully saved {saved_profiles_count} profiles from dictionary.")
                else:
                    log.warning(f"save_profile: No valid profiles found to save from the dictionary provided to path {file_path}.")
                    # This might not be an error if the input dict was empty or all profiles were invalid
                    # raise ValueError('Could not find any valid profiles in the dictionary to save.')

        except (IOError, OSError) as e:
            log.error(f"save_profile: Error writing profile to {file_path}: {e}")
            raise # Re-raise to allow caller to handle
        except ValueError as e: # Catch specific ValueErrors from this function or recursive calls
            log.error(f"save_profile: ValueError: {e} (while processing {file_path})")
            raise
        except Exception as e:
            log.exception(f"save_profile: Unexpected error while saving profile to {file_path}: {e}")
            raise

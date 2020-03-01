# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import requests
import urllib.parse
#import translate
#import googletrans
import uno
import os
import sys
#from google.cloud import translate
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from os import path
from time import sleep
from multiprocessing import Process
import time
import logging
import contextlib


# -*- coding: utf-8 -*-


CTX = uno.getComponentContext()
SM = CTX.getServiceManager()
#target_language = "en"
#project_id = "my-project-1510327785880"
default_pinyin_engine = "google"
retries = 3
sentinel_file = '/tmp/pinyin.sentinel'
logging.basicConfig(filename='pinyin.log',filemode='w',level=logging.DEBUG, 
    format='%(asctime)s %(levelname)-8s %(message)s', 
    datefmt='%Y-%m-%d %H:%M:%S')
logging.info("start logging")
logging.info("test")
logger = logging.getLogger("pinyin")



def create_driver_instance():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('window-size=1024x768')
    options.add_argument("--proxy-server='direct://'")
    options.add_argument("--proxy-bypass-list=*")
    driver = webdriver.Chrome('chromedriver', chrome_options=options)
    cdi_executor_url = driver.command_executor._url
    cdi_session_id = driver.session_id

    print (cdi_session_id)
    print (cdi_executor_url)
    logging.info("create_driver_instance: sessionId: {}, executorUrl: {}".format(cdi_session_id,cdi_executor_url))
    return cdi_session_id, cdi_executor_url

def browser_session_exists (bse_session_id, bse_executor_url):
    from selenium.common.exceptions import WebDriverException
    logging.info("testing if browser exists with sessionId: {} and exec url: {} ".format(bse_session_id,bse_executor_url))
    try:
        driver = create_driver_session(bse_session_id, bse_executor_url)
        logger.info("browser_session_exists: Trying to get the driver title. ")
        try:
            driver.title
            logger.info("browser_session_exists with sessionid {} and executor_url {}. OK to reuse.".format(bse_session_id,bse_executor_url))
            return True
        except:
            logger.info("browser_session_exists: session exists but browser seems dead. Killing session, cleaning up and returning false.")
            try:
               logger.info("browser_session_exists: executing driver.quit here.")
               driver.quit()
               logger.info("browser_session_exists: killed session through driver.quit.")
            except:
                logger.info("browser_session_exists: failed to kill driver session. Still removing sentinel file. Checking to kill pid later.")
            with contextlib.suppress(FileNotFoundError):
                os.remove(sentinel_file)
            logger.info("browser_session_exists: driver quitted, sentinel file removed. returning false.")    
            return False

    except WebDriverException:
        logger.info("browser_session_exists: session DOES NOT ExIST with sessionid {} and executor_url {}".format(bse_session_id,bse_executor_url))
        return False  

def get_browser_session():
    gbs_session_id = ''
    gbs_executor_url = ''
    if path.exists(sentinel_file):
        with open(sentinel_file, 'r') as f:
            config = json.load(f)
        gbs_session_id = config['session_id']
        gbs_executor_url = config['executor_url']
        logging.info("get_browser_session: sessionid: {}, executorurl: {}".format(gbs_session_id,gbs_executor_url))
        if browser_session_exists(gbs_session_id,gbs_executor_url):
            logger.info("get_browser_session: browser_session_exists returned true. ")
        else:
            logging.info("get_browser_session: Session not found, spawning a new session"  )
            gbs_session_id, gbs_executor_url = create_driver_instance()
            logging.info("get_browser_session: New session spawned with sessionid: {}, executorurl: {}".format(gbs_session_id,gbs_executor_url))
            config = {'session_id': gbs_session_id, 'executor_url': gbs_executor_url}
            with open(sentinel_file, 'w') as f:
                json.dump(config, f)
        return gbs_session_id, gbs_executor_url
            
    else:
        session_id, executor_url = create_driver_instance()
        config = {'session_id': session_id, 'executor_url': executor_url}
        with open(sentinel_file, 'w') as f:
            json.dump(config, f)

        return session_id, executor_url
    





def create_driver_session(session_id, executor_url):
    from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver
    org_command_execute = RemoteWebDriver.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            return {'success': 0, 'value': None, 'sessionId': session_id}
        else:
            return org_command_execute(self, command, params)

    # Patch the function before creating the driver object
    RemoteWebDriver.execute = new_command_execute
    logging.info("create_driver_session: setting up new_driver")
    new_driver = webdriver.Remote(command_executor=executor_url, desired_capabilities={})
    logger.info("create_driver_session: setting session id to found exisiting session id {}".format(session_id) )
    new_driver.session_id = session_id
    logging.info("create_driver_session: finished setting new_driver sessionid: {}, executorurl: {}".format(new_driver.session_id,executor_url))

    # Replace the patched function with original function
    RemoteWebDriver.execute = org_command_execute
    
    return new_driver

def google_sel_translate_reuse_browser (tobetranslated, sourcelang , destlang ):
    from selenium.common.exceptions import NoSuchElementException
    logging.info("google_sel_translate: translating from {} to {}".format(sourcelang,destlang))
    translated = "<error translating>"
    get_source_pinyin = True if sourcelang == 'zh-CN' else False
    get_target_pinyin = True if destlang == 'zh-CN' else False
    driver_session_id, driver_executor_id = get_browser_session()
    driver = create_driver_session(driver_session_id, driver_executor_id)
    logger.info("google_sel_translate_reuse_browser: created driver session with id {} and url: {}".format(driver_session_id,driver_executor_id))
    logger.info("google_sel_translate_reuse_browser: translating: {}\nsource language {}\nDestination: {}\n...please wait for a few seconds.. ".format(tobetranslated,sourcelang,destlang))
    retries_left = retries
    failed = 0
    pinyin = "no pinyin"
    translated = "no translation"
    while retries_left > 0:
        logger.info("google_sel_translate_reuse_browser: retries left {}".format(retries_left))
        try:  
            driver.get("https://translate.google.com/#" + sourcelang +"/" +destlang +"/")
            driver.find_element_by_id('source').send_keys(tobetranslated)
            retries_left = 0
        except NoSuchElementException as e:
            logger.info("google_sel_translate_reuse_browser: Connection to google translate failed. Sleeping a second. {} retries left ".format(retries_left))
            retries_left -= 1
            sleep(1)
            failed = 1
            logger.info("google_sel_translate_reuse_browser: exception {}".format(e))

    if failed == 1:
        logger.info("google_sel_translate_reuse_browser: Unable to connect to google.  Please check your network connection.")
        driver.quit()
        exit()

    wait = WebDriverWait(driver.find_element_by_css_selector(".transliteration-container"),5000)
    print("got the items")

    if get_source_pinyin:
        show_more_link = "div.tlid-show-more-link.truncate-link"
        show_more_transliteration_link = 'div.tlid-transliteration-content.transliteration-content'
        transliteration_link = 'div.tlid-transliteration-content.transliteration-content.full'
    elif get_target_pinyin:
        show_more_link = "div.tlid-result-transliteration-container.result-transliteration-container.transliteration-container > div.tlid-show-more-link.truncate-link"
        show_more_transliteration_link = 'div.tlid-result-transliteration-container.result-transliteration-container.transliteration-container > div.tlid-transliteration-content.transliteration-content'
        transliteration_link = 'div.tlid-result-transliteration-container.result-transliteration-container.transliteration-container > div.tlid-transliteration-content.transliteration-content.full'

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.tlid-transliteration-content.transliteration-content")))
    sleep(2)
    wait = WebDriverWait(driver.find_element_by_css_selector("div.text-wrap.tlid-copy-target"),5000)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.tlid-translation.translation")))
    try:
        driver.find_element_by_css_selector(show_more_link).click()
        pinyin = driver.find_element_by_css_selector(show_more_transliteration_link).text 
    except:
        print ("no show more field")
        try:
            pinyin = driver.find_element_by_css_selector(transliteration_link).text
        except:
            pinyin = "no pinyin found"
            logging.info("google_sel_translate_reuse_browser: finally pinyin = {}".format(pinyin))

    #get translation
    try:
         translated = driver.find_element_by_css_selector('span.tlid-translation.translation').text
    except :
         print("no translation")
    #driver.quit()
    return pinyin, translated




def google_translate(text):
    target_language = "en"
    project_id = "my-project-1510327785880"

    client = translate.TranslationServiceClient()

    contents = [text]
    parent = client.location_path(project_id, "global")

    response = client.translate_text(
        parent=parent,
        contents=contents,
        mime_type='text/plain',  # mime types: text/plain, text/html
        source_language_code='zh-cn',
        target_language_code=target_language)
    return response.translations[0].translated_text



def translate_controller(pinyin_engine = default_pinyin_engine, sourcelang = "zh-CN", destlang = "en"):
    xModel = XSCRIPTCONTEXT.getDocument()
 
    xSelectionSupplier = xModel.getCurrentController()
    xIndexAccess = xSelectionSupplier.getSelection()
    count = xIndexAccess.getCount()
    for i in range(count) :
        xTextRange = xIndexAccess.getByIndex(i)
        theString = xTextRange.getString()
        if len(theString)==0 :
            xText = xTextRange.getText()
            xWordCursor = xText.createTextCursorByRange(xTextRange)
            if not xWordCursor.isStartOfWord():
                xWordCursor.gotoStartOfWord(False)
            xWordCursor.gotoNextWord(True)
            theString = xWordCursor.getString()
            newString = translation_service(theString, pinyin_engine, sourcelang, destlang)
            if newString :
                xWordCursor.setString(newString)
                xSelectionSupplier.select(xWordCursor)
        else :
            newString = translation_service( theString, pinyin_engine, sourcelang, destlang )
            if newString:
                xTextRange.setString(newString)
                xSelectionSupplier.select(xTextRange)


def translation_service(a, pinyin_engine, sourcelang, destlang):
    import chinesechars
    import unidecode
    logging.info("translation_logic: translating from {} to {}.".format(sourcelang,destlang))
    if sourcelang == 'zh-CN':
        if pinyin_engine == "glosbe":
            urlencoded = urllib.parse.quote_plus(a)
            response = requests.get("https://glosbe.com/transliteration/api?from=Han&dest=Latin&text=" + urlencoded + "&format=json")
            todos= json.loads(response.text)
            pinyin = todos["text"]
            translated = google_translate(a)
        else:
            if not chinesechars.has_chinese(a):
                a =  unidecode.unidecode(a).lower()
                pinyin, translated = google_sel_translate_reuse_browser(a,sourcelang,destlang)
                a, _  = google_sel_translate_reuse_browser(pinyin,sourcelang, destlang)
            else:
                pinyin, translated = google_sel_translate_reuse_browser(a,sourcelang,destlang)
        
        stext = "{}: {} ({})".format(a,pinyin, translated)
        return stext
    else:
        pinyin, translated = google_sel_translate_reuse_browser(a,sourcelang,destlang)
        logger.info("translation_logic: english: pinyin: {}".format(pinyin))
        stext =  "{}: {} ({})".format(a,translated, pinyin)
        return stext

def translate_cn_to_en (self):
    logging.info("translate_google_selenium: start logging")    
    logging.info("translate_google_selenium: translating from chinese to english")
    translate_controller("google", 'zh-CN', 'en' )

def translate_glosbe (self):
    translate_controller ("glosbe")


def translate_to_cn(self):
    logging.info("start logging, translating from english to Chinese")    
    translate_controller("google", 'en', 'zh-CN' )

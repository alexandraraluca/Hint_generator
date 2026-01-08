#In this file I will extract multiple submissions from this page(https://codeforces.com/problemset/status) using selenium and for each one of them I will save the html file of that submission and extract the hint and the code from that submission and the official code.

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
import sys
import time
from selenium.webdriver.support.ui import WebDriverWait

# Force stdout encoding to UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def setup_driver():
    options = webdriver.ChromeOptions()
    debug_address = "127.0.0.1:9133"
    print(f"Attempting to connect to Chrome at {debug_address}")
    options.add_experimental_option("debuggerAddress", debug_address)
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options) #inceraca sa se conecteze
        print("Connected to existing Chrome. Title:", driver.title)
        return driver
    except WebDriverException as e:
        print("\nDetailed error information:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        sys.exit(1)

driver = setup_driver()


try:

    #First, I will access this page, where I can see the id of the problems and the links for the submission and the problem and the status of the submission
    # I can build the link for the following:
        # https://codeforces.com/problemset/submission/1811/356978384
        # https://codeforces.com/problemset/problem/1811/A
        # https://codeforces.com/profile/fatema.akte (userul in case I wnat all his subbmisions)
    driver.get("https://codeforces.com/problemset/status")
    
    # Wait for page load
    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    
    # Save the page source
    with open("problemset_page.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Page saved successfully!")

except Exception as e:
    print(f"An error occurred: {str(e)}")
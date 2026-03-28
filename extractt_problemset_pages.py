import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By


def setup_driver(debug_port=9123):
    """
    Conecteaza la un browser Chrome existent prin debugger.
    
    Args:
        debug_port: Portul pe care ruleaza Chrome in debug mode
    """
    options = webdriver.ChromeOptions()
    debug_address = f"127.0.0.1:{debug_port}"
    print(f"Attempting to connect to Chrome at {debug_address}")
    options.add_experimental_option("debuggerAddress", debug_address)
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        print("✓ Connected to existing Chrome. Title:", driver.title)
        return driver
    except WebDriverException as e:
        print("\nDetailed error information:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        return None


def save_page(driver, filename="problemset_page.html"):
    """
    Salveaza pagina curenta din browser intr-un fisier HTML.
    
    Args:
        driver: Selenium WebDriver
        filename: Numele fisierului unde sa se salveze pagina
    
    Returns:
        True daca a reusit, False altfel
    """
    try:
        # Asteptam incarcarea completa a paginii
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Delay mic pentru a se asigura ca totul e incarcat
        time.sleep(2)
        
        # Salvam HTML-ul paginii
        with open(filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        print(f"✓ Page saved successfully in {filename}!")
        print(f"  File size: {len(driver.page_source)} bytes")
        return True
        
    except Exception as e:
        print(f"✗ Error saving page: {str(e)}")
        return False


if __name__ == "__main__":
    try:
        # Configurare
        DEBUG_PORT_START = 9207  # Portul initial
        CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        USER_DATA_DIR = "C:\\chrome_debug_temp"
        OUTPUT_FILE = "problemset_pages\problemset_page_3.html"
        
        # Conectare initiala pentru a salva pagina principala
        print("=" * 60)
        print("SAVING CURRENT PAGE FROM CHROME")
        print("=" * 60)
        print("\nMake sure Chrome is running with:")
        print(f'& "{CHROME_PATH}" --remote-debugging-port={DEBUG_PORT_START} --user-data-dir="{USER_DATA_DIR}"\n')
        
        # Conectare la browser
        driver = setup_driver(DEBUG_PORT_START)
        if not driver:
            print("\n❌ Please start Chrome with the command above and try again.")
            sys.exit(1)
        
        # Verificam daca pagina este corecta
        print(f"\nCurrent URL: {driver.current_url}")
        print(f"Page Title: {driver.title}\n")
        
        # Salvam pagina
        if save_page(driver, OUTPUT_FILE):
            print("\n✓ SUCCESS! Page saved to:", os.path.abspath(OUTPUT_FILE))
        else:
            print("\n✗ FAILED to save page")
            sys.exit(1)
        
        # Inchidem conexiunea
        driver.quit()
        print("\n" + "=" * 60)
        print("DONE!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
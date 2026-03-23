"""
Script pentru extragerea enunturilor, tutorialelor, solutiilor si hints de pe Codeforces.
Foloseste delay-uri mari (2-7 minute) pentru a evita blocarea Cloudflare.
"""

import os
import json
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import sys

# Import functia de extragere probleme
from merged_problems_nume_si_enunt import extract_problems_from_html


def setup_driver(debug_port=9305):
    """Conecteaza la un browser Chrome existent prin debugger."""
    options = webdriver.ChromeOptions()
    debug_address = f"127.0.0.1:{debug_port}"
    print(f"Attempting to connect to Chrome at {debug_address}")
    options.add_experimental_option("debuggerAddress", debug_address)
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        print("✓ Connected to existing Chrome. Title:", driver.title)
        return driver
    except WebDriverException as e:
        print(f"\n❌ Error connecting: {str(e)}")
        return None


def random_delay(min_sec=120, max_sec=220, message="Waiting"):
    """Asteapta un timp aleatoriu intre min_sec si max_sec (default: 2-7 minute)."""
    delay = random.uniform(min_sec, max_sec)
    print(f"    ⏳ {message}: {delay:.0f}s ({delay/60:.1f} minutes)")
    time.sleep(delay)


def extract_problem_statement(soup):
    """Extrage enuntul problemei din HTML."""
    try:
        #salveaza pagina in fisierul enunt.html pentru debug
        with open("enunt.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())

        # Cautam div-ul cu clasa "problem-statement"
        problem_div = soup.find("div", class_="problem-statement")
        if problem_div:
            # Extragem textul, eliminand header-ul
            header = problem_div.find("div", class_="header")
            if header:
                header.extract()  # Remove header
            
            return problem_div.get_text(strip=True, separator='\n')
        return None
    except Exception as e:
        print(f"        ⚠️ Error extracting statement: {str(e)}")
        return None


def extract_tutorial_content(driver, problem_code):
    """
    Gaseste linkul catre Tutorial/Editorial din pagina problemei si navighează la el.
    Extrage Code, Solution, Hints pentru problema.
    
    Returns:
        dict cu campurile: code, solution, hints sau None daca nu exista tutorial
    """
    tutorial_data = {
        'code': None,
        'solution': None,
        'hints': None
    }
    
    try:
        # Parsam HTML-ul paginii problemei curente
        print(f"        🔍 Looking for Tutorial/Editorial link...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Cautam linkul Tutorial/Editorial
        tutorial_link = None
        
        # Cautam toate link-urile cu text care contine "Tutorial"
        for link in soup.find_all("a", href=True):
            link_text = link.get_text(strip=True)
            link_title = link.get('title', '')
            
            if 'Tutorial' in link_text or 'Editorial' in link_title or 'Editorial' in link_text:
                tutorial_link = link.get('href')
                print(f"        ✓ Found Tutorial link: {tutorial_link}")
                break
        
        if not tutorial_link:
            print(f"  No Tutorial/Editorial link found")
            return None
        
        # Construim URL-ul complet
        if not tutorial_link.startswith('http'):
            tutorial_url = f"https://codeforces.com{tutorial_link}"
        else:
            tutorial_url = tutorial_link
        
        print(f"        🌐 Navigating to: {tutorial_url}")
        
        # Navigam la pagina tutorial
        driver.get(tutorial_url)
        
        # Delay dupa navigare
        random_delay(60, 180, "After navigating to Tutorial")
        
        # Asteptam sa se incarce pagina
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # # Salvam pagina tutorial in fisierul tutorial.html
        # with open(f"tutorial.html", "w", encoding="utf-8") as f:
        #     f.write(driver.page_source)

        # salveaza pagina fiecarui tutorial astfel: tutorial_{problem_code}.html in folderul tutorial_pages_saved
        os.makedirs("tutorial_pages_saved", exist_ok=True)
        with open(f"tutorial_pages_saved/tutorial_{problem_code}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
    except TimeoutException:
        print(f"        ⚠️ Timeout loading tutorial page")
        return None
    except Exception as e:
        print(f"        ⚠️ Error extracting tutorial: {str(e)}")
        return None


def process_all_problems(driver, problems_dict, output_file="code_solution_hints.json", 
                        min_delay=60, max_delay=180):
    """
    Proceseaza toate problemele si salveaza rezultatele in JSON.
    
    Args:
        driver: Selenium WebDriver
        problems_dict: Dictionarul cu probleme din merged_problems_nume_si_enunt.py
        output_file: Fisierul JSON de output
        min_delay: Delay minim intre requesturi (secunde)
        max_delay: Delay maxim intre requesturi (secunde)
    """
    results = {}
    total = len(problems_dict)
    processed = 0
    errors = 0
    
    # Incarcam rezultatele existente daca fisierul exista
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print(f"✓ Loaded {len(results)} existing results from {output_file}")
    
    print(f"\n{'='*60}")
    print(f"Starting to process {total} problems")
    print(f"Delay: {min_delay}-{max_delay}s ({min_delay/60:.1f}-{max_delay/60:.1f} minutes)")
    print(f"{'='*60}\n")
    
    for i, (problem_code, problem_info) in enumerate(problems_dict.items()):
        print(f"[{i+1}/{total}] Processing {problem_code}: {problem_info['name']}")
        
        # Skip daca deja am procesat problema
        if problem_code in results:
            print(f"    ✓ Already processed, skipping...")
            continue
        
        try:
            # Construim URL-ul complet
            url = f"https://codeforces.com{problem_info['link']}"
            print(f"    🌐 URL: {url}")
            
            # Navigam la pagina problemei
            driver.get(url)
            
            # Asteptam incarcarea paginii
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Small delay pentru a simula citirea
            time.sleep(random.uniform(2, 4))
            
            # Extragem enuntul problemei
            soup = BeautifulSoup(driver.page_source, "html.parser")
            statement = extract_problem_statement(soup)
            
            if statement:
                print(f"    ✓ Extracted problem statement ({len(statement)} chars)")
            else:
                print(f"    ⚠️ Could not extract statement")
            
            # Delay inainte de a cauta Tutorial
            random_delay(min_delay, max_delay, "Before checking for Tutorial")
            
            # Incercam sa extragem tutorial-ul
            tutorial = extract_tutorial_content(driver, problem_code)
            
            # Salvam rezultatele
            results[problem_code] = {
                'name': problem_info['name'],
                'link': problem_info['link'],
                'statement': statement,
                'tutorial': tutorial
            }
            
            processed += 1
            
            # Salvam progresul dupa fiecare problema procesata
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"    ✅ Saved to {output_file} ({processed}/{total} completed)")
            
            # Delay mare inaintede urmatoarea problema
            if i < total - 1:  # Nu facem delay dupa ultima problema
                random_delay(min_delay, max_delay, "Before next problem")
            
        except Exception as e:
            print(f"    ❌ Error processing {problem_code}: {str(e)}")
            errors += 1
            
            # Delay si dupa eroare
            if i < total - 1:
                random_delay(min_delay, max_delay, "After error, before next problem")
            continue
    
    print(f"\n{'='*60}")
    print(f"FINISHED!")
    print(f"Total problems: {total}")
    print(f"Successfully processed: {processed}")
    print(f"Errors: {errors}")
    print(f"Output file: {output_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    try:
        # Configurare
        DEBUG_PORT = 9306
        CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        USER_DATA_DIR = "C:\\chrome_debug_temp"
        OUTPUT_FILE = "code_solution_hints.json"
        
        print("=" * 60)
        print("STEP 1: Extracting problems from problemset_page.html")
        print("=" * 60)
        
        # Extragem lista de probleme
        problems_dict = extract_problems_from_html("problemset_page.html")

        #Verifying all problems titles and their links (from here we will extract the solution, code and hints)
        # print(f"\nExtracted {len(problems_dict)} problems:")
        # for code, info in problems_dict.items():
        #     print(f"  {code}: {info['name']} ({info['link']})")
        
        driver = setup_driver(DEBUG_PORT)
        if not driver:
            print("\n❌ Please start Chrome with the command above and try again.")
            sys.exit(1)
        
        print("\n" + "=" * 60)
        print("STEP 3: Processing problems (extracting statements and tutorials)")
        print("=" * 60)
        print("\n  Using VERY LONG delays (2-7 minutes) to avoid Cloudflare!")
        print("This will take a LONG time. Progress is saved after each problem.\n")
        
        # Procesam problemele
        process_all_problems(
            driver,
            problems_dict,
            output_file=OUTPUT_FILE,
            min_delay=60,    # 1 minut
            max_delay=180    # 3 minute
        )
        
        # Cleanup
        try:
            driver.quit()
        except:
            pass
    
    except Exception as e:
        print(f"\n An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

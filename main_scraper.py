# Script pentru a scala procesarea: pentru fiecare fisier din problemset_pages,
# ETAPA 1: creeaza rezultate in rezultate_<nmb>/submission_pages_<nmb> si rezultate_<nmb>/verdict_<nmb>
# ETAPA 2: extrage code, solution, hints din tutorial si salveaza in code_solution_hints_<nmb>.json

import os
import sys
import time
import random
import glob
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import traceback

# Force stdout encoding to UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Import functiile din extract_code_solution_hints.py
from merged_problems_nume_si_enunt import extract_problems_from_html
from extract_code_solution_hints import (
    extract_code_from_html,
    extract_solution_from_html,
    extract_hints_from_html,
    extract_problem_statement,
    extract_tutorial_section,
    extract_editorial_section,
    extract_tutorial_content,
    random_delay
)

# Lista de User-Agents pentru rotatie
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

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


def extract_submissions_from_html(html_file="problemset_page.html"):
    """
    Extrage toate submisiile din fisierul HTML si returneaza o lista de dictionare
    cu informatii despre fiecare submisie (submission_id, contest_id, link).
    """
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    
    submissions = []
    
    # Gasim toate randurile din tabel care au data-submission-id
    rows = soup.find_all("tr", attrs={"data-submission-id": True})
    
    for row in rows:
        submission_id = row.get("data-submission-id")
        
        # Gasim linkul catre submisie (contine contest_id)
        link_tag = row.find("a", class_="view-source")
        if link_tag and link_tag.get("href"):
            href = link_tag.get("href")
            # href este de forma: /problemset/submission/2185/358654970
            # Extragem contest_id din href
            parts = href.split("/")
            if len(parts) >= 4:
                contest_id = parts[3]  # ex: 2185
                
                submissions.append({
                    "submission_id": submission_id,
                    "contest_id": contest_id,
                    "url": f"https://codeforces.com{href}"
                })
    
    print(f"Found {len(submissions)} submissions in {html_file}")
    return submissions


def extract_and_save_failed_test(driver, submission_id, verdict_dir="results/verdict"):
    """
    Extrage si salveaza ultimul test failed pentru o submisie care nu are verdictul Accepted.
    Face click pe butonul 'Click to see test details', asteapta incarcarea testelor,
    si salveaza HTML-ul ultimului test care nu e OK.
    
    Args:
        driver: Selenium WebDriver
        submission_id: ID-ul submisiei
        verdict_dir: Directorul unde se salveaza fisierele cu verdictele
    
    Returns:
        True daca a reusit sa salveze, False altfel
    """
    try:
        # Cream directorul daca nu exista
        if not os.path.exists(verdict_dir):
            os.makedirs(verdict_dir)
            print(f"        Created verdict directory: {verdict_dir}")
        
        # Verificam daca fisierul deja exista
        output_file = os.path.join(verdict_dir, f"submission_{submission_id}.html")
        if os.path.exists(output_file):
            print(f"        ⊙ Verdict already saved")
            return True
        
        # Verificam verdictul in problemset_page.html (MAI INTAI, inainte de click)
        with open("problemset_page.html", "r", encoding="utf-8") as f:
            problemset_soup = BeautifulSoup(f.read(), "html.parser")
        
        # Cautam submisia dupa ID in fisierul problemset_page.html
        submission_wrapper = problemset_soup.find("span", class_="submissionVerdictWrapper", attrs={"submissionid": submission_id})
        
        if submission_wrapper:
            # Verificam daca are verdict-accepted (OK)
            if submission_wrapper.find("span", class_="verdict-accepted"):
                print(f"        ✓ Verdict: Accepted - skipping test extraction")
                return False
        
        # IMPORTANT: Delay aleatoriu ÎNAINTE de a face click (2-7 minute pentru anti-Cloudflare)
        delay_before_click = random.uniform(65, 120)
        print(f"        ⏳ Verdict NOT Accepted - waiting {delay_before_click:.0f}s ({delay_before_click/60:.1f} min) before clicking...")
        time.sleep(delay_before_click)
        
        # Daca nu e Accepted, cautam butonul pentru a vedea testele
        try:
            click_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "click-to-view-tests"))
            )
            
            print(f"        🖱️  Clicking to view test details...")
            driver.execute_script("arguments[0].click();", click_button)
            
            # Asteptam sa se incarce testele (cautam elemente cu clasa test result)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "verdict"))
            )
            
            # Delay mic pentru a se incarca complet toate testele
            time.sleep(2)
            
            # Parsam HTML-ul actualizat
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # Gasim toate test box-urile
            test_boxes = soup.find_all("div", class_="roundbox")
            
            # Cautam ultimul test care nu e OK/Accepted
            last_failed_test = None
            for box in reversed(test_boxes):  # parcurgem de la sfarsit
                verdict_elem = box.find("span", class_="verdict")
                if verdict_elem:
                    verdict_text = verdict_elem.get_text(strip=True)
                    # Daca nu e OK/Accepted, salvam acest test
                    if "ok" not in verdict_text.lower() and "accepted" not in verdict_text.lower():
                        last_failed_test = box
                        break
            
            if last_failed_test:
                # Salvam HTML-ul ultimului test failed
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(str(last_failed_test.prettify()))
                
                verdict_text = last_failed_test.find("span", class_="verdict").get_text(strip=True)
                print(f"        ✓ Saved last failed test (Verdict: {verdict_text})")
                
                # IMPORTANT: Delay aleatoriu DUPĂ salvarea testului (anti-Cloudflare)
                delay_after_save = random.uniform(30, 65)
                print(f"        ⏳ Waiting {delay_after_save:.0f}s ({delay_after_save/60:.1f} min) after test extraction...")
                time.sleep(delay_after_save)
                
                return True
            else:
                print(f"        ⚠️  No failed tests found")
                return False
                
        except Exception as e:
            print(f"        ⚠️  Could not extract tests: {str(e)}")
            return False
            
    except Exception as e:
        print(f"        ✗ Error in extract_and_save_failed_test: {str(e)}")
        return False


def save_all_submissions(submissions, output_dir="results/submission_pages", 
                        verdict_dir="results/verdict",
                        min_delay=25, max_delay=45, batch_size=8, 
                        long_pause_min=120, long_pause_max=300,
                        change_useragent=True, debug_port_start=9308,
                        chrome_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                        user_data_dir="C:\\chrome_debug_temp"):
    """
    Pentru fiecare submisie, acceseaza linkul si salveaza continutul HTML intr-un fisier.
    Implementeaza strategii anti-Cloudflare: delay-uri variabile, pauze lungi, comportament natural.
    
    Args:
        submissions: Lista de dictionare cu informatii despre submisii
        output_dir: Directorul unde se salveaza fisierele HTML
        verdict_dir: Directorul unde se salveaza verdictele
        min_delay: Delay minim intre request-uri (secunde)
        max_delay: Delay maxim intre request-uri (secunde)
        batch_size: Cate submisii sa proceseze inainte de o pauza lunga
        long_pause_min: Durata minima a pauzei lungi (secunde)
        long_pause_max: Durata maxima a pauzei lungi (secunde)
        change_useragent: Daca True, asteapta reconectare cu User-Agent diferit dupa fiecare batch
        debug_port_start: Portul initial de debug pentru Chrome
        chrome_path: Calea catre chrome.exe
        user_data_dir: Directorul pentru user data
    """
    # Cream directorul daca nu exista
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
    
    total = len(submissions)
    processed = 0
    skipped = 0
    errors = 0
    current_port = debug_port_start
    batch_number = 0
    
    print(f"\n{'='*60}")
    print(f"Starting to process {total} submissions")
    print(f"Settings: delay={min_delay}-{max_delay}s, batch_size={batch_size}")
    print(f"User-Agent rotation: {'ENABLED' if change_useragent else 'DISABLED'}")
    print(f"Port rotation: Starting from {debug_port_start}")
    print(f"{'='*60}\n")
    
    # Conectare initiala
    driver = setup_driver(current_port)
    if not driver:
        print("❌ Failed to connect to Chrome. Please start Chrome with:")
        user_agent = USER_AGENTS[batch_number % len(USER_AGENTS)]
        print(f'& "{chrome_path}" --remote-debugging-port={current_port} --user-data-dir="{user_data_dir}" --user-agent="{user_agent}"')
        return
    
    for i, sub in enumerate(submissions):
        submission_id = sub["submission_id"]
        contest_id = sub["contest_id"]
        url = sub["url"]
        
        output_file = os.path.join(output_dir, f"submission_{submission_id}.html")
        
        # Skip daca fisierul exista deja
        if os.path.exists(output_file):
            print(f"[{i+1}/{total}] ✓ Skipping {submission_id} (already exists)")
            skipped += 1
            
            # IMPORTANT: Delay aleatoriu și pentru submisiile existente (anti-Cloudflare)
            delay = random.uniform(min_delay, max_delay)
            print(f"    ⏳ Waiting {delay:.1f}s before next request...")
            time.sleep(delay)
            
            # Pauza lunga dupa fiecare batch (inclusiv pentru cele skipped)
            total_processed = processed + skipped
            if total_processed > 0 and total_processed % batch_size == 0 and i < total - 1:
                if not change_useragent:
                    long_pause = random.uniform(long_pause_min, long_pause_max)
                    print(f"\n{'─'*60}")
                    print(f"🛑 BATCH PAUSE after {total_processed} submissions ({processed} new, {skipped} skipped)")
                    print(f"   Progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")
                    print(f"   Taking a long break: {long_pause:.0f}s ({long_pause/60:.1f} minutes)")
                    print(f"{'─'*60}\n")
                    time.sleep(long_pause)
            
            continue
        
        print(f"[{i+1}/{total}] → Fetching submission {submission_id}")
        print(f"    URL: {url}")
        
        try:
            # Acceseaza pagina
            driver.get(url)
            
            # Asteptam incarcarea paginii
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # Small random delay pentru a simula citirea paginii
            time.sleep(random.uniform(1, 3))
            
            # Salvam HTML-ul
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            print(f"    ✓ Saved successfully")
            processed += 1
            
            # Incercam sa extragem si salvam ultimul test failed (daca nu e Accepted)
            print(f"    📊 Checking for failed tests...")
            extract_and_save_failed_test(driver, submission_id, verdict_dir=verdict_dir)
            
            # Delay variabil pentru a evita pattern-uri predictibile
            delay = random.uniform(min_delay, max_delay)
            print(f"    ⏳ Waiting {delay:.1f}s before next request...")
            time.sleep(delay)
            
            # Pauza lunga dupa fiecare batch
            if processed > 0 and processed % batch_size == 0 and i < total - 1:
                print(f"\n{'─'*60}")
                print(f"🛑 BATCH {batch_number + 1} COMPLETE ({processed} processed)")
                print(f"   Progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")
                print(f"{'─'*60}\n")
                
                if not change_useragent:
                    long_pause = random.uniform(long_pause_min, long_pause_max)
                    print(f"   Taking a long break: {long_pause:.0f}s ({long_pause/60:.1f} minutes)")
                    time.sleep(long_pause)
            
        except Exception as e:
            print(f"    ✗ Error fetching {submission_id}: {str(e)}")
            errors += 1
            # In caz de eroare, asteapta putin mai mult
            error_delay = random.uniform(max_delay, max_delay * 2)
            print(f"    ⏳ Waiting {error_delay:.1f}s after error...")
            time.sleep(error_delay)
            continue
    
    # Cleanup
    try:
        driver.quit()
    except:
        pass
    
    print(f"\n{'='*60}")
    print(f"FINISHED!")
    print(f"Total submissions: {total}")
    print(f"Successfully processed: {processed}")
    print(f"Skipped (already exists): {skipped}")
    print(f"Errors: {errors}")
    print(f"Output directory: {output_dir}/")
    print(f"{'='*60}\n")


def extract_code_solution_hints(driver, problemset_file, page_number, 
                                output_folder="code_solution_hints_folder",
                                min_delay=90, max_delay=240):
    """
    ETAPA 2: Extrage Code, Solution si Hints din fiecare problem din tutorial.
    
    Args:
        driver: Selenium WebDriver
        problemset_file: Calea catre fisierul problemset HTML
        page_number: Numarul paginii (pentru creare json output_<nmb>)
        output_folder: Folderul unde se salveaza json-urile
        min_delay: Delay minim intre requesturi (secunde)
        max_delay: Delay maxim intre requesturi (secunde)
    """
    print(f"\n{'='*80}")
    print(f"ETAPA 2: Extracting Code, Solution, Hints for page {page_number}")
    print(f"File: {os.path.basename(problemset_file)}")
    print(f"{'='*80}\n")
    
    # Cream folderul de output daca nu exista
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"✓ Created directory: {output_folder}")
    
    # Extrago lista de probleme din fisierul problemset
    print("🔍 Extracting problems from problemset file...")
    problems_dict = extract_problems_from_html(problemset_file)
    
    if not problems_dict:
        print(f"⚠️  No problems found in {problemset_file}")
        return
    
    print(f"✓ Found {len(problems_dict)} problems")
    
    # JSON output file
    output_file = os.path.join(output_folder, f"code_solution_hints_{page_number}.json")
    
    # Incarcam rezultatele existente daca fisierul exista
    results = {}
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print(f"✓ Loaded {len(results)} existing results from {output_file}\n")
    
    total = len(problems_dict)
    processed = 0
    skipped = 0
    errors = 0
    
    print(f"\n{'='*60}")
    print(f"Processing {total} problems")
    print(f"Delay: {min_delay}-{max_delay}s ({min_delay/60:.1f}-{max_delay/60:.1f} minutes)")
    print(f"IMPORTANT: Long delays to avoid Cloudflare blocking!")
    print(f"{'='*60}\n")
    
    for i, (problem_code, problem_info) in enumerate(problems_dict.items()):
        print(f"[{i+1}/{total}] Processing {problem_code}: {problem_info['name']}")
        
        # Skip daca deja am procesat problema
        if problem_code in results:
            print(f"    ✓ Already processed, skipping...")
            skipped += 1
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
            
            # Delay inainte de a cauta Tutorial (1.5-4 minute)
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
            
            # Delay mare (1.5-4 min) inainte de urmatoarea problema
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
    print(f"ETAPA 2 FINISHED!")
    print(f"Total problems: {total}")
    print(f"Successfully processed: {processed}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print(f"Output file: {output_file}")
    print(f"{'='*60}\n")
    
    return output_file


def process_problemset_file(problemset_file, page_number, debug_port=9308):
    """
    Proceseaza un fisier de problemset:
    - Extrage submisiile din fisierul HTML
    - Creeaza folderele results_<nmb>/submission_pages_<nmb> si results_<nmb>/verdict_<nmb>
    - Descarca si salveaza submisiile si verdictele
    
    Args:
        problemset_file: Calea catre fisierul problemset HTML
        page_number: Numarul paginii (pentru creare foldere)
        debug_port: Portul pour conexiunea Chrome
    """
    print(f"\n{'='*80}")
    print(f"PROCESSING FILE {page_number}: {os.path.basename(problemset_file)}")
    print(f"{'='*80}\n")
    
    # Creare directoare
    base_results_dir = f"results_{page_number}"
    submission_pages_dir = os.path.join(base_results_dir, f"submission_pages_{page_number}")
    verdict_dir = os.path.join(base_results_dir, f"verdict_{page_number}")
    
    for dir_path in [base_results_dir, submission_pages_dir, verdict_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"✓ Created directory: {dir_path}")
    
    # Extrage submisiile din fisierul problemset
    submissions = extract_submissions_from_html(problemset_file)
    
    if not submissions:
        print(f"⚠️  No submissions found in {problemset_file}")
        return
    
    # Proceseaza submisiile
    print("\n" + "=" * 60)
    print(f"STEP 3: Processing submissions for page {page_number}")
    print("=" * 60)
    print("\nUsing SAME browser with VERY LONG pauses - safer for Cloudflare!")
    print("Random delay of 1.5-2 minutes between EACH request!\n")
    
    save_all_submissions(
        submissions,
        output_dir=submission_pages_dir,
        verdict_dir=verdict_dir,
        min_delay=80,               # minim 80 secunde intre requests
        max_delay=120,              # maxim 120 secunde intre requests  
        batch_size=8,               # pauza lunga la fiecare 8 submisii
        long_pause_min=180,         # pauza de 3 minute
        long_pause_max=360,         # pauza de 6 minute
        change_useragent=False,     # NU schimba User-Agent (mai sigur!)
        debug_port_start=debug_port,
        chrome_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        user_data_dir="C:\\chrome_debug_temp"
    )
    
    print(f"\n✓ Completed processing for page {page_number}")
    print(f"  Results saved in: {os.path.abspath(base_results_dir)}")
    
    # ETAPA 2: Extrage code, solution si hints din tutorial
    print(f"\n" + "="*80)
    print(f"PROCEEDING TO STAGE 2: Extract Code, Solution, Hints")
    print("="*80)
    
    # Conectare la browser pentru etapa 2
    print(f"\nMake sure Chrome is running with:")
    print(f'& "{chrome_path}" --remote-debugging-port={debug_port} --user-data-dir="{user_data_dir}"\n')
    
    driver = setup_driver(debug_port)
    if not driver:
        print("❌ Failed to connect to Chrome for stage 2. Please start Chrome with the command above.")
        return
    
    # Procesam tutorial-urile pentru aceasta pagina
    extract_code_solution_hints(
        driver,
        problemset_file,
        page_number,
        output_folder="code_solution_hints_folder",
        min_delay=90,   # 1.5 minute
        max_delay=240   # 4 minute
    )
    
    # Cleanup
    try:
        driver.quit()
    except:
        pass


if __name__ == "__main__":
    try:
        # Configurare
        DEBUG_PORT_START = 9308
        CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        USER_DATA_DIR = "C:\\chrome_debug_temp"
        PROBLEMSET_PAGES_DIR = "problemset_pages"
        
        print("=" * 80)
        print("MAIN SCRAPER - Procesarea mai multor fisiere de problemset")
        print("=" * 80)
        print(f"\nMake sure Chrome is running with:")
        print(f'& "{CHROME_PATH}" --remote-debugging-port={DEBUG_PORT_START} --user-data-dir="{USER_DATA_DIR}"\n')
        
        # Gaseste toate fisierele HTML din folderul problemset_pages
        if not os.path.exists(PROBLEMSET_PAGES_DIR):
            print(f"❌ Directory '{PROBLEMSET_PAGES_DIR}' not found!")
            sys.exit(1)
        
        problemset_files = sorted(glob.glob(os.path.join(PROBLEMSET_PAGES_DIR, "*.html")))
        
        if not problemset_files:
            print(f"❌ No HTML files found in '{PROBLEMSET_PAGES_DIR}'!")
            sys.exit(1)
        
        print(f"Found {len(problemset_files)} problemset files to process:")
        for i, file in enumerate(problemset_files, 1):
            print(f"  {i}. {os.path.basename(file)}")
        
        # Proceseaza fiecare fisier
        for i, problemset_file in enumerate(problemset_files, 1):
            # Calculeaza portul Debug pentru fiecare fisier
            debug_port = DEBUG_PORT_START + (i - 1) * 10  # ex: 9308, 9318, 9328...
            
            try:
                process_problemset_file(problemset_file, i, debug_port)
            except Exception as e:
                print(f"\n❌ Error processing {problemset_file}:")
                print(f"   {str(e)}")
                traceback.print_exc()
                continue
            
            # Pauza mare intre procesarea fisierelor
            if i < len(problemset_files):
                pause_time = random.uniform(300, 600)  # 5-10 minute intre fisiere
                print(f"\n🛑 Waiting {pause_time:.0f}s ({pause_time/60:.1f} minutes) before next file...")
                time.sleep(pause_time)
        
        print("\n" + "=" * 80)
        print("✓ MAIN SCRAPER COMPLETED!")
        print(f"  Processed {len(problemset_files)} problemset files")
        print(f"  Results saved in results_1, results_2, etc.")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

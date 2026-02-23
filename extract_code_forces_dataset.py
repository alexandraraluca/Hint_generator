#In this file I will extract multiple submissions from this page(https://codeforces.com/problemset/status) using selenium and for each one of them I will save the html file of that submission and extract the hint and the code from that submission and the official code.

import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
import sys
import time
import random
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup

# Force stdout encoding to UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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


def save_all_submissions(submissions, output_dir="results/submission_pages", 
                        min_delay=25, max_delay=45, batch_size=8, 
                        long_pause_min=120, long_pause_max=300,
                        change_useragent=True, debug_port_start=9195,
                        chrome_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                        user_data_dir="C:\\chrome_debug_temp"):
    """
    Pentru fiecare submisie, acceseaza linkul si salveaza continutul HTML intr-un fisier.
    Implementeaza strategii anti-Cloudflare: delay-uri variabile, pauze lungi, comportament natural.
    
    Args:
        submissions: Lista de dictionare cu informatii despre submisii
        output_dir: Directorul unde se salveaza fisierele HTML
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
            
            # Delay variabil pentru a evita pattern-uri predictibile
            delay = random.uniform(min_delay, max_delay)
            print(f"    ⏳ Waiting {delay:.1f}s before next request...")
            time.sleep(delay)
            
            # Pauza lunga dupa fiecare batch + schimbare User-Agent si Port
            if processed > 0 and processed % batch_size == 0 and i < total - 1:
                print(f"\n{'─'*60}")
                print(f"🛑 BATCH {batch_number + 1} COMPLETE ({processed} processed)")
                print(f"   Progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")
                print(f"{'─'*60}\n")
                
                if change_useragent:
                    # Incrementam batch number si portul
                    batch_number += 1
                    current_port = debug_port_start + batch_number
                    
                    # Selectam un User-Agent din lista
                    user_agent = USER_AGENTS[batch_number % len(USER_AGENTS)]
                    
                    print("🔄 Time to change User-Agent and Port!")
                    print("\n" + "="*60)
                    print("STEPS TO FOLLOW:")
                    print("="*60)
                    print("\n1. Close your Chrome browser completely (all windows)\n")
                    print("2. Open PowerShell and run this command:\n")
                    print(f'& "{chrome_path}" --remote-debugging-port={current_port} --user-data-dir="{user_data_dir}" --user-agent="{user_agent}"\n')
                    print("3. Wait for Chrome to open")
                    print("4. Login to Codeforces if needed")
                    print("5. Press ENTER here to continue...\n")
                    print("="*60)
                    
                    # Inchidem conexiunea curenta
                    try:
                        driver.quit()
                    except:
                        pass
                    
                    # Asteptam input de la user
                    input("\n⏸️  Press ENTER when Chrome is ready with new settings...")
                    
                    # Reconectare la noul port
                    print("\n🔌 Reconnecting to Chrome...")
                    attempts = 0
                    max_attempts = 3
                    while attempts < max_attempts:
                        driver = setup_driver(current_port)
                        if driver:
                            print("✓ Reconnected successfully!\n")
                            break
                        attempts += 1
                        if attempts < max_attempts:
                            print(f"⚠️  Connection attempt {attempts} failed. Retrying in 5s...")
                            time.sleep(5)
                    
                    if not driver:
                        print("❌ Failed to reconnect after 3 attempts. Exiting...")
                        return
                    
                    # Small delay dupa reconectare
                    time.sleep(3)
                else:
                    # Pauza normala fara schimbarea User-Agent-ului
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


if __name__ == "__main__":
    try:
        # Configurare
        DEBUG_PORT_START = 9195  # Portul initial
        CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        USER_DATA_DIR = "C:\\chrome_debug_temp"
        
        # Conectare initiala pentru a salva pagina principala
        print("=" * 60)
        print("STEP 1: Connecting to Chrome to save main page")
        print("=" * 60)
        print("\nMake sure Chrome is running with:")
        print(f'& "{CHROME_PATH}" --remote-debugging-port={DEBUG_PORT_START} --user-data-dir="{USER_DATA_DIR}"\n')
        
        driver = setup_driver(DEBUG_PORT_START)
        if not driver:
            print("\n❌ Please start Chrome with the command above and try again.")
            sys.exit(1)
        
        # Save the page source (daca nu exista deja)
        # if not os.path.exists("problemset_page.html"):
        #     with open("problemset_page.html", "w", encoding="utf-8") as f:
        #         f.write(driver.page_source)
        #     print("✓ Page saved successfully in problemset_page.html!")
        # else:
        #     print("✓ Using existing problemset_page.html")
        
        driver.quit()
        
        # Extrage submisiile
        print("\n" + "=" * 60)
        print("STEP 2: Extracting submissions from HTML")
        print("=" * 60)
        submissions = extract_submissions_from_html("problemset_page.html")
        
        print("\n" + "=" * 60)
        print("STEP 3: Processing submissions (NO User-Agent rotation)")
        print("=" * 60)
        print("\nUsing SAME browser with long pauses - safer for Cloudflare!")
        print("Long pause of 2-5 minutes after every 8 submissions.\n")
        
        # Procesam TOATE submisiile cu strategii anti-Cloudflare
        # MODIFIED: change_useragent=False pentru a evita blocarea Cloudflare
        save_all_submissions(
            submissions,
            output_dir="results/submission_pages",
            min_delay=20,                # minim 20 secunde intre requests
            max_delay=50,                # maxim 50 secunde intre requests  
            batch_size=8,                # pauza lunga la fiecare 8 submisii
            long_pause_min=180,          # pauza de 3 minute
            long_pause_max=360,          # pauza de 6 minute
            change_useragent=False,      # DISABLED: NU schimba User-Agent (mai sigur!)
            debug_port_start=DEBUG_PORT_START,
            chrome_path=CHROME_PATH,
            user_data_dir=USER_DATA_DIR
        )
    
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
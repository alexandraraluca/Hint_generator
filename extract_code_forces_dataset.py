#In this file I will extract multiple submissions from this page(https://codeforces.com/problemset/status) using selenium and for each one of them I will save the html file of that submission and extract the hint and the code from that submission and the official code.

import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
import sys
import time
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup

# Force stdout encoding to UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def setup_driver():
    options = webdriver.ChromeOptions()
    debug_address = "127.0.0.1:9222"
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


def save_all_submissions(driver, submissions, output_dir="results/submission_pages", delay=3):
    """
    Pentru fiecare submisie, acceseaza linkul si salveaza continutul HTML intr-un fisier.
    
    Args:
        driver: Selenium WebDriver
        submissions: Lista de dictionare cu informatii despre submisii
        output_dir: Directorul unde se salveaza fisierele HTML
        delay: Delay intre request-uri (pentru a evita blocarea)
    """
    # Cream directorul daca nu exista
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")
    
    total = len(submissions)
    
    for i, sub in enumerate(submissions):
        submission_id = sub["submission_id"]
        contest_id = sub["contest_id"]
        url = sub["url"]
        
        output_file = os.path.join(output_dir, f"submission_{submission_id}.html")
        
        # Skip daca fisierul exista deja
        if os.path.exists(output_file):
            print(f"[{i+1}/{total}] Skipping {submission_id} (already exists)")
            continue
        
        print(f"[{i+1}/{total}] Fetching submission {submission_id} from {url}")
        
        try:
            driver.get(url)
            
            # Asteptam incarcarea paginii
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            # Salvam HTML-ul
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            print(f"    Saved to {output_file}")
            
            # Delay pentru a nu fi blocat
            time.sleep(delay)
            
        except Exception as e:
            print(f"    Error fetching {submission_id}: {str(e)}")
            continue
    
    print(f"\nDone! Saved {total} submissions to {output_dir}/")


try:

    #First, I will access this page, where I can see the id of the problems and the links for the submission and the problem and the status of the submission
    # I can build the link for the following:
        # https://codeforces.com/problemset/submission/1811/356978384
        # https://codeforces.com/problemset/problem/1811/A
        # https://codeforces.com/profile/fatema.akte (userul in case I wnat all his subbmisions)
    # driver.get("https://codeforces.com/problemset/status")

    # driver.get("https://codeforces.com/problemset/status/page/3?order=BY_ARRIVED_DESC") # we access the 3 page with all submissions to know that the code was tested for all submissions
    # # Wait for page load
    # WebDriverWait(driver, 10).until(
    #     lambda d: d.execute_script("return document.readyState") == "complete"
    # )
    
    # Save the page source
    with open("problemset_page.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Page saved successfully in problemset_page.html!")

    submissions = extract_submissions_from_html("problemset_page.html")

    #save_all_submissions(driver, submissions, output_dir="results/submission_pages", delay=2)

    time.sleep(60)
    save_all_submissions(driver, submissions[:2], output_dir="results/submission_pages", delay=40)

except Exception as e:
    print(f"An error occurred: {str(e)}")
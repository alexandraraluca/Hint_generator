"""
Script pentru extragerea enunturilor, tutorialelor, solutiilor si hints de pe Codeforces.
Foloseste delay-uri mari (2-7 minute) pentru a evita blocarea Cloudflare.
"""

import os
import json
import time
import random
import traceback
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


def extract_tutorial_from_saved_html(html_file_path, problem_code):
    """
    Extrage Code, Solution si Hints din HTML-ul salvat anterior.
    
    Args:
        html_file_path: Calea catre fisierul HTML salvat
        problem_code: Codul problemei
    
    Returns:
        dict cu campurile: code, solution, hints
    """
    tutorial_data = {
        'code': None,
        'solution': None,
        'hints': None
    }
    
    try:
        # Citim HTML-ul din fisier
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Parsam HTML-ul
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extragem cele 3 componente (specifice acestei probleme)
        tutorial_data['code'] = extract_code_from_html(soup, problem_code)
        tutorial_data['solution'] = extract_solution_from_html(soup, problem_code)
        tutorial_data['hints'] = extract_hints_from_html(soup, problem_code)
        
        print(f"        ✓ Extracted tutorial data for {problem_code} from saved HTML")
        if tutorial_data['code']:
            print(f"            ✓ Code: {len(tutorial_data['code'])} chars")
        if tutorial_data['solution']:
            print(f"            ✓ Solution: {len(tutorial_data['solution'])} chars")
        if tutorial_data['hints']:
            if isinstance(tutorial_data['hints'], list):
                print(f"            ✓ Hints: {len(tutorial_data['hints'])} items")
            else:
                print(f"            ✓ Hints found")
        
        return tutorial_data
    
    except Exception as e:
        print(f"        ⚠️ Error extracting from saved HTML: {str(e)}")
        return None


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


def random_delay(min_sec=40, max_sec=120, message="Waiting"):
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


def find_problem_section(soup, problem_code):
    """
    Gaseste si izoleaza sectiunea HTML pentru o anumita problema.
    Cauta linkul /problem/X">...PROBLEM_CODE in HTML si extrage
    continutul pana la:
    1. Urmatoarea /problem/Y (Y = next letter), SAU
    2. <a name="comments"> (sectiunea de comentarii a oamenilor)
    
    Returns: BeautifulSoup object cu doar continutul acelei probleme
    """
    try:
        search_code = problem_code.upper()
        html_str = soup.prettify()
        
        # Cautam linkul /problem/X">
        problem_letter = search_code[-1]  # 'C' din '2192C'
        
        # Pattern: /problem/C"> (mai flexibil)
        link_pattern = f'/problem/{problem_letter}"'
        start_pos = html_str.find(link_pattern)
        
        if start_pos == -1:
            print(f"        ⚠️ Could not find /problem/{problem_letter}\" for {search_code}")
            return soup  # Nu gasit, returneaza tot
        
        # Verifica ca urmatoarele caractere contin codul problemei
        check_window = html_str[start_pos:start_pos + 150]
        if search_code not in check_window:
            print(f"        ⚠️ Found /problem/{problem_letter} but {search_code} not in next 150 chars")
            return soup
        
        print(f"        ✓ Found editorial for {search_code}")
        
        # Gasim urmatoarea problema: /problem/Y unde Y = next letter
        next_letter = chr(ord(problem_letter) + 1)
        next_pattern = f'/problem/{next_letter}"'
        end_pos = html_str.find(next_pattern, start_pos + 50)
        
        # IMPORTANT: Verifica si pentru <a name="comments"> - aceasta e inceput comentariilor oamenilor!
        comments_marker = '<a name="comments">'
        comments_pos = html_str.find(comments_marker, start_pos + 50)
        
        if end_pos == -1:
            # Nu gasit urmatoarea problema
            if comments_pos != -1:
                # Dar gasit sectiunea comentariilor - mergem pana acolo
                end_pos = comments_pos
                print(f"        ✓ Stopping at comments section")
            else:
                # Nici sectiunea comentariilor nu exista, mergem pana la sfarsit
                end_pos = len(html_str)
        else:
            # Gasit urmatoarea problema, dar verifica daca comentariile vin mai devreme
            if comments_pos != -1 and comments_pos < end_pos:
                end_pos = comments_pos
                print(f"        ✓ Stopping at comments section (inainte de urmatoarea problema)")
        
        # Extragem sectiunea
        section_html = html_str[start_pos:end_pos]
        
        # Parsam doar aceasta sectiune
        section_soup = BeautifulSoup(section_html, 'html.parser')
        return section_soup
        
    except Exception as e:
        print(f"        ⚠️ Error finding problem section: {str(e)}")
        return soup  # Fallback


def extract_hints_from_html(soup, problem_code=None):
    """Extrage hints-urile (Hint, Hint1, Hint2, etc) din tutorialul problemei."""
    hints = []
    
    try:
        # Daca avem problem_code, incearcam sa izolam sectiunea problemei
        if problem_code:
            section = find_problem_section(soup, problem_code)
            if section:
                soup = section
        
        # Cauta pentru toți spoilers care contin Hint/Hint1/Hint2/etc in titlu
        spoilers = soup.find_all("div", class_="spoiler")
        for spoiler in spoilers:
            # Cauta titlul spoilerului
            spoiler_title = spoiler.find("b", class_="spoiler-title")
            if spoiler_title is None:
                spoiler_title = spoiler.find("p", class_="spoiler-title")
            
            if spoiler_title:
                title_text = spoiler_title.get_text(strip=True).lower()
                # Verifica daca titlul incepe cu "hint" (Hint, Hint1, Hint2, HintA, etc)
                if title_text.startswith("hint"):
                    # Extrage conținutul din spoiler-content
                    hint_content_div = spoiler.find("div", class_="spoiler-content")
                    if hint_content_div:
                        hint_text = hint_content_div.get_text(strip=True)
                        if hint_text and len(hint_text) > 10:
                            hints.append(hint_text[:500])  # Primele 500 caractere
        
        return hints if hints else None
    except Exception as e:
        print(f"            ⚠️ Error extracting hints: {str(e)}")
        return None


def extract_code_from_submission_url(driver, submission_url):
    """
    Extrage codul din pagina unei submission pe Codeforces folosind Selenium (Chrome real).
    IMPORTANT: Folosim Selenium in loc de requests pentru a evita HTTP 403 Forbidden!
    
    Args:
        driver: Selenium WebDriver (Chrome real browser)
        submission_url: URL-ul submission-ului (de exemplu: https://codeforces.com/contest/2157/submission/350380442)
    
    Returns:
        Codul din submission sau None daca nu se reuseste
    """
    try:
        print(f"                🌐 Fetching code from submission: {submission_url}")
        
        # Adauga delay pentru a evita rate limiting
        time.sleep(random.uniform(90, 240))
        
        # Navigam la pagina submission folosind Selenium Driver (Chrome real)
        # Asta evita HTTP 403 Forbidden!
        driver.get(submission_url)
        
        # Asteptam sa se incarce pagina
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Parsam HTML-ul
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Cauta codul in <pre id="program-source-text"> (formatare moderna Codeforces)
        program_source = soup.find("pre", id="program-source-text")
        if program_source:
            code_text = program_source.get_text(strip=True)
            if code_text and len(code_text) > 30:
                print(f"                ✓ Extracted {len(code_text)} chars of code from submission")
                return code_text
        
        # Fallback: Cauta orice <pre> care arata a fi cod
        pre_blocks = soup.find_all("pre")
        for pre_block in pre_blocks:
            code_text = pre_block.get_text(strip=True)
            if code_text and (
                "#include" in code_text or 
                "int main" in code_text or 
                "void solve" in code_text or
                code_text.count('{') > 2
            ):
                if len(code_text) > 30:
                    print(f"                ✓ Extracted {len(code_text)} chars of code from submission (fallback)")
                    return code_text
        
        print(f"                ⚠️ Could not find code block in submission page")
        return None
        
    except TimeoutException:
        print(f"                ⚠️ Timeout fetching submission")
        return None
    except Exception as e:
        print(f"                ⚠️ Error extracting code from submission: {str(e)}")
        return None


def extract_code_from_html(soup, problem_code=None, driver=None):
    """Extrage CODUL din HTML-ul tutorialului, specific problemei (dupa linia cu problemei).
    
    Args:
        soup: BeautifulSoup object cu HTML-ul
        problem_code: Codul problemei pentru izolare sectiune
        driver: Optional Selenium WebDriver pentru a fetch submission-urile (evita 403 Forbidden!)
    """
    try:
        # Daca avem problem_code, incearcam sa izolam sectiunea problemei
        if problem_code:
            section = find_problem_section(soup, problem_code)
            if section:
                soup = section
        
        # PRIORITATE 1: Cauta pentru bloc de cod actual (pre/code tags cu C++ code)
        pre_blocks = soup.find_all("pre")
        for pre_block in pre_blocks:
            code_text = pre_block.get_text(strip=True)
            # Verifica daca pare a fi cod C++ (contine #include, int main, etc)
            if code_text and (
                "#include" in code_text or 
                "int main" in code_text or 
                "void solve" in code_text or
                code_text.count('{') > 2  # Probabil cod
            ):
                # Returneaza codul
                if len(code_text) > 50:
                    return code_text[:3000]
        
        # PRIORITATE 2: Cauta linkuri de submission cu formatul /contest/XXXX/submission/NNNNN
        for link in soup.find_all("a", href=True):
            href = link.get('href')
            
            # Verifica daca linkul este o submission (si nu e comentariu)
            if href and "/submission/" in href and "/contest/" in href:
                # Construim URL complet si extragem codul
                if href.startswith('/'):
                    href = f"https://codeforces.com{href}"
                
                # Extragem codul din pagina submission DOAR daca avem driver (Chrome real)
                if driver:
                    code = extract_code_from_submission_url(driver, href)
                    if code:
                        return code
                else:
                    # Fara driver, nu putem fetch submission (ar primi 403 Forbidden)
                    print(f"                ⚠️ Cannot fetch submission without Selenium driver: {href}")
                # Daca nu am gasit codul, continua sa cauta in pagina actuala
        
        # PRIORITATE 3: Cauta pentru spoilers cu "Code" in titlu care contain cod
        spoilers = soup.find_all("div", class_="spoiler")
        for spoiler in spoilers:
            spoiler_title = spoiler.find("b", class_="spoiler-title")
            if spoiler_title is None:
                spoiler_title = spoiler.find("p", class_="spoiler-title")
                
            if spoiler_title and spoiler_title.get_text(strip=True).lower().startswith("code"):
                # Extrage din spoiler-content
                content_div = spoiler.find("div", class_="spoiler-content")
                if content_div:
                    code_text = content_div.get_text(strip=True)
                    if code_text and len(code_text) > 50:
                        return code_text[:3000]
        
        return None
    except Exception as e:
        print(f"            ⚠️ Error extracting code: {str(e)}")
        return None


def extract_solution_from_html(soup, problem_code=None):
    """Extrage explicatia solutiei din HTML-ul tutorialului, specific problemei.
    Cauta in 2 moduri:
    1. Spoiler cu titlu "Solution"
    2. Plain text in <div class="ttypography"> dupa linia cu codul problemei (caz special)
    
    IMPORTANT: Se opreste la <a name="comments"> - de acolo in jos sunt comentarii ale oamenilor!
    """
    try:
        # Daca avem problem_code, incearcam sa izolam sectiunea problemei
        if problem_code:
            section = find_problem_section(soup, problem_code)
            if section:
                soup = section
        
        # CAZUL 1: Cauta pentru spoilers cu titlu "Solution" (exact match)
        spoilers = soup.find_all("div", class_="spoiler")
        for spoiler in spoilers:
            # Cauta titlul spoilerului (poate fi <b> sau <p>)
            spoiler_header = spoiler.find("b", class_="spoiler-title")
            if spoiler_header is None:
                spoiler_header = spoiler.find("p", class_="spoiler-title")
            
            if spoiler_header:
                header_text = spoiler_header.get_text(strip=True).lower()
                # Verifica daca titlul incepe cu "solution"
                if header_text.startswith("solution"):
                    # Extrage continutul din spoiler-content div
                    content_div = spoiler.find("div", class_="spoiler-content")
                    if content_div:
                        # Extrage TOAT textul din div
                        solution_text = content_div.get_text(strip=True, separator=" ")
                        if solution_text and len(solution_text) > 30:
                            # Returneaza primele 4000 caractere
                            return solution_text[:4000]
        
        # CAZUL 2: Plain text in <div class="ttypography"> (cazul special pentru 318A, 2097F, etc)
        # Cauta ttypography dupa linia cu codul problemei
        ttypography_divs = soup.find_all("div", class_="ttypography")
        for ttypography_div in ttypography_divs:
            text = ttypography_div.get_text(strip=True, separator=" ")
            
            # Verifica daca e text lung (editorial explanation) si nu e comentariu
            # Editorial explanationuri incep cu pattern: "Problem analysis", "In this problem", "it is clear", etc
            if len(text) > 100 and any(phrase in text[:200].lower() for phrase in 
                                       ["problem analysis", "in this problem", "it is clear", 
                                        "we need", "solution", "approach", "observe"]):
                return text[:4000]  # Returneaza primele 4000 caractere
        
        return None
    except Exception as e:
        print(f"            ⚠️ Error extracting solution: {str(e)}")
        return None


def extract_tutorial_section(soup, problem_code=None):
    """Extrage TUTORIAL-ul din HTML-ul paginii (cautand cuvantul 'Tutorial').
    
    Cauta in 2 moduri:
    1. Spoiler cu titlu "Tutorial"
    2. Plain text in <div class="ttypography"> care contine Tutorial explanation
    """
    try:
        # Daca avem problem_code, incearcam sa izolam sectiunea problemei
        if problem_code:
            section = find_problem_section(soup, problem_code)
            if section:
                soup = section
        
        # CAZUL 1: Cauta pentru spoilers cu titlu "Tutorial"
        spoilers = soup.find_all("div", class_="spoiler")
        for spoiler in spoilers:
            # Cauta titlul spoilerului (poate fi <b> sau <p>)
            spoiler_header = spoiler.find("b", class_="spoiler-title")
            if spoiler_header is None:
                spoiler_header = spoiler.find("p", class_="spoiler-title")
            
            if spoiler_header:
                header_text = spoiler_header.get_text(strip=True).lower()
                # Verifica daca titlul incepe cu "tutorial"
                if header_text.startswith("tutorial"):
                    # Extrage continutul din spoiler-content div
                    content_div = spoiler.find("div", class_="spoiler-content")
                    if content_div:
                        tutorial_text = content_div.get_text(strip=True, separator=" ")
                        if tutorial_text and len(tutorial_text) > 30:
                            return tutorial_text[:5000]  # Primele 5000 caractere
        
        # CAZUL 2: Plain text in <div class="ttypography"> care pare a fi Tutorial
        ttypography_divs = soup.find_all("div", class_="ttypography")
        for ttypography_div in ttypography_divs:
            text = ttypography_div.get_text(strip=True, separator=" ")
            # Verifica daca contine cuvintele "tutorial" sau "explanation"
            if len(text) > 100 and any(word in text.lower() for word in ["tutorial", "explanation"]):
                return text[:5000]
        
        return None
    except Exception as e:
        print(f"            ⚠️ Error extracting tutorial section: {str(e)}")
        return None


def extract_editorial_section(soup, problem_code=None):
    """Extrage EDITORIAL-ul din HTML-ul paginii (cautand cuvantul 'Editorial').
    
    Cauta in 2 moduri:
    1. Spoiler cu titlu "Editorial"
    2. Heading/text care contine "Editorial"
    """
    try:
        # Daca avem problem_code, incearcam sa izolam sectiunea problemei
        if problem_code:
            section = find_problem_section(soup, problem_code)
            if section:
                soup = section
        
        # CAZUL 1: Cauta pentru spoilers cu titlu "Editorial"
        spoilers = soup.find_all("div", class_="spoiler")
        for spoiler in spoilers:
            # Cauta titlul spoilerului (poate fi <b> sau <p>)
            spoiler_header = spoiler.find("b", class_="spoiler-title")
            if spoiler_header is None:
                spoiler_header = spoiler.find("p", class_="spoiler-title")
            
            if spoiler_header:
                header_text = spoiler_header.get_text(strip=True).lower()
                # Verifica daca titlul incepe cu "editorial"
                if header_text.startswith("editorial"):
                    # Extrage continutul din spoiler-content div
                    content_div = spoiler.find("div", class_="spoiler-content")
                    if content_div:
                        editorial_text = content_div.get_text(strip=True, separator=" ")
                        if editorial_text and len(editorial_text) > 30:
                            return editorial_text[:5000]  # Primele 5000 caractere
        
        # CAZUL 2: Cauta pentru heading/text care contine "Editorial"
        ttypography_divs = soup.find_all("div", class_="ttypography")
        for ttypography_div in ttypography_divs:
            text = ttypography_div.get_text(strip=True, separator=" ")
            if len(text) > 100 and "editorial" in text.lower():
                # Extrage text pana la urmatoarea sectiune (max 5000 chars)
                return text[:5000]
        
        return None
    except Exception as e:
        print(f"            ⚠️ Error extracting editorial section: {str(e)}")
        return None


def extract_tutorial_content(driver, problem_code):
    """
    Gaseste linkul catre Tutorial/Editorial din pagina problemei si navighează la el.
    Extrage Code, Solution, Hints, Tutorial si Editorial pentru problema.
    
    Returns:
        dict cu campurile: code, solution, hints, Tutorial, Editorial sau None daca nu exista tutorial
    """
    tutorial_data = {
        'code': None,
        'solution': None,
        'hints': None,
        'Tutorial': None,
        'Editorial': None
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
        random_delay(90, 240, "After navigating to Tutorial")
        
        # Asteptam sa se incarce pagina
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Parsam pagina tutorial pentru a extrage Code, Solution, Hints, Tutorial si Editorial
        tutorial_soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Extragem cele 5 componente (specifice acestei probleme)
        # PASS DRIVER pentru a putea fetch submission-urile fara 403 Forbidden!
        tutorial_data['code'] = extract_code_from_html(tutorial_soup, problem_code, driver=driver)
        tutorial_data['solution'] = extract_solution_from_html(tutorial_soup, problem_code)
        tutorial_data['hints'] = extract_hints_from_html(tutorial_soup, problem_code)
        tutorial_data['Tutorial'] = extract_tutorial_section(tutorial_soup, problem_code)
        tutorial_data['Editorial'] = extract_editorial_section(tutorial_soup, problem_code)
        
        # salveaza pagina fiecarui tutorial astfel: tutorial_{problem_code}.html in folderul tutorial_pages_saved
        os.makedirs("tutorial_pages_saved", exist_ok=True)
        with open(f"tutorial_pages_saved/tutorial_{problem_code}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        print(f"        ✓ Extracted tutorial data for {problem_code}")
        if tutorial_data['code']:
            print(f"            ✓ Code: {len(tutorial_data['code'])} chars")
        if tutorial_data['solution']:
            print(f"            ✓ Solution: {len(tutorial_data['solution'])} chars")
        if tutorial_data['hints']:
            print(f"            ✓ Hints: {len(tutorial_data['hints'])} items")
        if tutorial_data['Tutorial']:
            print(f"            ✓ Tutorial: {len(tutorial_data['Tutorial'])} chars")
        if tutorial_data['Editorial']:
            print(f"            ✓ Editorial: {len(tutorial_data['Editorial'])} chars")
        
        return tutorial_data
        
    except TimeoutException:
        print(f"        ⚠️ Timeout loading tutorial page")
        return None
    except Exception as e:
        print(f"        ⚠️ Error extracting tutorial: {str(e)}")
        return None


def process_saved_tutorials(problems_dict, tutorial_folder="tutorial_pages_saved", 
                           output_file="code_solution_hints.json"):
    """
    Proceseaza paginile de tutorial deja salvate din folderul tutorial_pages_saved
    si actualizeaza JSON-ul cu Code, Solution si Hints.
    
    Args:
        problems_dict: Dictionarul cu probleme
        tutorial_folder: Folderul unde sunt salvate paginile HTML
        output_file: Fisierul JSON de output
    """
    results = {}
    processed = 0
    skipped = 0
    errors = 0
    
    # Incarcam rezultatele existente daca fisierul exista
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print(f"✓ Loaded {len(results)} existing results from {output_file}")
    
    print(f"\n{'='*60}")
    print(f"Processing saved tutorial pages from '{tutorial_folder}'")
    print(f"{'='*60}\n")
    
    # Iterez prin folderul cu pagini salvate
    if not os.path.exists(tutorial_folder):
        print(f"⚠️ Tutorial folder '{tutorial_folder}' not found!")
        return
    
    saved_files = [f for f in os.listdir(tutorial_folder) if f.endswith('.html')]
    print(f"Found {len(saved_files)} saved tutorial files\n")
    
    for html_file in saved_files:
        # Extraiem codul problemei din nume fisierului (format: tutorial_XXXXX.html)
        try:
            problem_code = html_file.replace('tutorial_', '').replace('.html', '')
        except:
            print(f"⚠️ Could not parse problem code from filename: {html_file}")
            continue
        
        # Verificam daca problema exista in dictionarul problemelor
        if problem_code not in problems_dict:
            print(f"⚠️ Problem code {problem_code} not found in problems list, skipping...")
            skipped += 1
            continue
        
        print(f"Processing {problem_code}: {problems_dict[problem_code]['name']}")
        
        # Daca deja am extras tutorial data pentru aceasta problema, skip
        if problem_code in results and results[problem_code].get('tutorial') is not None:
            print(f"    ✓ Already processed, skipping...")
            skipped += 1
            continue
        
        # Procesam pagina salvata
        html_file_path = os.path.join(tutorial_folder, html_file)
        tutorial_data = extract_tutorial_from_saved_html(html_file_path, problem_code)
        
        if tutorial_data:
            # Daca problema nu exista in results, o adaugam
            if problem_code not in results:
                results[problem_code] = {
                    'name': problems_dict[problem_code]['name'],
                    'link': problems_dict[problem_code]['link'],
                    'statement': None,
                    'tutorial': tutorial_data
                }
            else:
                # Actualizam tutorial data pentru problema existenta
                results[problem_code]['tutorial'] = tutorial_data
            
            processed += 1
            
            # Salvam progresul dupa fiecare problema procesata
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"    ✅ Updated {output_file} ({processed} completed)")
        else:
            print(f"    ❌ Failed to extract tutorial data")
            errors += 1
    
    print(f"\n{'='*60}")
    print(f"FINISHED PROCESSING SAVED TUTORIALS!")
    print(f"Total files: {len(saved_files)}")
    print(f"Successfully processed: {processed}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print(f"Output file: {output_file}")
    print(f"{'='*60}\n")


def process_all_problems(driver, problems_dict, output_file="code_solution_hints.json", 
                        min_delay=90, max_delay=240):
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
    print(f"IMPORTANT: Long delays (1.5-4 min) to avoid Cloudflare blocking!")
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
    print(f"FINISHED!")
    print(f"Total problems: {total}")
    print(f"Successfully processed: {processed}")
    print(f"Errors: {errors}")
    print(f"Output file: {output_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    try:
        # Configurare
        DEBUG_PORT = 9321
        CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        USER_DATA_DIR = "C:\\chrome_debug_temp"
        OUTPUT_FILE = "code_solution_hints.json"
        TUTORIAL_FOLDER = "tutorial_pages_saved"
        
        print("=" * 60)
        print("EXTRACTION OPTIONS:")
        print("=" * 60)
        print("1. Process SAVED tutorial pages (from tutorial_pages_saved/)")
        print("2. Process ALL problems with full web scraping (requires Chrome)")
        print("=" * 60)
        
        choice = input("\nSelect option (1 or 2): ").strip()
        
        # Extragem lista de probleme
        print("\nExtracting problems from problemset_page.html...")
        problems_dict = extract_problems_from_html("problemset_page.html")
        print(f"✓ Found {len(problems_dict)} problems")
        
        if choice == "1":
            # Procesam paginile tutorial salvate
            print("\n" + "=" * 60)
            print("OPTION 1: Processing saved tutorial pages")
            print("=" * 60)
            process_saved_tutorials(problems_dict, TUTORIAL_FOLDER, OUTPUT_FILE)
            
        elif choice == "2":
            # Procesam cu web scraping complet
            print("\n" + "=" * 60)
            print("OPTION 2: Full web scraping")
            print("=" * 60)
            
            driver = setup_driver(DEBUG_PORT)
            if not driver:
                print("\n❌ Please start Chrome with the command above and try again.")
                sys.exit(1)
            
            print("\nProcessing problems (extracting statements and tutorials)")
            print("Using VERY LONG delays (2-7 minutes) to avoid Cloudflare!")
            print("This will take a LONG time. Progress is saved after each problem.\n")
            
            # Procesam problemele
            process_all_problems(
                driver,
                problems_dict,
                output_file=OUTPUT_FILE,
                min_delay=90,    # 1.5 minute
                max_delay=240    # 4 minute
            )
            
            # Cleanup
            try:
                driver.quit()
            except:
                pass
        else:
            print("Invalid option. Exiting.")
            sys.exit(1)
        
        print("\n✅ Done! Results saved to " + OUTPUT_FILE)
    
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()

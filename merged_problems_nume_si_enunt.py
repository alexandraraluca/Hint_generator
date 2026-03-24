from bs4 import BeautifulSoup


def extract_problems_from_html(html_file="problemset_page.html"):
    """
    Extrage informatii despre probleme din fisierul HTML.
    
    Args:
        html_file: Calea catre fisierul HTML cu lista de submisii
    
    Returns:
        dict: Dictionar cu informatii despre probleme
              Format: {
                  'problem_code': {
                      'name': 'problem_name',
                      'link': '/problemset/problem/...'
                  }
              }
    """
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    
    problems = {}
    
    # Gasim toate link-urile catre probleme
    problem_links = soup.find_all("a", href=lambda href: href and "/problemset/problem/" in href)
    
    for link in problem_links:
        href = link.get("href")  # ex: /problemset/problem/2140/C
        problem_name = link.get_text(strip=True)  # ex: 2140C - Ultimate Value
        
        # Extragem codul problemei (ex: 2140C)
        if problem_name:
            problem_code = problem_name.split(" - ")[0] if " - " in problem_name else problem_name.split()[0]
            
            # Evitam duplicate
            if problem_code not in problems:
                problems[problem_code] = {
                    'name': problem_name,
                    'link': href
                }
    
    print(f"Found {len(problems)} unique problems")
    return problems


if __name__ == "__main__":
    # Test
    problems_dict = extract_problems_from_html("problemset_page.html")
    
    # Afisam primele 5 probleme pentru verificare
    print("\nPrimele 5 probleme:")
    for i, (code, info) in enumerate(list(problems_dict.items())[:5]):
        print(f"{code}: {info['name']} -> {info['link']}")

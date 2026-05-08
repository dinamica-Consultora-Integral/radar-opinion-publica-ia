import requests
from bs4 import BeautifulSoup

def buscar_noticias(palabra):
    resultados = []

    try:
        url = f"https://www.google.com/search?q={palabra}"
        
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        links = soup.find_all("a")

        for link in links:
            href = link.get("href")

            if href and "http" in href:
                resultados.append(href)

        return resultados[:20]

    except Exception as e:
        return [str(e)]

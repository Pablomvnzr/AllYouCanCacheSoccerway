from playwright.sync_api import sync_playwright

URL = "https://cl.soccerway.com/chile/liga-de-primera/tabla-de-posiciones/"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(3000)  # espera extra por si acaso
        html = page.content()
        with open("pagina_renderizada.html", "w", encoding="utf-8") as f:
            f.write(html)
        browser.close()
    print("HTML guardado en pagina_renderizada.html")

if __name__ == "__main__":
    main()

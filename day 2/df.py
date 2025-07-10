import os
import re
import time
import requests
import pandas as pd
from urllib.parse import urljoin
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    InvalidSessionIdException, WebDriverException, TimeoutException, NoSuchElementException)

# === CONFIGURATION ===
CHROMEDRIVER_PATH = r"C:\Users\zizou\OneDrive\Desktop\stage 3ème\day 2\chromedriver-win64\chromedriver.exe"
BASE_DIR = r"C:\Users\zizou\OneDrive\Desktop\stage 3ème\day 2"
PDF_DIR = os.path.join(BASE_DIR, "pdffiles")
CSV_DIR = os.path.join(BASE_DIR, "csvfiles")
DEBUG_DIR = os.path.join(BASE_DIR, "debug")
BASE_URL = "https://www.tunisieclearing.com/tc/fr/statistiques/historiquebulletin"
WAIT_TIMEOUT = 30

def setup_directories():
    os.makedirs(PDF_DIR, exist_ok=True)
    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(DEBUG_DIR, exist_ok=True)
    print("✅ Répertoires configurés")

def check_network():
    try:
        response = requests.head(BASE_URL, timeout=10)
        if response.status_code == 200:
            print("✅ Connexion réseau OK")
            return True
        print(f"⚠️ Échec de connexion: Statut {response.status_code}")
        return False
    except requests.RequestException as e:
        print(f"❌ Erreur réseau: {str(e)}")
        return False

def initialize_driver():
    print("🔍 Initialisation du navigateur...")
    options = Options()
    # options.add_argument("--headless=new")  # À activer si besoin
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.javascript": 1,
    })

    try:
        service = Service(executable_path=CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(10)
        print("✅ Navigateur initialisé avec succès")
        return driver
    except Exception as e:
        print(f"❌ Erreur d'initialisation du navigateur: {str(e)}")
        return None

def wait_for_page_ready(driver, timeout=30):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print("✅ Page complètement chargée")
        return True
    except TimeoutException:
        print("⚠️ Timeout lors du chargement de la page")
        return False

def scrape_bulletin_links():
    """Récupère les liens vers les bulletins PDF (année 2025 affichée par défaut)"""
    print("\n=== DÉBUT DU SCRAPING DES LIENS ===")

    if not check_network():
        return []

    driver = None
    bulletin_links = []

    try:
        driver = initialize_driver()
        if not driver:
            return []

        print(f"🌐 Chargement de la page: {BASE_URL}")
        driver.get(BASE_URL)

        if not wait_for_page_ready(driver):
            return []

        print("🔍 Recherche des onglets...")
        tabs = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//ul[contains(@class, 'nav-tabs') or contains(@class, 'nav')]//a")
            )
        )

        if len(tabs) < 2:
            print("⚠️ Moins de 2 onglets trouvés")
            return []

        tabs[1].click()
        print("✅ Deuxième onglet cliqué")
        time.sleep(5)

        print("🔍 Recherche des groupes de mois dans <accordion-group>...")
        accordion_groups = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_all_elements_located((By.XPATH, "//accordion-group"))
        )
        print(f"✅ {len(accordion_groups)} mois trouvés")

        for group in accordion_groups:
            try:
                header = group.find_element(By.XPATH, ".//div[contains(@class, 'panel-heading') or contains(@class, 'card-header')]")
                body = group.find_element(By.XPATH, ".//div[contains(@class, 'panel-collapse') or contains(@class, 'collapse')]")
                if "in" not in body.get_attribute("class") and "show" not in body.get_attribute("class"):
                    driver.execute_script("arguments[0].click();", header)
                    time.sleep(2)

                links = group.find_elements(By.XPATH, ".//a[contains(@href, '.pdf')]")
                for link in links:
                    pdf_url = urljoin(BASE_URL, link.get_attribute('href'))
                    filename = os.path.basename(pdf_url)
                    bulletin_links.append((pdf_url, filename))
                    print(f"📄 Lien trouvé: {filename}")

            except Exception as e:
                print(f"⚠️ Erreur dans un accordion-group : {str(e)}")
                continue

        print(f"✅ Total des PDF trouvés: {len(bulletin_links)}")
        return bulletin_links

    except Exception as e:
        print(f"❌ Erreur majeure lors du scraping: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()
            print("🛑 Navigateur fermé")

def download_pdf(url, filename):
    filepath = os.path.join(PDF_DIR, filename)
    if os.path.exists(filepath):
        print(f"✅ {filename} existe déjà")
        return filepath
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"📥 Téléchargé: {filename}")
        return filepath
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement de {filename}: {str(e)}")
        return None

def extraire_date(pdf_path):
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
        date_patterns = [
            r'Bulletin du (\d{2}/\d{2}/\d{4})',
            r'Journée du (\d{2}/\d{2}/\d{4})',
            r'Date : (\d{2}/\d{2}/\d{4})'
        ]
        found_dates = []
        for page in reader.pages:
            text = page.extract_text()
            if not text:
                continue
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    found_dates.append((match.group(1), pattern))

        for date, pattern in found_dates:
            if 'Bulletin du' in pattern:
                return date.replace('/', '-')
        if found_dates:
            return found_dates[0][0].replace('/', '-')

        try:
            metadata = reader.metadata
            if metadata and '/CreationDate' in metadata:
                creation_date = metadata['/CreationDate']
                match = re.search(r'D:(\d{4})(\d{2})(\d{2})', creation_date)
                if match:
                    year, month, day = match.groups()
                    return f"{day}-{month}-{year}"
        except:
            pass

        return "date_inconnue"

def extraire_tableaux(pdf_path, debut_section, fin_section):
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
        texte_complet = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                texte_complet += text + "\n"

        start_idx = texte_complet.find(debut_section)
        end_idx = texte_complet.find(fin_section)

        if start_idx == -1 or end_idx == -1:
            return []

        section_texte = texte_complet[start_idx + len(debut_section):end_idx]
        lignes = [ligne.strip() for ligne in section_texte.split('\n') if ligne.strip()]
        tableaux = []
        tableau_actuel = []
        for ligne in lignes:
            if re.match(r'^.*\s{2,}.*$', ligne):
                tableau_actuel.append(ligne)
            elif tableau_actuel:
                tableaux.append(tableau_actuel)
                tableau_actuel = []

        if tableau_actuel:
            tableaux.append(tableau_actuel)
        return tableaux

def convertir_en_dataframe(tableau):
    lignes_propres = []
    for ligne in tableau:
        ligne_propre = re.sub(r'\s{2,}', '|', ligne.strip())
        colonnes = ligne_propre.split('|')
        lignes_propres.append(colonnes)

    if len(lignes_propres) < 3:
        return None

    header = ["ISIN", "Libellé", "Nombre de Titres", "Montant", "Echéance", "Taux"]
    lignes_normalisees = []
    for ligne in lignes_propres[2:]:
        if len(ligne) < 6:
            ligne = ligne + [''] * (6 - len(ligne))
        elif len(ligne) > 6:
            ligne = ligne[:6]
        lignes_normalisees.append(ligne)

    if not lignes_normalisees:
        return None

    try:
        df = pd.DataFrame(lignes_normalisees, columns=header)
        return df
    except:
        return None

def traiter_pdf(pdf_path, output_dir):
    """Traite un PDF et exporte tous les tableaux dans un seul CSV"""
    try:
        date_bulletin = extraire_date(pdf_path)
        if date_bulletin == "date_inconnue":
            print(f"Date non trouvée dans {os.path.basename(pdf_path)}")
            return
        
        tableaux = extraire_tableaux(
            pdf_path,
            "Les opérations de Mise en Pension du jour",
            "Les opérations de Rétrocession des Pensions Livrées"
        )
        
        if not tableaux:
            print(f"Aucun tableau trouvé dans {os.path.basename(pdf_path)} entre les sections spécifiées")
            return
        
        # Fusionner tous les tableaux extraits dans un seul DataFrame
        dfs = []
        for i, tableau in enumerate(tableaux, 1):
            df = convertir_en_dataframe(tableau)
            if df is not None and not df.empty:
                dfs.append(df)
            else:
                print(f"Tableau {i} ignoré (format invalide)")
        
        if not dfs:
            print(f"Aucune donnée valide extraite de {os.path.basename(pdf_path)}")
            return
        
        df_total = pd.concat(dfs, ignore_index=True)
        
        date_dir = os.path.join(output_dir, date_bulletin)
        os.makedirs(date_dir, exist_ok=True)
        fichier_csv = os.path.join(date_dir, f"{date_bulletin}.csv")
        df_total.to_csv(fichier_csv, index=False, encoding='utf-8-sig', sep=';')
        print(f"📄 CSV exporté : {fichier_csv}")
        
    except Exception as e:
        print(f"Erreur lors du traitement de {os.path.basename(pdf_path)}: {str(e)}")

def main():
    print("=== DÉBUT DU PROGRAMME ===")
    setup_directories()
    bulletin_links = scrape_bulletin_links()
    if not bulletin_links:
        print("❌ Aucun lien trouvé")
        return
    downloaded_files = []
    seen = set()
    for url, filename in bulletin_links:
        if url in seen:
            continue
        seen.add(url)
        path = download_pdf(url, filename)
        if path:
            downloaded_files.append(path)

    for pdf_path in downloaded_files:
        print(f"\n=== Traitement de {os.path.basename(pdf_path)} ===")
        traiter_pdf(pdf_path, CSV_DIR)

    print("\n✅ TRAITEMENT TERMINÉ AVEC SUCCÈS")

if __name__ == "__main__":
    main()

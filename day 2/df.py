import os
import re
import time
import requests
import pandas as pd
import tabula
from urllib.parse import urljoin
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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
    """Extrait la date du bulletin depuis le PDF"""
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
        date_patterns = [
            r'Bulletin du (\d{2}/\d{2}/\d{4})',
            r'Journée du (\d{2}/\d{2}/\d{4})',
            r'Date : (\d{2}/\d{2}/\d{4})'
        ]
        
        # Recherche dans le texte des pages
        for page in reader.pages:
            text = page.extract_text()
            if not text:
                continue
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1).replace('/', '-')
        
        # Recherche dans les métadonnées si pas trouvé dans le texte
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

def extraire_et_nettoyer_tableaux(pdf_path):
    """
    Extrait uniquement le tableau du PDF avec exactement 6 colonnes et conserve les données telles quelles
    Args:
        pdf_path (str): Chemin vers le fichier PDF
    Returns:
        pd.DataFrame: DataFrame contenant uniquement le tableau avec 6 colonnes
    """
    try:
        # 1. Extraction avec Tabula
        dfs = tabula.read_pdf(
            pdf_path,
            pages='all',
            guess=True,
            multiple_tables=True,
            stream=True,
            lattice=False,
            pandas_options={'header': None, 'dtype': str},
            silent=True
        )

        if not dfs:
            print(f"⚠️ Aucun tableau extrait de {os.path.basename(pdf_path)}")
            return pd.DataFrame()

        # 2. Sélectionner uniquement les tableaux avec exactement 6 colonnes
        valid_dfs = [df for df in dfs if len(df.columns) == 6]
        if not valid_dfs:
            print(f"⚠️ Aucun tableau avec exactement 6 colonnes dans {os.path.basename(pdf_path)}")
            return pd.DataFrame()

        # 3. Fusion des tableaux valides
        df = pd.concat(valid_dfs, ignore_index=True)

        # 4. Nettoyage initial
        df = df.dropna(how='all')

        # 5. Supprimer les lignes avec des en-têtes ou du texte non désiré
        mask = df[0].str.contains(
            r'tunisieclearing|Bulletin|Journée|Montant Pension|Dépositaire Central|ISIN Libelle|Total',
            case=False, na=False
        )
        df = df[~mask]

        # 6. Filtrer les lignes avec un ISIN valide
        isin_pattern = r'^(TN[A-Z0-9]{10,12}|\d{8,12}|H\d+)$'
        df = df[df[0].str.match(isin_pattern, na=False)]

        # 7. Vérifier à nouveau le nombre de colonnes
        if len(df.columns) != 6:
            print(f"⚠️ Format de tableau incorrect après filtrage dans {os.path.basename(pdf_path)}: {len(df.columns)} colonnes")
            return pd.DataFrame()

        # 8. Nommer les colonnes
        df.columns = ["ISIN", "Libellé", "Nombre de Titres", "Montant", "Echéance", "Taux"]

        # 9. Nettoyer les colonnes numériques, en préservant le format du PDF
        num_cols = ["Nombre de Titres", "Montant", "Echéance", "Taux"]
        for col in num_cols:
            if col in df.columns:
                # Supprimer les espaces, garder les virgules pour correspondre au format PDF
                df[col] = df[col].str.replace(r'\s+', '', regex=True)
                # Convertir en numérique pour validation, mais conserver la chaîne pour l'output
                df[col] = df[col].str.replace(',', '.').apply(lambda x: pd.to_numeric(x, errors='coerce')).astype(str).str.replace('.', ',', regex=False)

        # 10. Nettoyer la colonne Libellé
        df["Libellé"] = df["Libellé"].str.replace(r'\s+', ' ', regex=True).str.strip()

        # 11. Filtrer les lignes avec des données valides dans toutes les colonnes
        df = df.dropna(subset=["ISIN", "Libellé", "Nombre de Titres", "Montant", "Echéance", "Taux"])

        # 12. Supprimer les doublons exacts
        df = df.drop_duplicates()

        # 13. Debugging: sauvegarder les données brutes pour inspection
        debug_path = os.path.join(DEBUG_DIR, f"raw_{os.path.basename(pdf_path)}.csv")
        df.to_csv(debug_path, index=False, sep=';', encoding='utf-8-sig')
        print(f"📄 Données brutes enregistrées dans {debug_path}")

        # 14. Debugging: signaler le nombre de lignes
        if df.empty:
            print(f"⚠️ Aucune donnée valide après nettoyage pour {os.path.basename(pdf_path)}")
        else:
            print(f"✅ {len(df)} lignes valides extraites de {os.path.basename(pdf_path)}")

        return df

    except Exception as e:
        print(f"❌ Erreur lors du traitement {pdf_path}: {str(e)}")
        return pd.DataFrame()

def traiter_pdf(pdf_path, output_dir):
    """Traite un PDF et exporte les données nettoyées en CSV"""
    try:
        date_bulletin = extraire_date(pdf_path)
        if date_bulletin == "date_inconnue":
            print(f"⚠️ Date non trouvée dans {os.path.basename(pdf_path)}")
            date_bulletin = os.path.basename(pdf_path).split('.')[0]
        
        print(f"🔍 Extraction des données depuis {os.path.basename(pdf_path)}...")
        df = extraire_et_nettoyer_tableaux(pdf_path)
        
        if df.empty:
            print(f"⚠️ Aucune donnée valide dans {os.path.basename(pdf_path)}")
            return
        
        # Création du répertoire de sortie
        date_dir = os.path.join(output_dir, date_bulletin)
        os.makedirs(date_dir, exist_ok=True)
        
        # Export CSV
        csv_path = os.path.join(date_dir, f"{date_bulletin}.csv")
        df.to_csv(csv_path, index=False, sep=';', encoding='utf-8-sig')
        print(f"✅ Données exportées vers {csv_path} ({len(df)} lignes)")
        
    except Exception as e:
        print(f"❌ Erreur critique lors du traitement de {pdf_path}: {str(e)}")

def main():
    print("=== DÉBUT DU PROGRAMME ===")
    setup_directories()
    
    # Étape 1: Scraping des liens PDF
    bulletin_links = scrape_bulletin_links()
    if not bulletin_links:
        print("❌ Aucun lien trouvé, arrêt du programme")
        return
    
    # Étape 2: Téléchargement des PDF
    print("\n=== TÉLÉCHARGEMENT DES PDF ===")
    downloaded_files = []
    seen_urls = set()
    
    for url, filename in bulletin_links:
        if url in seen_urls:
            continue
        seen_urls.add(url)
        filepath = download_pdf(url, filename)
        if filepath:
            downloaded_files.append(filepath)
    
    # Étape 3: Traitement des PDF
    print("\n=== TRAITEMENT DES PDF ===")
    for pdf_path in downloaded_files:
        traiter_pdf(pdf_path, CSV_DIR)
    
    print("\n✅ TRAITEMENT TERMINÉ AVEC SUCCÈS")

if __name__ == "__main__":
    main()
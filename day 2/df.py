# === BIBLIOTHÈQUES ===
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
CHROMEDRIVER_PATH = r"C:\\Users\\zizou\\OneDrive\\Desktop\\stage 3ème\\day 2\\chromedriver-win64\\chromedriver.exe"
BASE_DIR = r"C:\\Users\\zizou\\OneDrive\\Desktop\\stage 3ème\\day 2"
PDF_DIR = os.path.join(BASE_DIR, "pdffiles")
CSV_DIR = os.path.join(BASE_DIR, "csvfiles")
DEBUG_DIR = os.path.join(BASE_DIR, "debug")
BASE_URL = "https://www.tunisieclearing.com/tc/fr/statistiques/historiquebulletin"
WAIT_TIMEOUT = 30

# === FONCTIONS ===

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
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)...")
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
    print("\n=== DÉBUT DU SCRAPING DES LIENS ===")
    if not check_network():
        return []

    driver = None
    bulletin_links = []

    try:
        driver = initialize_driver()
        if not driver:
            return []

        driver.get(BASE_URL)

        if not wait_for_page_ready(driver):
            return []

        tabs = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//ul[contains(@class, 'nav-tabs') or contains(@class, 'nav')]//a")
            )
        )

        if len(tabs) < 2:
            return []

        tabs[1].click()
        time.sleep(5)

        accordion_groups = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_all_elements_located((By.XPATH, "//accordion-group"))
        )

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

            except Exception:
                continue

        return bulletin_links

    except Exception as e:
        print(f"❌ Erreur majeure lors du scraping: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()

def download_pdf(url, filename):
    filepath = os.path.join(PDF_DIR, filename)
    if os.path.exists(filepath):
        return filepath
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
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
        for page in reader.pages:
            text = page.extract_text()
            if not text:
                continue
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    return match.group(1).replace('/', '-')
        try:
            metadata = reader.metadata
            if metadata and '/CreationDate' in metadata:
                match = re.search(r'D:(\d{4})(\d{2})(\d{2})', metadata['/CreationDate'])
                if match:
                    y, m, d = match.groups()
                    return f"{d}-{m}-{y}"
        except:
            pass
        return "date_inconnue"

def format_francais(val, decimales=3):
    if pd.isna(val):
        return val
    # Format sans séparateur de milliers, avec x décimales
    s = f"{val:.{decimales}f}"
    # Remplacer le point décimal par une virgule
    s = s.replace('.', ',')
    # Insérer espaces comme séparateur de milliers (groupe de 3 chiffres avant la virgule)
    # Regex : insère un espace entre groupes de 3 chiffres en partant de la droite (avant la virgule)
    import re
    parts = s.split(',')
    parts[0] = re.sub(r"(?<!^)(?=(\d{3})+$)", " ", parts[0])
    return ','.join(parts)


def extraire_et_nettoyer_tableaux(pdf_path):
    import re

    def format_francais(val, decimales=3):
        if pd.isna(val):
            return val
        s = f"{val:.{decimales}f}"
        s = s.replace('.', ',')
        parts = s.split(',')
        parts[0] = re.sub(r"(?<!^)(?=(\d{3})+$)", " ", parts[0])
        return ','.join(parts)

    try:
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
            return pd.DataFrame()

        all_rows = []
        isin_pattern = r'^(TN[A-Z0-9]{10,12}|\d{8,12}|H\d+)$'

        for df in dfs:
            if df.shape[1] != 6:
                continue
            for _, row in df.iterrows():
                row = row.fillna("").astype(str).str.strip()
                all_rows.append(row.tolist())

        cleaned_rows = []
        skip_next = False

        for i in range(len(all_rows)):
            if skip_next:
                skip_next = False
                continue

            current = all_rows[i]

            if re.match(isin_pattern, current[0]):
                cleaned_rows.append(current)
                continue

            if i + 1 < len(all_rows):
                next_row = all_rows[i + 1]
                fusion = current.copy()
                fusion[0] = (current[0] + next_row[0]).strip()
                for j in range(1, 6):
                    fusion[j] = current[j] if current[j] else next_row[j]
                if re.match(isin_pattern, fusion[0]):
                    cleaned_rows.append(fusion)
                    skip_next = True
                    continue

            cleaned_rows.append(current)

        df = pd.DataFrame(cleaned_rows)
        if df.shape[1] != 6:
            return pd.DataFrame()

        df.columns = ["ISIN", "Libellé", "Nombre de Titres", "Montant", "Echéance", "Taux"]

        # Nettoyage & conversion des colonnes numériques
        num_cols = ["Nombre de Titres", "Montant", "Echéance", "Taux"]
        for col in num_cols:
            df[col] = df[col].str.replace(r'\s+', '', regex=True)
            df[col] = df[col].str.replace(',', '.')
            df[col] = df[col].apply(lambda x: pd.to_numeric(x, errors='coerce'))

        # Formatage des colonnes selon le format français
        df["Nombre de Titres"] = df["Nombre de Titres"].apply(
            lambda x: format_francais(x, decimales=0) if pd.notna(x) else x)

        df["Montant"] = df["Montant"].apply(
            lambda x: format_francais(x, decimales=3) if pd.notna(x) else x)

        df["Echéance"] = df["Echéance"].apply(
            lambda x: format_francais(x, decimales=0) if pd.notna(x) else x)

        df["Taux"] = df["Taux"].apply(
            lambda x: format_francais(x, decimales=3) if pd.notna(x) else x)

        df["Libellé"] = df["Libellé"].str.replace(r'\s+', ' ', regex=True).str.strip()

        debug_path = os.path.join(DEBUG_DIR, f"raw_{os.path.basename(pdf_path)}.csv")
        df.to_csv(debug_path, index=False, sep=';', encoding='utf-8-sig')

        return df

    except Exception as e:
        print(f"❌ Erreur lors du traitement {pdf_path}: {str(e)}")
        return pd.DataFrame()

def traiter_pdf(pdf_path, output_dir):
    try:
        date_bulletin = extraire_date(pdf_path)
        if date_bulletin == "date_inconnue":
            date_bulletin = os.path.basename(pdf_path).split('.')[0]

        df = extraire_et_nettoyer_tableaux(pdf_path)

        if df.empty:
            return

        mask = (df.iloc[:, 0] == "ISIN") & (df.iloc[:, 1] == "Libelle") & (df.iloc[:, 2:].isna().all(axis=1))
        df = df[~mask].reset_index(drop=True)

        date_dir = os.path.join(output_dir, date_bulletin)
        os.makedirs(date_dir, exist_ok=True)

        csv_path = os.path.join(date_dir, f"{date_bulletin}.csv")
        df.to_csv(csv_path, index=False, sep=';', encoding='utf-8-sig')
        print(f"✅ Données exportées vers {csv_path} ({len(df)} lignes)")

    except Exception as e:
        print(f"❌ Erreur critique lors du traitement de {pdf_path}: {str(e)}")

def creer_dataframe_finale(csv_root_dir, nom_fichier_final="dataframefinale.csv"):
    print("\n=== CRÉATION DE LA DATAFRAME FINALE ===")
    toutes_les_donnees = []

    for root, _, files in os.walk(csv_root_dir):
        for file in files:
            if file.endswith(".csv") and file != nom_fichier_final:
                chemin_csv = os.path.join(root, file)
                try:
                    df = pd.read_csv(chemin_csv, sep=';', encoding='utf-8-sig')

                    # ➕ Extraire la date depuis le nom du dossier
                    dossier_date = os.path.basename(root)
                    match = re.match(r"(\d{2})-(\d{2})-(\d{4})", dossier_date)
                    if match:
                        dateloading = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                    else:
                        dateloading = "date_inconnue"

                    df.insert(0, "dataloadingdate", dateloading)
                    toutes_les_donnees.append(df)
                except Exception as e:
                    print(f"⚠️ Erreur lors de la lecture de {chemin_csv} : {e}")

    # ➕ Ajouter les données Excel (hors 2025)
    try:
        excel_path = r"C:\Users\zizou\OneDrive\Desktop\stage 3ème\day 5\pl.xlsx"
        df_excel = pd.read_excel(excel_path)

        df_excel = df_excel.drop(columns=[col for col in ['ID', 'SAVEDDATE'] if col in df_excel.columns])

        df_excel = df_excel.rename(columns={
            "LIBELLE": "Libellé",
            "NBTITRES": "Nombre de Titres",
            "MONTANT": "Montant",
            "ECHEANCE": "Echéance",
            "TAUX": "Taux",
            "ISIN": "ISIN",
            "DATALOADINGDATE": "dataloadingdate"
        })

        df_excel['dataloadingdate'] = pd.to_datetime(df_excel['dataloadingdate'], dayfirst=True, errors='coerce')
        df_excel = df_excel[df_excel['dataloadingdate'].dt.year != 2025]

        if toutes_les_donnees:
            colonnes_finales = toutes_les_donnees[0].columns
            df_excel = df_excel[colonnes_finales]

        toutes_les_donnees.append(df_excel)
        print("✅ Données Excel intégrées (hors 2025)")
    except Exception as e:
        print(f"⚠️ Erreur chargement Excel pl.xlsx : {e}")

    if toutes_les_donnees:
        dataframefinale = pd.concat(toutes_les_donnees, ignore_index=True)

        # Nettoyage général des colonnes numériques
        for col in ["Nombre de Titres", "Montant", "Echéance", "Taux"]:
            if col in dataframefinale.columns:
                dataframefinale[col] = dataframefinale[col].astype(str)
                dataframefinale[col] = dataframefinale[col].str.replace('"', '', regex=False)  # enlever les ""
                dataframefinale[col] = dataframefinale[col].str.replace(' ', '', regex=False)  # enlever les espaces
                dataframefinale[col] = dataframefinale[col].str.replace(',', '.', regex=False)  # , → .
                dataframefinale[col] = pd.to_numeric(dataframefinale[col], errors='coerce')

        # Supprimer les lignes incomplètes
        dataframefinale = dataframefinale.dropna()

        # Filtrer échéance ≤ 399
        if "Echéance" in dataframefinale.columns:
            dataframefinale = dataframefinale[dataframefinale["Echéance"] <= 399]

        # Reformater la date
        dataframefinale['dataloadingdate'] = pd.to_datetime(dataframefinale['dataloadingdate'], dayfirst=True, errors='coerce')
        dataframefinale['dataloadingdate'] = dataframefinale['dataloadingdate'].dt.strftime('%d/%m/%Y')

        chemin_final = os.path.join(csv_root_dir, nom_fichier_final)
        dataframefinale.to_csv(chemin_final, index=False, sep=';', encoding='utf-8-sig')

        print(f"✅ Dataframe finale enregistrée dans : {chemin_final} ({len(dataframefinale)} lignes)")
    else:
        print("❌ Aucune donnée trouvée pour créer la dataframe finale.")


def main():
    print("=== DÉBUT DU PROGRAMME ===")
    setup_directories()
    bulletin_links = scrape_bulletin_links()
    if not bulletin_links:
        print("❌ Aucun lien trouvé")
        return

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

    print("\n=== TRAITEMENT DES PDF ===")
    for pdf_path in downloaded_files:
        traiter_pdf(pdf_path, CSV_DIR)

    print("\n✅ TRAITEMENT TERMINÉ AVEC SUCCÈS")

    # Création de la dataframe finale
    creer_dataframe_finale(CSV_DIR)

if __name__ == "__main__":
    main()
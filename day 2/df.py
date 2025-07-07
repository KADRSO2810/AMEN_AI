import os
import re
import pandas as pd
from PyPDF2 import PdfReader

def extraire_date(pdf_path):
    """Extrait la date du bulletin depuis toutes les pages du PDF"""
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
        date_patterns = [
            r'Bulletin du (\d{2}/\d{2}/\d{4})',  # Priorité à 'Bulletin du'
            r'Journée du (\d{2}/\d{2}/\d{4})',
            r'Date : (\d{2}/\d{2}/\d{4})'
        ]
        
        # Recherche dans toutes les pages
        found_dates = []
        for page in reader.pages:
            text = page.extract_text()
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    found_dates.append((match.group(1), pattern))
        
        # Debugging: Afficher toutes les dates trouvées
        print(f"Dates trouvées dans {os.path.basename(pdf_path)} : {found_dates}")
        
        # Prioriser la première date correspondant à 'Bulletin du'
        for date, pattern in found_dates:
            if 'Bulletin du' in pattern:
                return date.replace('/', '-')
        
        # Sinon, prendre la première date trouvée
        if found_dates:
            return found_dates[0][0].replace('/', '-')
        
        # Fallback: Utiliser la date de création du PDF si disponible
        try:
            metadata = reader.metadata
            if metadata and '/CreationDate' in metadata:
                creation_date = metadata['/CreationDate']
                # Format PDF: D:YYYYMMDDHHMMSS
                match = re.search(r'D:(\d{4})(\d{2})(\d{2})', creation_date)
                if match:
                    year, month, day = match.groups()
                    return f"{day}-{month}-{year}"
        except Exception as e:
            print(f"Erreur lors de l'extraction de la date de création : {str(e)}")
        
        return "date_inconnue"

def extraire_tableaux(pdf_path, debut_section, fin_section):
    """Extrait les tableaux entre deux sections spécifiques"""
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
        texte_complet = ""
        
        # Concaténer le texte de toutes les pages
        for page in reader.pages:
            texte_complet += page.extract_text() + "\n"
        
        # Trouver les positions des sections
        start_idx = texte_complet.find(debut_section)
        end_idx = texte_complet.find(fin_section)
        
        if start_idx == -1 or end_idx == -1:
            return []
        
        # Extraire le texte entre les sections
        section_texte = texte_complet[start_idx + len(debut_section):end_idx]
        
        # Détection des tableaux (basée sur les lignes avec plusieurs colonnes)
        lignes = [ligne.strip() for ligne in section_texte.split('\n') if ligne.strip()]
        tableaux = []
        tableau_actuel = []
        
        for ligne in lignes:
            # Si la ligne contient au moins 2 séparations par plusieurs espaces
            if re.match(r'^.*\s{2,}.*$', ligne):
                tableau_actuel.append(ligne)
            elif tableau_actuel:
                tableaux.append(tableau_actuel)
                tableau_actuel = []
        
        if tableau_actuel:
            tableaux.append(tableau_actuel)
        
        return tableaux

def convertir_en_dataframe(tableau):
    """Convertit un tableau texte en DataFrame"""
    lignes_propres = []
    for ligne in tableau:
        # Nettoyage des espaces multiples et split
        ligne_propre = re.sub(r'\s{2,}', '|', ligne.strip())
        colonnes = ligne_propre.split('|')
        lignes_propres.append(colonnes)
    
    if len(lignes_propres) < 3:  # Besoin d'au moins une ligne de données après exclusion de ligne 0 et 1
        print("Tableau trop court après exclusion des lignes 0 et 1, ignoré.")
        return None
    
    # Debugging: Afficher toutes les lignes propres pour inspection
    print("Lignes propres extraites :")
    for i, ligne in enumerate(lignes_propres):
        print(f"Ligne {i}: {ligne} ({len(ligne)} colonnes)")
    
    # Définir les en-têtes manuellement (6 colonnes)
    header = ["ISIN", "Libellé", "Nombre de Titres", "Montant", "Echéance", "Taux"]
    
    # Normaliser les lignes de données (exclure ligne 0 et ligne 1)
    lignes_normalisees = []
    for ligne in lignes_propres[2:]:  # Commencer à partir de la ligne 2
        # Normaliser à 6 colonnes
        if len(ligne) < 6:
            ligne = ligne + [''] * (6 - len(ligne))  # Compléter avec des chaînes vides
        elif len(ligne) > 6:
            ligne = ligne[:6]  # Tronquer les colonnes supplémentaires
        lignes_normalisees.append(ligne)
    
    if not lignes_normalisees:
        print("Aucune donnée valide après exclusion des lignes 0 et 1.")
        return None
    
    try:
        # Créer le DataFrame
        df = pd.DataFrame(lignes_normalisees, columns=header)
        print(f"DataFrame créé avec {len(df)} lignes et colonnes : {df.columns.tolist()}")
        return df
    except Exception as e:
        print(f"Erreur lors de la création du DataFrame : {str(e)}")
        return None

def traiter_pdf(pdf_path, output_dir):
    """Traite un PDF et exporte les tableaux en CSV"""
    try:
        # Extraire la date pour le nommage
        date_bulletin = extraire_date(pdf_path)
        if date_bulletin == "date_inconnue":
            print(f"Date non trouvée dans {os.path.basename(pdf_path)}")
            return
        
        # Extraire les tableaux entre les sections spécifiques
        tableaux = extraire_tableaux(
            pdf_path,
            "Les opérations de Mise en Pension du jour",
            "Les opérations de Rétrocession des Pensions Livrées"
        )
        
        if not tableaux:
            print(f"Aucun tableau trouvé dans {os.path.basename(pdf_path)} entre les sections spécifiées")
            return
        
        # Créer un dossier par date si nécessaire
        date_dir = os.path.join(output_dir, date_bulletin)
        os.makedirs(date_dir, exist_ok=True)
        
        # Convertir et exporter chaque tableau
        for i, tableau in enumerate(tableaux, 1):
            df = convertir_en_dataframe(tableau)
            if df is not None and not df.empty:
                csv_path = os.path.join(date_dir, f"{date_bulletin}_tableau_{i}.csv")
                df.to_csv(csv_path, index=False, encoding='utf-8-sig', sep=';')
                print(f"Tableau {i} exporté dans {csv_path}")
            else:
                print(f"Tableau {i} ignoré (format invalide)")
                
    except Exception as e:
        print(f"Erreur lors du traitement de {os.path.basename(pdf_path)}: {str(e)}")

# Configuration des chemins
dossier_pdf = r"C:\Users\zizou\OneDrive\Desktop\stage 3ème\day 2\pdffiles"
dossier_csv = r"C:\Users\zizou\OneDrive\Desktop\stage 3ème\day 2\csvfiles"

# Vérification des dossiers
if not os.path.exists(dossier_pdf):
    print(f"Erreur: Le dossier PDF {dossier_pdf} n'existe pas")
    exit()

if not os.path.exists(dossier_csv):
    os.makedirs(dossier_csv)

# Traitement de tous les fichiers PDF
for fichier in os.listdir(dossier_pdf):
    if fichier.lower().endswith('.pdf'):
        pdf_path = os.path.join(dossier_pdf, fichier)
        traiter_pdf(pdf_path, dossier_csv)
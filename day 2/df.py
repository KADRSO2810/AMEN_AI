import os
import pandas as pd
import fitz  # PyMuPDF
from datetime import datetime
import re
import glob

def find_pension_page(doc):
    """Trouve la page contenant la table de pension livrée"""
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if "Pension Livrée" in text and "Les opérations du jour" in text:
            return page_num
    return None

def extract_pension_table(page):
    """Extrait la table de pension de la page spécifique"""
    tabs = page.find_tables()
    if not tabs:
        return None
    
    for table in tabs:
        data = table.extract()
        
        if len(data) > 1 and len(data[0]) >= 4:
            headers = [str(h).strip().lower() for h in data[0]]
            expected = ['isin', 'libellé', 'montant', 'taux']
            if sum(1 for e in expected if any(e in h for h in headers)) >= 3:
                return data
    
    return None

def clean_data(table_data):
    """Nettoie et structure les données extraites"""
    headers = [str(h).strip() for h in table_data[0]]
    rows = table_data[1:]
    
    df = pd.DataFrame(rows, columns=headers)
    
    col_mapping = {
        'isin': 'ISIN',
        'libellé': 'Libellé',
        'nombre de titres': 'Nombre de Titres',
        'montant': 'Montant',
        'échéance': 'Échéance',
        'taux': 'Taux'
    }
    
    for col in df.columns:
        col_lower = col.lower()
        for target, replacement in col_mapping.items():
            if target in col_lower:
                df = df.rename(columns={col: replacement})
                break
    
    df = df.dropna(how='all')
    df = df[~df.iloc[:, 0].str.contains('Les opérations|Montant Global', na=False)]
    
    return df

def process_single_pdf(pdf_path, output_folder):
    """Traite un seul fichier PDF"""
    try:
        print(f"\nTraitement du fichier: {os.path.basename(pdf_path)}")
        doc = fitz.open(pdf_path)
        
        page_num = find_pension_page(doc)
        if page_num is None:
            print("Page contenant la table de pension non trouvée")
            return None
        
        table_data = extract_pension_table(doc[page_num])
        if table_data is None:
            print("Table de pension non trouvée sur la page")
            return None
        
        df = clean_data(table_data)
        
        if df is not None and not df.empty:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_path = os.path.join(output_folder, f"pension_livree_{pdf_name}_{timestamp}.csv")
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            print("Extraction réussie!")
            print(f"Fichier sauvegardé: {output_path}")
            print("\nAperçu des données:")
            print(df.head())
            return output_path
        
        print("Échec de l'extraction - aucune donnée valide trouvée")
        return None
    
    except Exception as e:
        print(f"Erreur lors du traitement du fichier: {str(e)[:200]}")
        return None

def batch_process_pdfs(input_folder, output_folder):
    """Traite tous les PDFs dans un dossier"""
    os.makedirs(output_folder, exist_ok=True)
    pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))
    
    if not pdf_files:
        print(f"Aucun fichier PDF trouvé dans: {input_folder}")
        return []
    
    results = []
    for pdf_file in pdf_files:
        result = process_single_pdf(pdf_file, output_folder)
        if result:
            results.append(result)
    
    return results

def main():
    # Configuration (peut être modifiée pour utiliser argparse)
    INPUT_FOLDER = "C:/Users/zizou/OneDrive/Desktop/stage 3ème/day 2/pdffiles/"
    OUTPUT_FOLDER = "C:/Users/zizou/OneDrive/Desktop/stage 3ème/day 2/csvfiles/"
    
    # Traitement par lot
    print(f"Début du traitement des PDFs dans {INPUT_FOLDER}")
    processed_files = batch_process_pdfs(INPUT_FOLDER, OUTPUT_FOLDER)
    
    # Résumé
    print("\nRésumé du traitement:")
    print(f"Nombre de fichiers PDF trouvés: {len(glob.glob(os.path.join(INPUT_FOLDER, '*.pdf')))}")
    print(f"Nombre de fichiers traités avec succès: {len(processed_files)}")
    print(f"Fichiers CSV générés dans: {OUTPUT_FOLDER}")

if __name__ == "__main__":
    main()
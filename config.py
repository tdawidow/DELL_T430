# config.py
import os
import multiprocessing

def get_system_ram_gb() -> int:
    """Natywnie pobiera całkowitą pamięć RAM w systemie Linux/Lubuntu."""
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if 'MemTotal' in line:
                    kb_val = int(line.split()[1])
                    gb_val = int(kb_val / (1024 * 1024))
                    
                    # Jeśli wynik jest nieparzysty, zaokrągla w dół do parzystej
                    if gb_val % 2 != 0:
                        gb_val -= 1
                        
                    return gb_val
    except Exception:
        pass
    return 16  # Bezpieczna wartość domyślna (parzysta)

# --- DYNAMICZNE BADANIE ZASOBÓW SPRZĘTOWYCH WERSJA MULTI-CPU ---
TOTAL_SYSTEM_RAM_GB = get_system_ram_gb()

# ✅ KOREKTA SPRZĘTOWA: Rezerwujemy bezwarunkowo 8 GB RAM (po 4 GB na każdy procesor Xeon) dla OS i Chromium
MAX_RAM_ALLOCATION_GB = max(TOTAL_SYSTEM_RAM_GB - 8, 8)  

TOTAL_SYSTEM_CORES = multiprocessing.cpu_count()

# ✅ KOREKTA OBLICZENIOWA: Bezwarunkowo zostawiamy 2 rdzenie CPU wolne dla pełnej płynności Lubuntu
MAX_THREADS_ALLOCATION = max(TOTAL_SYSTEM_CORES - 2, 2)  

# --- DOMYŚLNE ŚCIEŻKI INICJALIZACYJNE (UŻYWANE PRZY PIERWSZYM STARCIE) ---
DEFAULT_APP_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_CONFIG_FILE = os.path.join(DEFAULT_APP_DIR, ".kombajn_master_config.json")

# Te zmienne będą dynamicznie nadpisywane przez dane wczytane z konfiguratora GUI
BASE_DATA_DIR = ""
OUTPUT_DIR = ""
LIBRARY_DIR = ""
LIBRARY_INDEX_FILE = ""
DEFAULT_KRAKEN_DB = ""
BACKUP_DIR = ""  
CURRENT_THREADS_LIMIT = MAX_THREADS_ALLOCATION

KRAKEN_NOISE_THRESHOLD = 0.1  # Stały próg odcięcia szumu metagenomiki (0.1%)

# =====================================================================
# 🚨 NIENARUSZALNA BAZA PRAWDY: STAŁE GLOBALNE PARAMETRÓW SIECIOWYCH NCBI
# =====================================================================
NCBI_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# ✅ SZABLON ADRESU URL: Bezpieczna domena eutils i znacznik {} oczekujący na dynamiczne wstrzyknięcie tokenu
NCBI_EUTILS_TEMPLATE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={}&rettype=fasta&retmode=text"

# Globalna zmienna robocza jądra aplikacji, zasilana przy starcie systemu z pliku JSON
NCBI_API_KEY = ""

# =====================================================================
# 🚨 PARAMETRY INTEGRACJI SIECIOWEJ PRODUKCYJNEGO TORRENT SERVERA
# =====================================================================
TORRENT_SERVER_URL = ""  # Wartość wymagająca ustawienia przy pierwszym rozruchu
TORRENT_SERVER_USER = "ionadmin"
TORRENT_SERVER_PASS = ""                     # Zmienna robocza zasilana dynamicznie z pliku JSON

# ✅ KOREKTA LABORATORYJNA: Dedykowany, sztywny katalog pobrań dla maszyn Ion Torrent
TORRENT_DOWNLOAD_DIR = ""  # Zabezpieczenie przed wolną amerykanką i błędami AttributeError

# esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
# esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
# ncbi_eutils_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={accession}&rettype=fasta&retmode=text"
# NCBI_EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={}&rettype=fasta&retmode=text"
# ✅ SZABLON ADRESU URL: Bezpieczna domena eutils i znacznik {} oczekujący na dynamiczne wstrzyknięcie tokenu
# NCBI_EUTILS_TEMPLATE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={}&rettype=fasta&retmode=text"

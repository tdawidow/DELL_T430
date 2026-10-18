# main.py
import sys
import os

# 🛡️ PANCERNA NEUTRALNOŚĆ SPRZĘTOWA CHROMIUM (STANDARD SPECJALISTYCZNY SERWEROWY):
# Wymusza na wbudowanym Chromium renderowanie czysto procesorowe (CPU Soft-Raster),
# eliminując krasze OpenGL i glitche w QWebEngineView na dowolnej karcie (RTX/Radeon/Matrox).
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-software-rasterizer --headless=new" if os.environ.get("HEADLESS") else "--disable-gpu --disable-software-rasterizer"
os.environ["QTWEBENGINE_DISABLE_GPU"] = "1"
os.environ["WEBENGINE_VISIBILITY_FIX"] = "1"

# Jowner wymuszenie na systemie Linux dodania bieżącego folderu do ścieżek Pythona
current_dir = os.path.dirname(os.path.abspath(__file__))

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Teraz importy wykonają się bezbłędnie na każdym komputerze i w każdym folderze
from gui.main_window import KombajnMainWindow
from PyQt6.QtWidgets import QApplication

def main():
    """Główny punkt startowy aplikacji 'Kombajn T430' dla środowiska Lubuntu."""
    # 1. Inicjalizacja aplikacji Qt
    app = QApplication(sys.argv)
    
    # 2. Inicjalizacja i wyświetlenie okna głównego z ciemnym motywem
    window = KombajnMainWindow()
    window.show()
    
    # 3. Bezpieczne zamknięcie pętli zdarzeń okna
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

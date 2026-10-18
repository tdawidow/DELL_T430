# core/explorer.py
import os
from enum import Enum, auto
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTreeView, 
                             QPushButton, QLabel, QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt, QDir, QSize, QModelIndex
from PyQt6.QtGui import QFileSystemModel, QKeyEvent
import config

class ExplorerMode(Enum):
    """Definiuje dwa fundamentalne tryby pracy wbudowanego eksploratora jądra."""
    FILE_SELECT = auto()
    DIRECTORY_SELECT = auto()

class FilterProfile:
    """
    Zbiór zunifikowanych profili maskowania rozszerzeń dla platform bioinformatycznych.
    Zapewnia zgodność z zasadą SOLID Open-Closed. Rozszerzony o standardy NCBI [2.4].
    """
    RAW_DATA = ["*.fastq", "*.fastq.gz", "*.bam", "*.pod5"]
    ARCHIVE_DATA = ["*.tar.gz", "*.gz", "*.zip"]
    # ✅ ROZSZERZENIE STANDARDU NCBI: Dołożenie .fn, .fna, .faa bez otwierania na szum globalny [2.4]
    REPORTS = ["*.fasta", "*.fa", "*.fn", "*.fna", "*.faa", "*.html", "*.txt", "*.tab"]
    ALL_BIO = ["*.fastq", "*.fastq.gz", "*.bam", "*.pod5", "*.tar.gz", "*.gz", "*.zip", 
               "*.fasta", "*.fa", "*.fn", "*.fna", "*.faa", "*.html", "*.txt", "*.tab"]

class CoreExplorer(QDialog):
    """
    [PANCERNY SYSTEMOWY EKSPLORATOR JĄDRA - CORE ENGINE]:
    Wbudowany, izolowany menedżer zasobów dyskowych NVMe Kingston oraz HDD.
    Wycina menu kontekstowe OS Lubuntu, blokuje klawisze niszczące i narzuca tryb Read-Only.
    """
    def __init__(self, parent=None, mode=ExplorerMode.FILE_SELECT, filter_profile=FilterProfile.RAW_DATA, start_dir=None):
        super().__init__(parent)
        self.mode = mode
        self.filter_profile = filter_profile
        
        # 1. USTALENIE PUNKTU STARTOWEGO Z POTRÓJNYM BEZPIECZNIKIEM UCIECZKI
        if not start_dir or not os.path.exists(start_dir):
            start_dir = getattr(config, 'DEFAULT_OUTPUT_DIR', "/home/ionadmin/kombajn_workspace/projects")
        if not os.path.exists(start_dir):
            start_dir = os.path.expanduser("~")
            
        self.current_selected_path = None
        self.start_absolute_path = os.path.abspath(start_dir)
        
        # Służy do śledzenia aktualnego katalogu bazowego (wirtualnego korzenia) w locie RAM
        self.current_root_path = self.start_absolute_path
        
        # 2. INICJALIZACJA I PARAMETRYZACJA MODALNEGO OKNA INTERFEJSU
        self.setWindowTitle("Kombajn T430 - Autonomiczny Menedżer Zasobów Laboratoryjnych")
        self.setMinimumSize(850, 550)
        self.setStyleSheet("""
            QDialog { background-color: #121212; border: 2px solid #2C2C2C; }
            QWidget { background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI', Arial; font-size: 13px; }
            QTreeView { background-color: #1A1A1A; border: 1px solid #2C2C2C; color: #FFFFFF; gridline-color: #2C2C2C; }
            QTreeView::item:hover { background-color: #2D2D2D; color: #00FF66; }
            QTreeView::item:selected { background-color: #006622; color: #FFFFFF; font-weight: bold; }
            QPushButton { background-color: #2D2D2D; border: 1px solid #3A3A3A; border-radius: 4px; padding: 6px 15px; font-weight: bold; }
            QPushButton:hover { background-color: #3D3D3D; border: 1px solid #00FF66; }
            QPushButton:disabled { background-color: #1A1A1A; color: #555555; border: 1px solid #222222; }
        """)
        
        # Centralny filtr zdarzeń klawiatury dla uodpornienia przed Delete/BackSpace
        self.installEventFilter(self)
        
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # GÓRNY PASEK NAWIGACYJNY: Nagłówek i przycisk powrotu w wyższy poziom struktury pliku
        navigation_bar = QHBoxLayout()
        title_text = "📁 WYBÓR PLIKU SEKWENCYJNEGO / PACZKI DANYCH" if self.mode == ExplorerMode.FILE_SELECT else "📂 WYBÓR KATALOGU PROJEKTU LABORATORYJNEGO"
        self.lbl_header = QLabel(title_text)
        self.lbl_header.setStyleSheet("font-weight: bold; color: #00FF66; font-size: 14px;")
        
        # Przycisk skoku do folderu nadrzędnego
        self.btn_go_up = QPushButton("W górę ⬆️")
        self.btn_go_up.setStyleSheet("""
            QPushButton { background-color: #1E2D2F; color: #00FF66; border: 1px solid #00FF66; font-size: 11px; padding: 4px 10px; }
            QPushButton:hover { background-color: #006622; color: white; }
        """)
        self.btn_go_up.clicked.connect(self._navigate_to_parent_directory)
        
        navigation_bar.addWidget(self.lbl_header)
        navigation_bar.addStretch()
        navigation_bar.addWidget(self.btn_go_up)
        layout.addLayout(navigation_bar)
        
        # Ścieżka nawigacyjna na żywo (Read-Only)
        self.lbl_current_path = QLabel(f"Aktywny węzeł: {self.start_absolute_path}")
        self.lbl_current_path.setWordWrap(True)
        self.lbl_current_path.setStyleSheet("color: #ECC94B; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.lbl_current_path)
        
        # MODEL I WIDOK SYSTEMU PLIKÓW
        self.model = QFileSystemModel()
        self.model.setReadOnly(True)
        
        if self.mode == ExplorerMode.DIRECTORY_SELECT:
            self.model.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)
        else:
            # PANCERNY BEZPIECZNIK QDir.Filter.AllDirs: Nakazuje modelowi przepuścić absolutnie wszystkie 
            # katalogi systemowe, nakładając maski i filtry nazw rozszerzeń WYŁĄCZNIE na pliki wynikowe [INDEX]!
            self.model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs)
            self.model.setNameFilters(self.filter_profile)
            self.model.setNameFilterDisables(False)

        self.model.setRootPath(self.start_absolute_path)
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.model)
        self.tree_view.setRootIndex(self.model.index(self.start_absolute_path))
       
        # Wycięcie menu kontekstowego OS Lubuntu oraz rygorystyczne spięcie akcji [2.4]
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.tree_view.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Ukrywanie kolumn szumu OS (rozmiar, typ, data) - widoczna tylko nienaruszalna nazwa
        self.tree_view.setColumnHidden(1, True)
        self.tree_view.setColumnHidden(2, True)
        self.tree_view.setColumnHidden(3, True)
        self.tree_view.header().setStyleSheet("QHeaderView::section { background-color: #2D2D2D; color: #00FF66; font-weight: bold; border: 1px solid #2C2C2C; }")
        
        self.tree_view.selectionModel().selectionChanged.connect(self._handle_selection_changed)
        
        # ✅ ERGONOMIA ENTERPRISE: Dwuklik myszką obsługuje wejście głębokie oraz szybką akceptację [2.4]
        self.tree_view.doubleClicked.connect(self._handle_double_clicked_accept)
        layout.addWidget(self.tree_view)
        
        # DOLNA LINIA KONTROLNA (PRZYCISKI ACCEP/CANCEL)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Anuluj ❌")
        self.btn_cancel.setStyleSheet("background-color: #2D2D2D; color: #FFFFFF;")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_accept = QPushButton("Zatwierdź wybór ✅")
        self.btn_accept.setEnabled(False)
        self.btn_accept.setStyleSheet("""
            QPushButton { background-color: #1A1A1A; color: #666666; border: 1px solid #444444; }
            QPushButton:enabled { background-color: #006622; color: #FFFFFF; border: 1px solid #00FF66; }
            QPushButton:enabled:hover { background-color: #008833; }
        """)
        self.btn_accept.clicked.connect(self._accept_and_return)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_accept)
        layout.addLayout(btn_layout)

    def _handle_selection_changed(self):
        """Obsługuje bezpieczną autodetekcję podświetlonego wiersza w RAM."""
        indexes = self.tree_view.selectionModel().selectedRows()
        if not indexes:
            self.btn_accept.setEnabled(False)
            self.lbl_current_path.setText("Aktywny węzeł: Nie zaznaczono pozycji")
            return
            
        index = indexes[0]
        path = self.model.filePath(index)
        is_dir = self.model.isDir(index)
        
        self.lbl_current_path.setText(f"Aktywny węzeł: {path}")
        
        # Walidacja zgodności wyboru z zadeklarowanym trybem jądra
        if self.mode == ExplorerMode.DIRECTORY_SELECT:
            if is_dir:
                self.current_selected_path = path
                self.btn_accept.setEnabled(True)
            else:
                self.btn_accept.setEnabled(False)
        else:
            if not is_dir:
                self.current_selected_path = path
                self.btn_accept.setEnabled(True)
            else:
                self.btn_accept.setEnabled(False)

    def _handle_double_clicked_accept(self, index: QModelIndex):
        """
        [THE DOUBLE CLICK DRILLDOWN & ACCEPT INTERLOCK]: 
        Jeśli kliknięto katalog -> wejdź do środka i przepnij korzeń widoku.
        Jeśli kliknięto zwalidowany plik -> zatwierdź i zwróć ścieżkę do RAM [2.4].
        """
        if not index.isValid(): return
        
        is_dir = self.model.isDir(index)
        path = self.model.filePath(index)
        
        if is_dir:
            # ✅ PRZEPIĘCIE WIRTUALNEGO KORZENIA: Bezpieczne wejście do wnętrza folderu dwuklikiem [2.4]
            self.current_root_path = path
            self.model.setRootPath(path)
            self.tree_view.setRootIndex(self.model.index(path))
            self.lbl_current_path.setText(f"Aktywny węzeł: {path}")
            
            # W trybie wyboru katalogu automatycznie podświetlamy przycisk akceptacji
            if self.mode == ExplorerMode.DIRECTORY_SELECT:
                self.current_selected_path = path
                self.btn_accept.setEnabled(True)
        else:
            # Zatwierdzenie pliku lub folderu końcowego [2.4]
            if self.mode == ExplorerMode.FILE_SELECT:
                self.current_selected_path = path
                self._accept_and_return()

    def _navigate_to_parent_directory(self):
        """
        [ATOMOWY SKOK W GÓRĘ]: Oblicza katalog nadrzędny (Parent Directory),
        weryfikuje jego istnienie i bezpiecznie przestawia korzeń widoku drzewiastego.
        """
        if not self.current_root_path:
            return
            
        # 1. Wyliczamy bezwzględną ścieżkę o jeden poziom wyżej
        parent_dir = os.path.dirname(os.path.abspath(self.current_root_path))
        
        # 2. BEZPIECZNIK: Sprawdzamy, czy katalog nadrzędny fizycznie istnieje
        if parent_dir and os.path.exists(parent_dir) and parent_dir != self.current_root_path:
            # Aktualizujemy stan pamięci lokalnej RAM
            self.current_root_path = parent_dir
            
            # Przestawiamy wskaźnik modelu i wirtualny korzeń widoku drzewiastego Qt C++
            self.model.setRootPath(parent_dir)
            self.tree_view.setRootIndex(self.model.index(parent_dir))
            
            # Synchronizujemy etykiety tekstowe interfejsu
            self.lbl_current_path.setText(f"Aktywny węzeł: {parent_dir}")
            
            if self.mode == ExplorerMode.DIRECTORY_SELECT:
                self.btn_accept.setEnabled(True)
                self.current_selected_path = parent_dir
            else:
                self.btn_accept.setEnabled(False)
                self.current_selected_path = None
        else:
            QMessageBox.information(
                self, 
                "Granica systemu", 
                "Osiągnięto bezwzględną granicę systemu plików (Korzeń główny Linuksa /).\nUcieczka wyżej jest zablokowana!"
            )

    def _accept_and_return(self):
        """Zamyka okno modalne, przekazując sterowanie do wątku wywołującego."""
        if self.current_selected_path:
            self.accept()

    def get_selected_path(self) -> str:
        """Publiczne API jądra: zwraca bezwzględną ścieżkę do wybranego zasobu."""
        return self.current_selected_path

    def eventFilter(self, obj, event):
        """
        [KEYBOARD SNIFFER]: Filtr zdarzeń niskopoziomowych.
        Wychwytuje i neutralizuje destrukcyjne klawisze systemowe (Delete/BackSpace),
        uniemożliwiając naruszenie plików laboratoryjnych na dysku.
        """
        if event and hasattr(event, 'type'):
            try:
                if event.type() == event.Type.KeyPress:
                    from PyQt6.QtGui import QKeyEvent
                    key_event = QKeyEvent(event)
                    if key_event.key() in [Qt.Key.Key_Delete, Qt.Key.Key_Backspace]:
                        return True
            except Exception:
                pass
        return super().eventFilter(obj, event)

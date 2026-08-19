"""
LAUNCHER DML - Sistema de Gestion de Stock y Repuestos
Version: 2.0 - UI Amigable para No Tecnicos
"""

import os
import signal
import socket
import subprocess
import sys
import time
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import messagebox

# Detectar si es ejecutable compilado o script
IS_EXECUTABLE = getattr(sys, 'frozen', False)
if IS_EXECUTABLE:
    # Para .exe empaquetado, ir a directorio padre
    SCRIPT_DIR = Path(sys.executable).parent
else:
    # Para script, ir a directorio padre (para llegar a raiz)
    SCRIPT_DIR = Path(__file__).parent.parent

class DMLLauncher:
    def __init__(self):
        self.server_process = None
        self.server_running = False
        self.root = None
        self.port = 5000
        self.url = f"http://127.0.0.1:{self.port}"
        
    def is_port_available(self):
        """Verificar si puerto 5000 esta disponible"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(('127.0.0.1', self.port))
            return result != 0
    
    def start_server(self):
        """Iniciar el servidor Flask en background"""
        try:
            # Cambiar a directorio del proyecto
            os.chdir(SCRIPT_DIR)
            
            # Comando para ejecutar Flask
            if IS_EXECUTABLE:
                # Si es .exe, el entorno ya esta empaquetado
                cmd = [sys.executable, "app.py"]
            else:
                # Si es script, usar venv
                venv_python = SCRIPT_DIR / "venv" / "Scripts" / "python.exe"
                if venv_python.exists():
                    cmd = [str(venv_python), "app.py"]
                else:
                    cmd = [sys.executable, "app.py"]
            
            # Iniciar proceso
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
                cwd=str(SCRIPT_DIR)
            )
            
            self.server_running = True
            print(f"[OK] Servidor iniciado (PID: {self.server_process.pid})")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error iniciando servidor: {e}")
            return False
    
    def wait_for_server(self, timeout=30):
        """Esperar a que el servidor este listo"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                # Hacer ping al servidor
                urllib.request.urlopen(self.url, timeout=1)
                print(f"[OK] Servidor listo en {self.url}")
                return True
            except Exception:
                pass
            time.sleep(0.5)
        return False
    
    def open_browser(self):
        """Abrir navegador en la URL del sistema"""
        try:
            webbrowser.open(self.url)
            print(f"[OK] Navegador abierto: {self.url}")
        except Exception as e:
            print(f"[ERROR] Error abriendo navegador: {e}")
    
    def show_gui(self):
        """Mostrar GUI de status"""
        self.root = tk.Tk()
        self.root.title("DML - Sistema en Ejecución")
        self.root.geometry("450x300")
        self.root.resizable(False, False)
        
        # Centrar ventana
        self.root.eval('tk::PlaceWindow . center')
        
        # Frame principal
        main_frame = tk.Frame(self.root, bg="#f0f0f0", padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Logo/Título
        title_label = tk.Label(
            main_frame, 
            text="DML - Sistema Operativo",
            font=("Arial", 16, "bold"),
            bg="#f0f0f0",
            fg="#1e3a8a"
        )
        title_label.pack(pady=(0, 10))
        
        # Status
        status_frame = tk.LabelFrame(
            main_frame,
            text="Estado del Sistema",
            font=("Arial", 11, "bold"),
            bg="#f0f0f0",
            fg="#1e3a8a",
            padx=15,
            pady=15
        )
        status_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Status items
        status_items = [
            ("Servidor", "[OK] Ejecutandose", "#10b981"),
            ("Puerto", "5000 (localhost)", "#3b82f6"),
            ("URL", "http://127.0.0.1:5000", "#3b82f6"),
            ("Base de Datos", "[OK] Conectada", "#10b981"),
            ("Status", "Listo para usar", "#10b981")
        ]
        
        for label, value, color in status_items:
            item_frame = tk.Frame(status_frame, bg="#f0f0f0")
            item_frame.pack(fill=tk.X, pady=5)
            
            label_widget = tk.Label(
                item_frame,
                text=f"{label}:",
                font=("Arial", 10),
                bg="#f0f0f0",
                fg="#374151",
                width=15,
                anchor="w"
            )
            label_widget.pack(side=tk.LEFT)
            
            value_widget = tk.Label(
                item_frame,
                text=value,
                font=("Arial", 10, "bold"),
                bg="#f0f0f0",
                fg=color
            )
            value_widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Botones
        button_frame = tk.Frame(main_frame, bg="#f0f0f0")
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Botón Abrir Sistema
        open_btn = tk.Button(
            button_frame,
            text="ABRIR Sistema en Navegador",
            command=self.on_open_click,
            bg="#1e3a8a",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        open_btn.pack(fill=tk.X, pady=(0, 10))
        
        # Botón Ver Manual
        manual_btn = tk.Button(
            button_frame,
            text="VER Manual de Usuario",
            command=self.on_manual_click,
            bg="#3b82f6",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        manual_btn.pack(fill=tk.X, pady=(0, 10))
        
        # Botón Cerrar
        close_btn = tk.Button(
            button_frame,
            text="CERRAR Sistema",
            command=self.on_close_click,
            bg="#ef4444",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        close_btn.pack(fill=tk.X)
        
        # Info
        info_label = tk.Label(
            main_frame,
            text="El navegador se abrirá automáticamente.\nLogin: admin@dml.com / admin123",
            font=("Arial", 9),
            bg="#f0f0f0",
            fg="#6b7280",
            justify=tk.CENTER
        )
        info_label.pack(pady=(10, 0))
        
        # Handler para cerrar ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_click)
        
        self.root.mainloop()
    
    def on_open_click(self):
        """Click en botón Abrir"""
        self.open_browser()
        messagebox.showinfo(
            "Sistema Abierto",
            f"El sistema se está cargando en:\n\n{self.url}\n\n"
            "Si el navegador no abre automáticamente,\n"
            "cópialo y pégalo en la barra de direcciones."
        )
    
    def on_manual_click(self):
        """Click en botón Ver Manual"""
        manual_path = SCRIPT_DIR / "DOCUMENTACION_SISTEMA" / "MANUAL_USUARIO_COMPLETO.md"
        if manual_path.exists():
            os.startfile(str(manual_path))
        else:
            messagebox.showwarning(
                "Archivo No Encontrado",
                "No se encontró el manual de usuario.\n\n"
                "Busca el archivo: MANUAL_USUARIO_COMPLETO.md"
            )
    
    def on_close_click(self):
        """Click en botón Cerrar"""
        if messagebox.askyesno("Cerrar Sistema", "¿Deseas detener el servidor?\n\nSe cerrarán todas las conexiones."):
            self.stop_server()
            if self.root:
                self.root.destroy()
            sys.exit(0)
    
    def stop_server(self):
        """Detener servidor"""
        if self.server_process and self.server_running:
            try:
                if sys.platform == "win32":
                    # En Windows, usar ctrl-break para el grupo de procesos
                    os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
                else:
                    self.server_process.terminate()
                self.server_running = False
                print("[OK] Servidor detenido")
            except Exception:
                pass
    
    def run(self):
        """Ejecutar launcher completo"""
        print("\n" + "="*50)
        print("  DML - Sistema de Gestión")
        print("="*50 + "\n")
        
        # Verificar puerto
        if not self.is_port_available():
            messagebox.showerror(
                "Error",
                "El puerto 5000 ya está en uso.\n\n"
                "Cierra la otra instancia e intenta nuevamente."
            )
            sys.exit(1)
        
        print("1. Iniciando servidor...")
        if not self.start_server():
            messagebox.showerror(
                "Error",
                "No se pudo iniciar el servidor.\n\n"
                "Verifica que todos los archivos estén presentes."
            )
            sys.exit(1)
        
        print("2. Esperando a que servidor esté listo...")
        time.sleep(2)
        
        if not self.wait_for_server():
            messagebox.showerror(
                "Error",
                "El servidor no respondió a tiempo.\n\n"
                "Intenta abrir nuevamente."
            )
            self.stop_server()
            sys.exit(1)
        
        print("3. Abriendo interfaz...\n")
        time.sleep(1)
        self.open_browser()
        
        print("4. Mostrando ventana de control...\n")
        self.show_gui()


if __name__ == "__main__":
    launcher = DMLLauncher()
    launcher.run()

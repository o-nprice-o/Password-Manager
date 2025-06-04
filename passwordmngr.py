try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk
    import pyperclip
    from ttkthemes import ThemedTk
except ImportError:
    raise ImportError("tkinter, pyperclip, and ttkthemes modules are required. Install them with `pip install pyperclip ttkthemes`.")

import json
import os
from cryptography.fernet import Fernet
import time

# === CONFIGURATION ===
DATA_FILE = 'vault.json'
KEY_FILE = 'vault.key'
AUTO_LOCK_TIMEOUT = 300  # 5 minutes

# === ENCRYPTION HELPERS ===
def generate_key():
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
    return key

def load_key():
    if not os.path.exists(KEY_FILE):
        return generate_key()
    with open(KEY_FILE, 'rb') as f:
        return f.read()

def encrypt_data(data: dict, key: bytes):
    fernet = Fernet(key)
    json_data = json.dumps(data).encode()
    return fernet.encrypt(json_data)

def decrypt_data(token: bytes, key: bytes):
    fernet = Fernet(key)
    try:
        decrypted = fernet.decrypt(token)
        return json.loads(decrypted.decode())
    except:
        return {}

# === VAULT STORAGE ===
def load_vault(key):
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, 'rb') as f:
        encrypted = f.read()
    return decrypt_data(encrypted, key)

def save_vault(data, key):
    encrypted = encrypt_data(data, key)
    with open(DATA_FILE, 'wb') as f:
        f.write(encrypted)

# === GUI LOGIC ===
class PasswordManager:
    def __init__(self, root):
        self.root = root
        self.root.set_theme('arc')  # example

        print(f"Root window class: {type(self.root)}")
        print(f"Is root a ThemedTk? {isinstance(self.root, ThemedTk)}")
        print(dir(self.root))  # See what methods it has

        self.root.title('🔐 Password Manager')
        self.root.geometry('400x300')

        self.key = load_key()
        self.vault = load_vault(self.key)
        self.last_active = time.time()

        # Get available themes from ttkthemes
        self.available_themes = self.root.get_themes()
        self.current_theme = tk.StringVar(value=self.root.current_theme)

        # Bind reset timer for auto-lock
        self.root.bind_all("<Any-KeyPress>", self.reset_timer)
        self.root.bind_all("<Any-Button>", self.reset_timer)
        self.root.after(1000, self.auto_lock_check)

        self.vault_win = None

        self.build_gui()

    def build_gui(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill='both', expand=True)

        # Theme selector
        ttk.Label(frame, text="Choose Theme:").grid(row=0, column=0, sticky='w')
        self.theme_combo = ttk.Combobox(frame, values=self.available_themes, textvariable=self.current_theme, state='readonly')
        self.theme_combo.grid(row=0, column=1, sticky='ew')
        self.theme_combo.bind('<<ComboboxSelected>>', self.change_theme)

        # Input fields shifted down one row
        ttk.Label(frame, text='Site:').grid(row=1, column=0, sticky='e')
        self.entry_site = ttk.Entry(frame, width=25)
        self.entry_site.grid(row=1, column=1)

        ttk.Label(frame, text='Username:').grid(row=2, column=0, sticky='e')
        self.entry_user = ttk.Entry(frame, width=25)
        self.entry_user.grid(row=2, column=1)

        ttk.Label(frame, text='Password:').grid(row=3, column=0, sticky='e')
        self.entry_pass = ttk.Entry(frame, width=25, show='*')
        self.entry_pass.grid(row=3, column=1)

        ttk.Button(frame, text='Add / Update', command=self.add_update).grid(row=4, column=0, columnspan=2, pady=5)
        ttk.Button(frame, text='Show Vault', command=self.show_vault).grid(row=5, column=0, columnspan=2, pady=5)

    def change_theme(self, event=None):
        selected_theme = self.current_theme.get()
        self.root.set_theme(selected_theme)
        # Optional: update combobox text in case theme changed elsewhere
        self.theme_combo.set(selected_theme)

    def reset_timer(self, event=None):
        self.last_active = time.time()

    def auto_lock_check(self):
        if time.time() - self.last_active > AUTO_LOCK_TIMEOUT:
            self.vault = {}  # Wipe in-memory vault
            messagebox.showwarning("Auto Lock", "Vault has been locked due to inactivity.")
        self.root.after(1000, self.auto_lock_check)

    def add_update(self):
        site = self.entry_site.get().strip()
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()

        if not site or not username or not password:
            messagebox.showerror('Error', 'All fields are required!')
            return

        self.vault[site] = {'username': username, 'password': password}
        save_vault(self.vault, self.key)
        messagebox.showinfo('Saved', f'Credentials for {site} saved.')
        self.entry_site.delete(0, tk.END)
        self.entry_user.delete(0, tk.END)
        self.entry_pass.delete(0, tk.END)

        if self.vault_win:
            self.update_vault_list(self.vault_win, '')

    def delete_credential(self, site, window):
        if messagebox.askyesno("Delete", f"Delete credentials for {site}?"):
            self.vault.pop(site, None)
            save_vault(self.vault, self.key)
            messagebox.showinfo("Deleted", f"Deleted credentials for {site}.")
            self.update_vault_list(window, '')

    def copy_to_clipboard(self, value):
        pyperclip.copy(value)
        messagebox.showinfo("Copied", "Password copied to clipboard.")

    def show_vault(self):
        if self.vault_win and tk.Toplevel.winfo_exists(self.vault_win):
            self.vault_win.lift()
            return

        self.vault_win = tk.Toplevel(self.root)
        self.vault_win.title('🔒 Stored Credentials')
        self.vault_win.geometry('500x400')

        search_var = tk.StringVar()
        search_var.trace("w", lambda *args: self.update_vault_list(self.vault_win, search_var.get()))
        ttk.Entry(self.vault_win, textvariable=search_var).pack(fill='x', padx=5, pady=5)
        self.vault_list_frame = ttk.Frame(self.vault_win)
        self.vault_list_frame.pack(fill='both', expand=True)

        self.update_vault_list(self.vault_win, '')

    def update_vault_list(self, win, filter_text):
        for widget in self.vault_list_frame.winfo_children():
            widget.destroy()

        row = 0
        for site, creds in self.vault.items():
            if filter_text.lower() in site.lower():
                ttk.Label(self.vault_list_frame, text=f'{site}', width=20).grid(row=row, column=0, sticky='w', padx=5)
                ttk.Label(self.vault_list_frame, text=f"{creds['username']} / {creds['password']}", width=30).grid(row=row, column=1, sticky='w')
                ttk.Button(self.vault_list_frame, text="Copy", command=lambda p=creds['password']: self.copy_to_clipboard(p)).grid(row=row, column=2)
                ttk.Button(self.vault_list_frame, text="Delete", command=lambda s=site, w=win: self.delete_credential(s, w)).grid(row=row, column=3)
                row += 1

# === RUN ===
if __name__ == '__main__':
    root = ThemedTk(theme="arc")  # Default theme can be changed here
    app = PasswordManager(root)
    root.mainloop()
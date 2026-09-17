import tkinter as tk
from tkinter import messagebox, ttk

from controller.tracker_controller import HardwareAuthController


class HardwareLoginWindow:
    def __init__(self, root, on_login_success):
        self.root = root
        self.on_login_success = on_login_success
        self.auth = HardwareAuthController()
        self.root.title("Engineering Equipment Tracking System - Login")
        self.root.geometry("370x365")
        self.root.minsize(330, 300)
        self.root.resizable(True, True)

        tk.Label(root, text="Engineering Equipment Tracking System", font=("Segoe UI", 12, "bold")).pack(pady=(15, 5))
        self._field("Username:", "entry_user")
        self._field("Email (for registration/reset):", "entry_email")
        self._field("Password:", "entry_pass", secret=True)

        role_frame = tk.Frame(root)
        role_frame.pack(anchor="w", padx=20, pady=5)
        tk.Label(role_frame, text="Role:").pack(side=tk.LEFT)
        self.role_var = tk.StringVar(value="USER")
        ttk.Combobox(role_frame, textvariable=self.role_var, values=("USER", "ADMIN"), state="readonly", width=12).pack(side=tk.LEFT, padx=8)

        self.show_password_var = tk.BooleanVar(value=False)
        tk.Checkbutton(root, text="Show Password", variable=self.show_password_var, command=self._toggle_password).pack(anchor="w", padx=20)

        buttons = tk.Frame(root)
        buttons.pack(pady=12)
        tk.Button(buttons, text="Login", command=self.handle_login, bg="#4CAF50", fg="white", width=12).pack(side=tk.LEFT, padx=4)
        tk.Button(buttons, text="Register", command=self.handle_register, bg="#2196F3", fg="white", width=12).pack(side=tk.LEFT, padx=4)
        tk.Button(root, text="Reset / Unlock Password", command=self.open_reset_dialog).pack()

    def _field(self, label, attribute, secret=False):
        tk.Label(self.root, text=label).pack(anchor="w", padx=20, pady=(7, 0))
        entry = tk.Entry(self.root, width=38, show="*" if secret else "")
        entry.pack(padx=20)
        setattr(self, attribute, entry)

    def handle_login(self):
        username = self.entry_user.get().strip()
        success, result = self.auth.login(username, self.entry_pass.get())
        if success:
            messagebox.showinfo("Login Successful", "Login successful.")
            self.on_login_success(result["username"], result["role"])
        else:
            messagebox.showerror("Login Failed", result)

    def handle_register(self):
        success, msg = self.auth.register(
            self.entry_user.get().strip(), self.entry_pass.get(), self.entry_email.get().strip(), self.role_var.get()
        )
        if success:
            messagebox.showinfo("Registration Successful", msg)
        else:
            messagebox.showerror("Registration Alert", msg)

    def open_reset_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Reset / Unlock Password")
        dialog.geometry("350x140")
        dialog.transient(self.root)
        tk.Label(dialog, text="Registered email:").pack(anchor="w", padx=15, pady=(12, 0))
        email = tk.Entry(dialog, width=38)
        email.pack(padx=15)
        def submit():
            success, msg = self.auth.request_password_reset(email.get().strip())
            (messagebox.showinfo if success else messagebox.showerror)("Password Reset", msg)
            if success:
                dialog.destroy()

        tk.Button(dialog, text="Submit Request", command=submit, bg="#FF9800", fg="white").pack(pady=14)

    def _toggle_password(self):
        self.entry_pass.config(show="" if self.show_password_var.get() else "*")

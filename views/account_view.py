import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from controller.tracker_controller import HardwareAuthController


class ProfileWindow:
    def __init__(self, parent, username):
        self.auth = HardwareAuthController()
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Profile & Security")
        self.dialog.geometry("380x300")
        profile = self.auth.get_profile(username)
        tk.Label(self.dialog, text=f"Username: {profile[0]}").pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(self.dialog, text=f"Email: {profile[1]}").pack(anchor="w", padx=20, pady=4)
        tk.Label(self.dialog, text=f"Role: {profile[2]}").pack(anchor="w", padx=20, pady=4)
        tk.Label(self.dialog, text="Current password:").pack(anchor="w", padx=20, pady=(12, 0))
        current = tk.Entry(self.dialog, show="*", width=35)
        current.pack(padx=20)
        tk.Label(self.dialog, text="New password:").pack(anchor="w", padx=20, pady=(7, 0))
        new = tk.Entry(self.dialog, show="*", width=35)
        new.pack(padx=20)

        def change():
            success, msg = self.auth.change_password(username, current.get(), new.get())
            (messagebox.showinfo if success else messagebox.showerror)("Password Change", msg)
            if success:
                self.dialog.destroy()

        tk.Button(self.dialog, text="Change Password", command=change, bg="#2196F3", fg="white").pack(pady=15)


class AdminApprovalsWindow:
    def __init__(self, parent, admin_username):
        self.auth = HardwareAuthController()
        self.admin_username = admin_username
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Admin Approvals")
        self.dialog.geometry("760x320")
        columns = ("ID", "Username", "Email", "Status", "Requested", "Reviewed", "By")
        self.tree = ttk.Treeview(self.dialog, columns=columns, show="headings")
        for column in columns:
            self.tree.heading(column, text=column)
            self.tree.column(column, width=105 if column != "Email" else 180)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        controls = tk.Frame(self.dialog)
        controls.pack(pady=(0, 10))
        tk.Button(controls, text="Approve Selected", command=lambda: self.review(True), bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(controls, text="Reject Selected", command=lambda: self.review(False), bg="#f44336", fg="white").pack(side=tk.LEFT, padx=5)
        self.load()

    def load(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.auth.get_reset_requests():
            self.tree.insert("", tk.END, values=row)

    def review(self, approve):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Approval", "Select a reset request first.")
            return
        request_id = self.tree.item(selected[0])["values"][0]
        new_password = None
        if approve:
            new_password = simpledialog.askstring(
                "Provide New Password",
                "Enter the new password to give the user:",
                parent=self.dialog,
                show="*",
            )
            if new_password is None:
                return
        success, msg = self.auth.review_reset_request(
            int(request_id), self.admin_username, approve, new_password
        )
        (messagebox.showinfo if success else messagebox.showerror)("Approval", msg)
        if success:
            self.load()

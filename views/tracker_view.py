import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from controller.hardware_controller import HardwareController
from views.account_view import AdminApprovalsWindow, ProfileWindow
from logger import logger


class HardwareTrackerWindow:
    def __init__(self, root, username="Unknown", role="USER", on_logout=None):
        self.root = root
        self.username = username
        self.role = role
        self.on_logout = on_logout
        self.controller = HardwareController()
        self.selected_item_id = None
        self._refresh_in_progress = False
        self._auto_refresh_job = None

        self.root.title("Engineering Equipment Tracking System")
        self.root.geometry("900x700")
        self.root.minsize(900, 620)
        self.root.resizable(True, True)
        self.root.configure(bg="#d9d9d9")

        self.sidebar = tk.Frame(self.root, width=220, bg="#efefef", bd=1, relief="solid")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="ENGINEERING", bg="#efefef", fg="#222222", font=("Segoe UI", 10, "bold"), anchor="w", justify="left").pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(self.sidebar, text="EQUIPMENT", bg="#efefef", fg="#222222", font=("Segoe UI", 10, "bold"), anchor="w", justify="left").pack(fill="x", padx=14, pady=(0, 10))

        self.nav_buttons = {}
        menu_items = [
            "Dashboard",
            "Inventory",
            "Item Finder",
            "Borrow & Return",
            "Maintenance",
            "Reports & Analytics",
            "Notifications",
            "Activity Logs",
            "User Management",
            "Settings",
        ]
        for idx, item in enumerate(menu_items):
            bg = "#f6f6f6" if idx % 2 == 0 else "#eeeeee"
            btn = tk.Button(
                self.sidebar,
                text=item,
                bg=bg,
                fg="#2d2d2d",
                font=("Segoe UI", 9),
                anchor="w",
                justify="left",
                bd=0,
                relief="flat",
                padx=14,
                pady=8,
                height=1,
                command=lambda value=item: self.open_section(value),
            )
            btn.pack(fill="x")
            self.nav_buttons[item] = btn

        self.content_area = tk.Frame(self.root, bg="#d9d9d9")
        self.content_area.pack(side="left", fill="both", expand=True, padx=18, pady=18)

        self.dashboard_panel = tk.Frame(self.content_area, bg="#d9d9d9")
        self.inventory_panel = tk.Frame(self.content_area, bg="#d9d9d9")
        self.section_frames = {"Dashboard": self.dashboard_panel, "Inventory": self.inventory_panel}

        self.frame_banner = tk.Frame(self.dashboard_panel, bg="#efefef", bd=1, relief="solid", padx=12, pady=12)
        self.frame_banner.pack(fill="x")

        self.label_user = tk.Label(self.frame_banner, text=f"Logged in as: {self.username} ({self.role})", bg="#efefef", fg="#222", font=("Segoe UI", 9, "bold"))
        self.label_user.pack(side="left")

        self.label_total = tk.Label(self.frame_banner, text="Total Inventory Value: ₱0.00", bg="#efefef", fg="#2b7a2b", font=("Segoe UI", 12, "bold"))
        self.label_total.pack(side="right")

        self.dashboard_summary = tk.Label(self.frame_banner, text="Items: 0 | Low Stock: 0 | Out of Stock: 0", bg="#efefef", fg="#4b4b4b", font=("Segoe UI", 9, "bold"))
        self.dashboard_summary.pack(side="right", padx=(0, 18))

        top_actions = tk.Frame(self.dashboard_panel, bg="#d9d9d9")
        top_actions.pack(fill="x", pady=(12, 0))
        tk.Button(top_actions, text="Refresh", command=self.load_data, width=10).pack(side="left", padx=(0, 8))
        tk.Button(top_actions, text="My Profile & Security", command=self.open_profile, width=22).pack(side="left", padx=(0, 8))
        tk.Button(top_actions, text="Export CSV", command=self.handle_export, width=14, bg="#f4a91d", fg="white").pack(side="left", padx=(0, 8))
        btn_logout = tk.Button(top_actions, text="Logout", command=self.handle_logout, bg="#607D8B", fg="white", width=10)
        btn_logout.pack(side="right")
        if self.role == "ADMIN":
            tk.Button(top_actions, text="Admin Approvals", command=self.open_approvals, bg="#795548", fg="white", width=16).pack(side="right", padx=(0, 8))

        overview = tk.LabelFrame(self.dashboard_panel, text="EQUIPMENT OVERVIEW", font=("Segoe UI", 9, "bold"), padx=10, pady=10)
        overview.pack(fill="x", pady=(10, 10))

        stats = tk.Frame(overview, bg="#f5f5f5")
        stats.pack(fill="x")

        self.dashboard_cards = {}
        for label in ("TOTAL", "AVAILABLE", "BORROWED"):
            card = tk.Frame(stats, bd=1, relief="solid", padx=10, pady=8, bg="#f9f9f9")
            card.pack(side="left", fill="y", expand=True, padx=(0, 8))
            tk.Label(card, text=label, font=("Segoe UI", 8, "bold"), fg="#444", bg="#f9f9f9").pack(anchor="w")
            value_label = tk.Label(card, text="0", font=("Segoe UI", 16, "bold"), fg="#222", bg="#f9f9f9")
            value_label.pack(anchor="w")
            self.dashboard_cards[label] = value_label

        lower_stats = tk.Frame(overview, bg="#f5f5f5")
        lower_stats.pack(fill="x", pady=(10, 0))

        for label in ("MAINTENANCE", "LOW STOCK", "INVENTORY"):
            card = tk.Frame(lower_stats, bd=1, relief="solid", padx=10, pady=8, bg="#f9f9f9")
            card.pack(side="left", fill="y", expand=True, padx=(0, 8))
            tk.Label(card, text=label, font=("Segoe UI", 8, "bold"), fg="#444", bg="#f9f9f9").pack(anchor="w")
            value_label = tk.Label(card, text="0", font=("Segoe UI", 16, "bold"), fg="#222", bg="#f9f9f9")
            value_label.pack(anchor="w")
            self.dashboard_cards[label] = value_label

        filter_frame = tk.Frame(self.inventory_panel)
        filter_frame.pack(fill="x", pady=(8, 0))
        tk.Label(filter_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        tk.Entry(filter_frame, textvariable=self.search_var, width=28).pack(side="left", padx=5)
        tk.Label(filter_frame, text="Category:").pack(side="left")
        self.category_var = tk.StringVar(value="All")
        self.category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var, state="readonly", width=18)
        self.category_combo.pack(side="left", padx=5)
        tk.Button(filter_frame, text="Apply Filter", command=self.load_data).pack(side="left", padx=5)
        tk.Button(filter_frame, text="Clear", command=self.clear_filter).pack(side="left")

        frame_form = tk.LabelFrame(self.inventory_panel, text="Add / Update Equipment Item", padx=10, pady=10)
        frame_form.pack(fill="x", pady=8)
        if self.role != "ADMIN":
            frame_form.configure(text="Equipment Inventory (read-only)")

        tk.Label(frame_form, text="Item Name:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_name = tk.Entry(frame_form, width=25)
        self.entry_name.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(frame_form, text="Category:").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_category = tk.Entry(frame_form, width=20)
        self.entry_category.grid(row=0, column=3, padx=5, pady=5)

        tk.Label(frame_form, text="Quantity:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.entry_quantity = tk.Entry(frame_form, width=25)
        self.entry_quantity.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(frame_form, text="Unit Price (₱):").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entry_price = tk.Entry(frame_form, width=20)
        self.entry_price.grid(row=1, column=3, padx=5, pady=5)

        tk.Label(frame_form, text="Serial Number:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.entry_serial = tk.Entry(frame_form, width=25)
        self.entry_serial.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(frame_form, text="Condition:").grid(row=2, column=2, sticky="e", padx=5, pady=5)
        self.condition_var = tk.StringVar(value="Good")
        self.entry_condition = ttk.Combobox(frame_form, textvariable=self.condition_var, values=self.controller.VALID_CONDITIONS, state="readonly", width=18)
        self.entry_condition.grid(row=2, column=3, padx=5, pady=5)

        btn_save = tk.Button(frame_form, text="Save Item", command=self.add_item, bg="#4CAF50", fg="white")
        btn_save.grid(row=3, column=0, columnspan=2, padx=5, pady=10, sticky="ew")

        btn_update = tk.Button(frame_form, text="Update Selected", command=self.update_item, bg="#2196F3", fg="white")
        btn_update.grid(row=3, column=2, padx=5, pady=10, sticky="ew")

        btn_delete = tk.Button(frame_form, text="Delete Selected", command=self.delete_item, bg="#f44336", fg="white")
        btn_delete.grid(row=3, column=3, padx=5, pady=10, sticky="ew")

        btn_clear = tk.Button(frame_form, text="Clear Form", command=self._clear_form)
        btn_clear.grid(row=4, column=0, columnspan=4, padx=5, pady=(0, 2), sticky="ew")
        if self.role != "ADMIN":
            for button in (btn_save, btn_update, btn_delete):
                button.config(state="disabled")

        frame_table = tk.Frame(self.inventory_panel)
        frame_table.pack(fill="both", expand=True, pady=(4, 0))

        scroll_y = tk.Scrollbar(frame_table, orient=tk.VERTICAL)
        columns = ("ID", "Name", "Category", "Qty", "Price (₱)", "Status", "Condition", "Serial")
        self.tree = ttk.Treeview(frame_table, columns=columns, show="headings", yscrollcommand=scroll_y.set)
        scroll_y.config(command=self.tree.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        widths = {"ID": 50, "Name": 180, "Category": 120, "Qty": 60, "Price (₱)": 90, "Status": 110, "Condition": 110, "Serial": 110}
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], anchor="w" if col == "Name" else "center")

        self.tree.tag_configure("out_of_stock", background="#f8d7da")
        self.tree.tag_configure("low_stock", background="#fff3cd")
        self.tree.tag_configure("in_stock", background="#d4edda")

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)

        self.dashboard_panel.pack(fill="both", expand=True)
        self.inventory_panel.pack(fill="both", expand=True)
        self.select_section("Dashboard")
        self.auto_refresh()

    @staticmethod
    def _row_tag(status):
        return {
            "Out of Stock": "out_of_stock",
            "Low Stock": "low_stock",
            "In Stock": "in_stock",
        }.get(status, "")

    def load_data(self):
        if self._refresh_in_progress:
            return

        self._refresh_in_progress = True
        try:
            self._populate_inventory_table()
            self._refresh_dashboard_cards()
        finally:
            self._refresh_in_progress = False

    def _populate_inventory_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = self.controller.fetch_all_items(self.search_var.get().strip(), self.category_var.get())
        categories = ["All"] + self.controller.fetch_categories()
        self.category_combo["values"] = categories
        if self.category_var.get() not in categories:
            self.category_var.set("All")
        for row in rows:
            item_id, name, category, qty, price, status, serial_number, condition, _ = row
            self.tree.insert("", tk.END, values=(item_id, name, category, qty, f"{price:.2f}", status, condition, serial_number or ""), tags=(self._row_tag(status),))

    def _refresh_dashboard_cards(self):
        total_value = self.controller.get_total_value()
        summary = self.controller.get_dashboard_summary()
        available = max(summary['total_items'] - summary['out_of_stock'] - summary['low_stock'], 0)
        borrowed = summary['borrowed_quantity']
        maintenance = self.controller.get_maintenance_items()

        self.label_total.config(text=f"Total Inventory Value: ₱{total_value:,.2f}")
        self.dashboard_summary.config(text=f"Items: {summary['total_items']} | Low Stock: {summary['low_stock']} | Out of Stock: {summary['out_of_stock']}")

        self.dashboard_cards["TOTAL"].config(text=str(summary['total_items']))
        self.dashboard_cards["AVAILABLE"].config(text=str(available))
        self.dashboard_cards["BORROWED"].config(text=str(borrowed))
        self.dashboard_cards["MAINTENANCE"].config(text=str(len(maintenance)))
        self.dashboard_cards["LOW STOCK"].config(text=str(summary['low_stock']))
        self.dashboard_cards["INVENTORY"].config(text=f"₱{total_value:,.0f}")

    def open_section(self, section_name):
        if section_name in {"Dashboard", "Inventory"}:
            self.select_section(section_name)
            return

        self.select_section(section_name)
        if section_name == "Item Finder":
            self.show_item_finder()
        elif section_name == "Borrow & Return":
            self.show_borrow_return()
        elif section_name == "Maintenance":
            self.show_maintenance()
        elif section_name == "Reports & Analytics":
            self.show_reports()
        elif section_name == "Notifications":
            self.show_notifications()
        elif section_name == "Activity Logs":
            self.show_activity_logs()
        elif section_name == "User Management":
            self.show_user_management()
        elif section_name == "Settings":
            self.show_settings()

    def select_section(self, section_name):
        for name, panel in self.section_frames.items():
            if name == section_name:
                panel.pack(fill="both", expand=True)
            else:
                panel.pack_forget()

        for name, btn in self.nav_buttons.items():
            if name == section_name:
                btn.configure(bg="#d9d9d9", fg="#111111", relief="solid")
            else:
                btn.configure(bg="#f6f6f6" if list(self.nav_buttons.keys()).index(name) % 2 == 0 else "#eeeeee", fg="#2d2d2d", relief="flat")

    def show_item_finder(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Item Finder")
        dialog.geometry("420x220")
        dialog.transient(self.root)

        tk.Label(dialog, text="Scan or enter item ID / serial number:", font=("Segoe UI", 10, "bold")).pack(padx=18, pady=(18, 8), anchor="w")
        entry = tk.Entry(dialog, width=35)
        entry.pack(padx=18, fill="x")

        result = tk.Label(dialog, text="", justify="left", wraplength=360, fg="#333")
        result.pack(padx=18, pady=(12, 0), anchor="w")

        def lookup():
            value = entry.get().strip()
            if not value:
                result.config(text="Please enter an item ID or serial number.")
                return
            row = None
            try:
                row_id = int(value)
                row = self.controller.get_item_by_id(row_id)
            except ValueError:
                with sqlite3.connect("hardware_inventory.db") as conn:
                    row = conn.execute("SELECT item_id, item_name, category, quantity, unit_price, status, serial_number, condition FROM hardware WHERE serial_number = ?", (value,)).fetchone()
            if not row:
                result.config(text="No item was found for that ID or serial number.")
                return
            item_id, name, category, quantity, price, status, serial_number, condition = row
            result.config(text=f"Item: {name}\nCategory: {category}\nStatus: {status}\nCondition: {condition}\nSerial: {serial_number or 'N/A'}")

        tk.Button(dialog, text="Lookup Item", command=lookup, bg="#2196F3", fg="white").pack(pady=14)

    def show_borrow_return(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Borrow & Return")
        dialog.geometry("760x500")
        dialog.minsize(620, 380)
        dialog.transient(self.root)

        form = tk.Frame(dialog)
        form.pack(fill="x", padx=18, pady=(18, 4))

        tk.Label(form, text="Item ID:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        item_id = tk.Entry(form, width=15)
        item_id.grid(row=0, column=1, sticky="ew", pady=4)

        tk.Label(form, text="Student Name:", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        student_name = tk.Entry(form, width=30)
        student_name.grid(row=1, column=1, sticky="ew", pady=4)

        tk.Label(form, text="Student ID:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        student_id = tk.Entry(form, width=20)
        student_id.grid(row=2, column=1, sticky="ew", pady=4)

        tk.Label(form, text="Quantity:", font=("Segoe UI", 10, "bold")).grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        qty = tk.Entry(form, width=25)
        qty.insert(0, "1")
        qty.grid(row=3, column=1, sticky="w", pady=4)
        form.columnconfigure(1, weight=1)

        def refresh_borrowed():
            for row in borrowed_tree.get_children():
                borrowed_tree.delete(row)
            for record in self.controller.get_borrowed_items():
                borrow_id, name, borrower, borrower_id, quantity, borrowed_at = record
                borrowed_tree.insert("", tk.END, values=(borrow_id, name, borrower, borrower_id, quantity, borrowed_at))

        table_label = tk.Label(dialog, text="Currently Borrowed Items", font=("Segoe UI", 10, "bold"))
        table_label.pack(anchor="w", padx=18, pady=(12, 6))
        table_frame = tk.Frame(dialog)
        table_frame.pack(fill="both", expand=True, padx=18)
        table_scroll = tk.Scrollbar(table_frame, orient=tk.VERTICAL)
        borrowed_columns = ("Borrow ID", "Item", "Student Name", "Student ID", "Qty", "Borrowed At")
        borrowed_tree = ttk.Treeview(table_frame, columns=borrowed_columns, show="headings", yscrollcommand=table_scroll.set)
        table_scroll.config(command=borrowed_tree.yview)
        table_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        borrowed_widths = {"Borrow ID": 70, "Item": 150, "Student Name": 150, "Student ID": 100, "Qty": 55, "Borrowed At": 140}
        for column in borrowed_columns:
            borrowed_tree.heading(column, text=column)
            borrowed_tree.column(column, width=borrowed_widths[column], anchor="center")
        borrowed_tree.pack(side=tk.LEFT, fill="both", expand=True)

        def borrow():
            try:
                item = int(item_id.get())
                q = int(qty.get())
            except ValueError:
                messagebox.showerror("Borrow Error", "Please enter a valid item ID and quantity.")
                return
            if not student_name.get().strip() or not student_id.get().strip():
                messagebox.showerror("Borrow Error", "Student name and student ID are required.")
                return
            success, msg = self.controller.borrow_item(item, q, student_name.get(), student_id.get())
            (messagebox.showinfo if success else messagebox.showerror)("Borrow", msg)
            if success:
                self.load_data()
                refresh_borrowed()

        def ret():
            try:
                item = int(item_id.get())
                q = int(qty.get())
            except ValueError:
                messagebox.showerror("Return Error", "Please enter a valid item ID and quantity.")
                return
            success, msg = self.controller.return_item(item, q, student_id.get().strip())
            (messagebox.showinfo if success else messagebox.showerror)("Return", msg)
            if success:
                self.load_data()
                refresh_borrowed()

        actions = tk.Frame(dialog)
        actions.pack(pady=16)
        tk.Button(actions, text="Borrow", command=borrow, bg="#4CAF50", fg="white", width=12).pack(side="left", padx=8)
        tk.Button(actions, text="Return", command=ret, bg="#FF9800", fg="white", width=12).pack(side="left", padx=8)
        refresh_borrowed()

    def show_maintenance(self):
        items = self.controller.get_maintenance_items()
        if not items:
            messagebox.showinfo("Maintenance", "No equipment is currently marked for maintenance or inspection.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Maintenance")
        dialog.geometry("560x260")
        dialog.transient(self.root)

        tree = ttk.Treeview(dialog, columns=("ID", "Item", "Condition", "Qty"), show="headings")
        for col, width in [("ID", 60), ("Item", 180), ("Condition", 130), ("Qty", 60)]:
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for item_id, name, condition, qty in items:
            tree.insert("", tk.END, values=(item_id, name, condition, qty))

        def mark_inspected():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Maintenance", "Select an item first.")
                return
            item_id = tree.item(selected[0])["values"][0]
            with sqlite3.connect("hardware_inventory.db") as conn:
                conn.execute("UPDATE hardware SET condition = 'Good' WHERE item_id = ?", (item_id,))
                conn.commit()
            messagebox.showinfo("Maintenance", "Selected equipment has been marked as inspected.")
            dialog.destroy()
            self.load_data()

        tk.Button(dialog, text="Mark as Inspected", command=mark_inspected, bg="#4CAF50", fg="white").pack(pady=(0, 10))

    def show_reports(self):
        summary = self.controller.get_dashboard_summary()
        report = (
            f"Total items: {summary['total_items']}\n"
            f"Total quantity: {summary['total_quantity']}\n"
            f"Inventory value: ₱{summary['total_value']:,.2f}\n"
            f"Low stock items: {summary['low_stock']}\n"
            f"Out-of-stock items: {summary['out_of_stock']}"
        )
        messagebox.showinfo("Reports & Analytics", report)

    def show_notifications(self):
        notifications = self.controller.get_notifications()
        dialog = tk.Toplevel(self.root)
        dialog.title("Notifications")
        dialog.geometry("600x320")
        dialog.minsize(480, 240)
        dialog.transient(self.root)

        tk.Label(dialog, text="System Alerts", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        text_frame = tk.Frame(dialog)
        text_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL)
        text = tk.Text(text_frame, wrap="word", font=("Segoe UI", 10), yscrollcommand=scrollbar.set)
        scrollbar.config(command=text.yview)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        if not notifications:
            text.insert("end", "No active notifications.\n")
        else:
            for notice in notifications:
                text.insert("end", f"- {notice}\n")
        text.config(state="disabled")

    def show_activity_logs(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Activity Logs")
        dialog.geometry("620x300")
        dialog.transient(self.root)

        text = tk.Text(dialog, height=14, width=80)
        text.pack(padx=12, pady=12, fill="both", expand=True)

        log_file = "app_logging/app.log"
        try:
            with open(log_file, "r", encoding="utf-8") as file:
                lines = file.readlines()[-100:]
            if not lines:
                text.insert("end", "No activity logged yet.\n")
            else:
                for line in lines:
                    text.insert("end", line)
        except FileNotFoundError:
            text.insert("end", "No activity log file has been created yet.\n")
        text.config(state="disabled")

    def show_user_management(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("User Management")
        dialog.geometry("620x260")
        dialog.transient(self.root)

        with sqlite3.connect("hardware_inventory.db") as conn:
            users = conn.execute("SELECT id, username, email, role, locked FROM users ORDER BY id").fetchall()

        tree = ttk.Treeview(dialog, columns=("ID", "Username", "Email", "Role", "Status"), show="headings")
        for col, width in [("ID", 50), ("Username", 140), ("Email", 180), ("Role", 90), ("Status", 90)]:
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for user in users:
            user_id, username, email, role, locked = user
            tree.insert("", tk.END, values=(user_id, username, email, role, "Locked" if locked else "Active"))

    def show_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("360x220")
        dialog.transient(self.root)

        tk.Label(dialog, text="Appearance", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        theme = tk.StringVar(value="Light")
        ttk.Combobox(dialog, textvariable=theme, values=("Light", "Dark"), state="readonly", width=20).pack(padx=18, anchor="w")

        def apply_setting():
            selected = theme.get()
            if selected == "Dark":
                self.root.configure(bg="#2b2b2b")
                self.sidebar.configure(bg="#1f1f1f")
                self.content_area.configure(bg="#2b2b2b")
            else:
                self.root.configure(bg="#d9d9d9")
                self.sidebar.configure(bg="#efefef")
                self.content_area.configure(bg="#d9d9d9")
            messagebox.showinfo("Settings", f"Theme set to {selected} mode.")
            dialog.destroy()

        tk.Button(dialog, text="Apply", command=apply_setting, bg="#4CAF50", fg="white").pack(pady=14)

    def clear_filter(self):
        self.search_var.set("")
        self.category_var.set("All")
        self.load_data()

    def open_profile(self):
        ProfileWindow(self.root, self.username)

    def open_approvals(self):
        if self.role == "ADMIN":
            AdminApprovalsWindow(self.root, self.username)

    def on_row_select(self, event):
        selected = self.tree.selection()
        if not selected:
            self.selected_item_id = None
            return
        values = self.tree.item(selected[0])["values"]
        self.selected_item_id = values[0]
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, values[1])
        self.entry_category.delete(0, tk.END)
        self.entry_category.insert(0, values[2])
        self.entry_quantity.delete(0, tk.END)
        self.entry_quantity.insert(0, values[3])
        self.entry_price.delete(0, tk.END)
        self.entry_price.insert(0, values[4])
        self.entry_serial.delete(0, tk.END)
        self.entry_serial.insert(0, values[7])
        self.condition_var.set(values[6] if values[6] else "Good")

    def _clear_form(self):
        self.entry_name.delete(0, tk.END)
        self.entry_category.delete(0, tk.END)
        self.entry_quantity.delete(0, tk.END)
        self.entry_price.delete(0, tk.END)
        self.entry_serial.delete(0, tk.END)
        self.condition_var.set("Good")
        self.selected_item_id = None

    def add_item(self):
        name = self.entry_name.get().strip()
        category = self.entry_category.get().strip()
        quantity = self.entry_quantity.get().strip()
        price = self.entry_price.get().strip()

        serial_number = self.entry_serial.get().strip()
        condition = self.condition_var.get()
        success, msg = self.controller.add_item(name, category, quantity, price, serial_number=serial_number, condition=condition)
        if success:
            messagebox.showinfo("Success", msg)
            self._clear_form()
            self.load_data()
        else:
            messagebox.showerror("Error", msg)

    def update_item(self):
        if self.selected_item_id is None:
            messagebox.showwarning("Warning", "Please select an item to update!")
            return

        name = self.entry_name.get().strip()
        category = self.entry_category.get().strip()
        quantity = self.entry_quantity.get().strip()
        price = self.entry_price.get().strip()

        serial_number = self.entry_serial.get().strip()
        condition = self.condition_var.get()
        success, msg = self.controller.update_item(self.selected_item_id, name, category, quantity, price, serial_number=serial_number, condition=condition)
        if success:
            messagebox.showinfo("Success", msg)
            self._clear_form()
            self.load_data()
        else:
            messagebox.showerror("Error", msg)

    def delete_item(self):
        if self.selected_item_id is None:
            messagebox.showwarning("Warning", "Please select an item to delete!")
            return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete item ID {self.selected_item_id}?")
        if confirm:
            success, msg = self.controller.delete_item(self.selected_item_id)
            if success:
                messagebox.showinfo("Success", msg)
                self._clear_form()
                self.load_data()
            else:
                messagebox.showerror("Error", msg)

    def handle_export(self):
        success, msg = self.controller.export_to_csv()
        if success:
            messagebox.showinfo("Export Complete", msg)
        else:
            messagebox.showerror("Export Failed", msg)

    def handle_logout(self):
        confirm = messagebox.askyesno("Confirm Logout", "Are you sure you want to log out?")
        if not confirm:
            return
        self.stop_auto_refresh()
        logger.info(f"User Logged Out: '{self.username}' logged out.")
        if callable(self.on_logout):
            self.on_logout()

    def auto_refresh(self):
        self._auto_refresh_job = None
        if not self.root.winfo_exists():
            return

        if self._refresh_in_progress:
            self._schedule_auto_refresh()
            return

        self.load_data()
        self._schedule_auto_refresh()

    def stop_auto_refresh(self):
        if self._auto_refresh_job is None:
            return
        try:
            self.root.after_cancel(self._auto_refresh_job)
        except tk.TclError:
            pass
        finally:
            self._auto_refresh_job = None

    def _schedule_auto_refresh(self):
        if self._auto_refresh_job is not None:
            try:
                self.root.after_cancel(self._auto_refresh_job)
            except Exception:
                pass

        self._auto_refresh_job = self.root.after(15000, self.auto_refresh)

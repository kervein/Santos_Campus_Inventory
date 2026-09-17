import csv
import sqlite3

import db_compat
from logger import logger


class HardwareController:
    def __init__(self, db_name="hardware_inventory.db"):
        self.db_name = db_name

    VALID_CONDITIONS = [
        "Excellent",
        "Good",
        "Needs Inspection",
        "Damaged",
        "Broken",
        "Retired",
    ]

    def _connect(self):
        if db_compat.USE_POSTGRES:
            return db_compat.get_connection()
        return sqlite3.connect(self.db_name)

    def _status_from_quantity(self, quantity: int) -> str:
        if quantity <= 0:
            return "Out of Stock"
        if quantity <= 5:
            return "Low Stock"
        return "In Stock"

    def fetch_all_items(self, search="", category="All"):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE hardware SET status = CASE
               WHEN quantity <= 0 THEN 'Out of Stock'
               WHEN quantity <= 5 THEN 'Low Stock'
               ELSE 'In Stock' END"""
        )
        conn.commit()
        query = "SELECT item_id, item_name, category, quantity, unit_price, status, serial_number, condition, location FROM hardware WHERE 1=1"
        params = []
        if search:
            query += " AND (item_name LIKE ? OR category LIKE ? OR status LIKE ? OR serial_number LIKE ? OR location LIKE ? OR condition LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term, term, term, term])
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
        cursor.execute(query + " ORDER BY item_id", params)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def fetch_categories(self):
        with self._connect() as conn:
            return [row[0] for row in conn.execute("SELECT DISTINCT category FROM hardware ORDER BY category")]

    def get_item_by_id(self, item_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT item_id, item_name, category, quantity, unit_price, status, serial_number, condition, location FROM hardware WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        return row

    def get_total_value(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(quantity * unit_price) FROM hardware")
        result = cursor.fetchone()
        conn.close()
        return result[0] or 0.0

    def borrow_item(self, item_id, quantity=1, student_name="", student_id=""):
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return False, "Borrow quantity must be a valid number."
        if quantity <= 0:
            return False, "Borrow quantity must be greater than zero."

        with self._connect() as conn:
            row = conn.execute("SELECT item_id, item_name, quantity, borrowed_quantity FROM hardware WHERE item_id = ?", (item_id,)).fetchone()
            if not row:
                return False, "Item not found."
            if row[2] < quantity:
                return False, "Not enough quantity available to borrow."
            new_qty = row[2] - quantity
            new_borrowed = row[3] + quantity
            conn.execute("UPDATE hardware SET quantity = ?, borrowed_quantity = ?, status = CASE WHEN ? <= 0 THEN 'Out of Stock' WHEN ? <= 5 THEN 'Low Stock' ELSE 'In Stock' END WHERE item_id = ?", (new_qty, new_borrowed, new_qty, new_qty, item_id))
            conn.execute(
                "INSERT INTO borrow_records (item_id, student_name, student_id, quantity) VALUES (?, ?, ?, ?)",
                (item_id, student_name.strip() or "Unassigned", student_id.strip() or "N/A", quantity),
            )
            conn.commit()
        return True, f"Borrowed {quantity} unit(s) of {row[1]}."

    def return_item(self, item_id, quantity=1, student_id=""):
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return False, "Return quantity must be a valid number."
        if quantity <= 0:
            return False, "Return quantity must be greater than zero."

        with self._connect() as conn:
            row = conn.execute("SELECT item_id, item_name, quantity, borrowed_quantity FROM hardware WHERE item_id = ?", (item_id,)).fetchone()
            if not row:
                return False, "Item not found."
            if row[3] < quantity:
                return False, "Cannot return more units than are currently borrowed."
            record_query = "SELECT borrow_id, quantity FROM borrow_records WHERE item_id = ? AND returned_at IS NULL"
            record_params = [item_id]
            if student_id:
                record_query += " AND student_id = ?"
                record_params.append(student_id)
            record_query += " ORDER BY borrowed_at, borrow_id LIMIT 1"
            record = conn.execute(record_query, record_params).fetchone()
            if student_id and not record:
                return False, "No active borrowed record was found for that student ID."

            new_qty = row[2] + quantity
            new_borrowed = row[3] - quantity
            conn.execute("UPDATE hardware SET quantity = ?, borrowed_quantity = ?, status = CASE WHEN ? <= 0 THEN 'Out of Stock' WHEN ? <= 5 THEN 'Low Stock' ELSE 'In Stock' END WHERE item_id = ?", (new_qty, new_borrowed, new_qty, new_qty, item_id))
            if record:
                borrow_id, record_quantity = record
                if record_quantity > quantity:
                    conn.execute("UPDATE borrow_records SET quantity = quantity - ? WHERE borrow_id = ?", (quantity, borrow_id))
                else:
                    conn.execute("UPDATE borrow_records SET quantity = 0, returned_at = CURRENT_TIMESTAMP WHERE borrow_id = ?", (borrow_id,))
            conn.commit()
        return True, f"Returned {quantity} unit(s) of {row[1]}."

    def get_borrowed_items(self):
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT b.borrow_id, h.item_name, b.student_name, b.student_id,
                       b.quantity, b.borrowed_at
                FROM borrow_records b
                JOIN hardware h ON h.item_id = b.item_id
                WHERE b.returned_at IS NULL AND b.quantity > 0
                ORDER BY b.borrowed_at, b.borrow_id
                """
            ).fetchall()

    def get_maintenance_items(self):
        with self._connect() as conn:
            return conn.execute(
                "SELECT item_id, item_name, condition, quantity FROM hardware WHERE condition IN ('Needs Inspection','Damaged','Broken','Retired') OR quantity <= 5 ORDER BY item_id"
            ).fetchall()

    def get_notifications(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT item_name, quantity, condition FROM hardware WHERE quantity <= 5 OR condition IN ('Needs Inspection','Damaged','Broken','Retired') ORDER BY item_id LIMIT 10"
            ).fetchall()
        notifications = []
        for name, qty, condition in rows:
            if qty <= 5:
                notifications.append(f"Low stock alert: {name} has {qty} remaining.")
            if condition in {'Needs Inspection', 'Damaged', 'Broken', 'Retired'}:
                notifications.append(f"Maintenance alert: {name} is marked {condition}.")
        return notifications

    def get_dashboard_summary(self):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_items,
                    COALESCE(SUM(quantity), 0) AS total_quantity,
                    COALESCE(SUM(quantity * unit_price), 0) AS total_value,
                    COALESCE(SUM(borrowed_quantity), 0) AS borrowed_quantity,
                    SUM(CASE WHEN quantity <= 0 THEN 1 ELSE 0 END) AS out_of_stock,
                    SUM(CASE WHEN quantity > 0 AND quantity <= 5 THEN 1 ELSE 0 END) AS low_stock
                FROM hardware
                """
            ).fetchone()

        return {
            "total_items": rows[0] or 0,
            "total_quantity": rows[1] or 0,
            "total_value": rows[2] or 0.0,
            "borrowed_quantity": rows[3] or 0,
            "out_of_stock": rows[4] or 0,
            "low_stock": rows[5] or 0,
        }

    def add_item(self, name, category, quantity, price, serial_number=None, condition="Good", location=""):
        if not name:
            return False, "Item name is required."
        if not category:
            return False, "Category is required."

        serial_number = (serial_number or "").strip()
        condition = (condition or "Good").strip()
        if condition not in self.VALID_CONDITIONS:
            return False, "Condition must be one of: Excellent, Good, Needs Inspection, Damaged, Broken, Retired."

        try:
            quantity = int(quantity)
            if quantity < 0:
                return False, "Quantity must be a non-negative integer."
        except (ValueError, TypeError):
            return False, "Quantity must be a valid number."

        try:
            price = float(price)
            if price < 0:
                return False, "Unit price must be a non-negative number."
        except (ValueError, TypeError):
            return False, "Unit price must be a valid number."

        status = self._status_from_quantity(quantity)

        try:
            conn = self._connect()
            cursor = conn.cursor()
            if serial_number:
                cursor.execute(
                    "SELECT 1 FROM hardware WHERE serial_number = ? AND serial_number IS NOT NULL",
                    (serial_number,),
                )
                if cursor.fetchone():
                    conn.close()
                    return False, "Possible duplicate: an equipment item with this serial number already exists."

            cursor.execute(
                "INSERT INTO hardware (item_name, category, quantity, unit_price, status, serial_number, condition, location) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, category, quantity, price, status, serial_number or None, condition, location),
            )
            conn.commit()
            conn.close()
            logger.info(f"Hardware item added: {name} ({category}) x{quantity}")
            return True, "Item added successfully."
        except db_compat.Error as exc:
            logger.error(f"Error adding hardware item: {exc}")
            return False, "Failed to add item to the database."

    def update_item(self, item_id, name, category, quantity, price, serial_number=None, condition="Good", location=None):
        if not name:
            return False, "Item name is required."
        if not category:
            return False, "Category is required."

        serial_number = (serial_number or "").strip()
        condition = (condition or "Good").strip()
        if condition not in self.VALID_CONDITIONS:
            return False, "Condition must be one of: Excellent, Good, Needs Inspection, Damaged, Broken, Retired."

        try:
            quantity = int(quantity)
            if quantity < 0:
                return False, "Quantity must be a non-negative integer."
        except (ValueError, TypeError):
            return False, "Quantity must be a valid number."

        try:
            price = float(price)
            if price < 0:
                return False, "Unit price must be a non-negative number."
        except (ValueError, TypeError):
            return False, "Unit price must be a valid number."

        status = self._status_from_quantity(quantity)

        try:
            conn = self._connect()
            cursor = conn.cursor()
            if serial_number:
                cursor.execute(
                    "SELECT 1 FROM hardware WHERE serial_number = ? AND item_id != ?",
                    (serial_number, item_id),
                )
                if cursor.fetchone():
                    conn.close()
                    return False, "Possible duplicate: an equipment item with this serial number already exists."

            cursor.execute(
                "UPDATE hardware SET item_name = ?, category = ?, quantity = ?, unit_price = ?, status = ?, serial_number = ?, condition = ?, location = COALESCE(?, location) WHERE item_id = ?",
                (name, category, quantity, price, status, serial_number or None, condition, location, item_id),
            )
            conn.commit()
            updated = cursor.rowcount
            conn.close()
            if updated:
                logger.info(f"Hardware item updated: ID {item_id}")
                return True, "Item updated successfully."
            return False, "Item not found."
        except db_compat.Error as exc:
            logger.error(f"Error updating hardware item: {exc}")
            return False, "Failed to update item in the database."

    def delete_item(self, item_id):
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM hardware WHERE item_id = ?", (item_id,))
            conn.commit()
            deleted = cursor.rowcount
            conn.close()
            if deleted:
                logger.info(f"Hardware item deleted: ID {item_id}")
                return True, "Item deleted successfully."
            return False, "Item not found."
        except db_compat.Error as exc:
            logger.error(f"Error deleting hardware item: {exc}")
            return False, "Failed to delete item from the database."

    def export_to_csv(self, filename="hardware_inventory_report.csv"):
        try:
            rows = self.fetch_all_items()
            with open(filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["ID", "Name", "Category", "Quantity", "Unit Price", "Status"])
                for row in rows:
                    writer.writerow(row)
            logger.info(f"Inventory exported to CSV: {filename}")
            return True, f"Inventory exported to {filename}."
        except Exception as exc:
            logger.error(f"Error exporting inventory to CSV: {exc}")
            return False, "Failed to export inventory to CSV."

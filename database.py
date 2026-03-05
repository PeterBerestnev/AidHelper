import os
import sqlite3
from datetime import datetime, date
from typing import List, Optional, Tuple


class Database:
    def __init__(self, db_path: str = None):
        # Используем переменную окружения или значение по умолчанию
        self.db_path = db_path or os.getenv("DB_PATH", "medication.db")
        # Создаем директорию для базы данных, если путь содержит директорию
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Инициализация базы данных с созданием таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица препаратов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Таблица для хранения информации о приемах
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medication_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                dosage_mg REAL NOT NULL,
                created_at TEXT NOT NULL,
                medication_id INTEGER DEFAULT 1
            )
        """)
        
        # Таблица для хранения настроек напоминаний
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                medication_id INTEGER DEFAULT 1
            )
        """)
        
        # Таблица для хранения настроек курса
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS course_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                daily_quantity INTEGER NOT NULL,
                dosage_mg REAL NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                medication_id INTEGER DEFAULT 1
            )
        """)
        
        # Миграция: добавляем колонку medication_id в таблицы, если её ещё нет
        try:
            cursor.execute(
                "ALTER TABLE medication_log ADD COLUMN medication_id INTEGER DEFAULT 1"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        
        try:
            cursor.execute(
                "ALTER TABLE reminders ADD COLUMN medication_id INTEGER DEFAULT 1"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        
        try:
            cursor.execute(
                "ALTER TABLE course_settings ADD COLUMN medication_id INTEGER DEFAULT 1"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        
        # Сид: создаём препарат «Акнекутан» по умолчанию, если ещё не создан
        now = datetime.now().isoformat()
        cursor.execute(
            "SELECT id FROM medications WHERE name = ?",
            ("Акнекутан",),
        )
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                """
                INSERT INTO medications (name, description, created_at, is_active)
                VALUES (?, ?, ?, 1)
                """,
                ("Акнекутан", "Препарат по умолчанию", now),
            )
            default_medication_id = cursor.lastrowid
        else:
            default_medication_id = row[0]
        
        # Проставляем medication_id по умолчанию там, где он NULL
        cursor.execute(
            "UPDATE medication_log SET medication_id = ? WHERE medication_id IS NULL",
            (default_medication_id,),
        )
        cursor.execute(
            "UPDATE reminders SET medication_id = ? WHERE medication_id IS NULL",
            (default_medication_id,),
        )
        cursor.execute(
            "UPDATE course_settings SET medication_id = ? WHERE medication_id IS NULL",
            (default_medication_id,),
        )
        
        conn.commit()
        conn.close()

    def add_medication(
        self, quantity: int, dosage_mg: float, medication_id: int = 1
    ) -> bool:
        """Добавить запись о приеме препарата для конкретного препарата"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now = datetime.now()
            
            cursor.execute("""
                INSERT INTO medication_log (date, time, quantity, dosage_mg, created_at, medication_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                quantity,
                dosage_mg,
                now.isoformat(),
                medication_id
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении записи: {e}")
            return False

    def get_today_medications(self, medication_id: int = 1) -> List[Tuple]:
        """Получить все приемы за сегодня для конкретного препарата"""
        conn = self.get_connection()
        cursor = conn.cursor()
        today = date.today().strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT time, quantity, dosage_mg
            FROM medication_log
            WHERE date = ? AND medication_id = ?
            ORDER BY time
        """, (today, medication_id))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def get_medications_by_date(
        self, target_date: date, medication_id: int = 1
    ) -> List[Tuple]:
        """Получить все приемы за указанную дату для конкретного препарата"""
        conn = self.get_connection()
        cursor = conn.cursor()
        date_str = target_date.strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT time, quantity, dosage_mg
            FROM medication_log
            WHERE date = ? AND medication_id = ?
            ORDER BY time
        """, (date_str, medication_id))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def get_medications_summary(self, days: int = 7, medication_id: int = 1) -> dict:
        """Получить сводку за последние N дней для конкретного препарата"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT date, 
                   SUM(quantity) as total_quantity,
                   SUM(quantity * dosage_mg) as total_dosage_mg
            FROM medication_log
            WHERE date >= date('now', '-' || ? || ' days')
              AND medication_id = ?
            GROUP BY date
            ORDER BY date DESC
        """, (days, medication_id))
        
        results = cursor.fetchall()
        conn.close()
        
        summary = {}
        for row in results:
            summary[row[0]] = {
                'quantity': row[1],
                'total_dosage_mg': row[2]
            }
        
        return summary

    def add_reminder(self, time_str: str, medication_id: int = 1) -> bool:
        """Добавить напоминание для конкретного препарата"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now = datetime.now()
            
            cursor.execute("""
                INSERT INTO reminders (time, enabled, created_at, medication_id)
                VALUES (?, 1, ?, ?)
            """, (time_str, now.isoformat(), medication_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении напоминания: {e}")
            return False

    def get_reminders(self, medication_id: Optional[int] = None) -> List[Tuple]:
        """Получить все активные напоминания.

        Если medication_id указан, возвращает напоминания только для этого препарата.
        Возвращает список кортежей (id, time, medication_id).
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if medication_id is not None:
            cursor.execute("""
                SELECT id, time, medication_id
                FROM reminders
                WHERE enabled = 1 AND medication_id = ?
                ORDER BY time
            """, (medication_id,))
        else:
            cursor.execute("""
                SELECT id, time, medication_id
                FROM reminders
                WHERE enabled = 1
                ORDER BY time
            """)
        
        results = cursor.fetchall()
        conn.close()
        return results

    def delete_reminder(self, reminder_id: int) -> bool:
        """Удалить напоминание"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM reminders
                WHERE id = ?
            """, (reminder_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при удалении напоминания: {e}")
            return False

    def get_all_medications(
        self, days: int = None, medication_id: int = 1
    ) -> List[Tuple]:
        """Получить все записи о приеме препарата для конкретного препарата"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if days:
            cursor.execute("""
                SELECT date, time, quantity, dosage_mg, created_at
                FROM medication_log
                WHERE date >= date('now', '-' || ? || ' days')
                  AND medication_id = ?
                ORDER BY date DESC, time DESC
            """, (days, medication_id))
        else:
            cursor.execute("""
                SELECT date, time, quantity, dosage_mg, created_at
                FROM medication_log
                WHERE medication_id = ?
                ORDER BY date DESC, time DESC
            """, (medication_id,))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def generate_statistics_csv(
        self, file_path: str, days: int = 30, medication_id: int = 1
    ) -> bool:
        """Генерировать CSV файл со статистикой для конкретного препарата"""
        try:
            import csv
            medications = self.get_all_medications(days=days, medication_id=medication_id)
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # Заголовки
                writer.writerow(['Дата', 'Время', 'Количество таблеток', 'Дозировка (мг)', 'Общая дозировка (мг)'])
                
                # Данные
                for date_str, time_str, quantity, dosage_mg, created_at in medications:
                    total_dosage = quantity * dosage_mg
                    writer.writerow([
                        date_str,
                        time_str,
                        quantity,
                        dosage_mg,
                        total_dosage
                    ])
            
            return True
        except Exception as e:
            print(f"Ошибка при генерации CSV: {e}")
            return False

    def set_course_settings(
        self,
        daily_quantity: int,
        dosage_mg: float,
        start_date: str = None,
        end_date: str = None,
        medication_id: int = 1,
    ) -> bool:
        """Установить настройки курса для конкретного препарата"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now = datetime.now()
            
            # Деактивируем предыдущие настройки
            cursor.execute("""
                UPDATE course_settings
                SET is_active = 0
                WHERE is_active = 1 AND medication_id = ?
            """, (medication_id,))
            
            # Если дата начала не указана, используем сегодня
            if start_date is None:
                start_date = date.today().strftime("%Y-%m-%d")
            
            # Добавляем новые настройки
            cursor.execute("""
                INSERT INTO course_settings (daily_quantity, dosage_mg, start_date, end_date, is_active, created_at, updated_at, medication_id)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            """, (daily_quantity, dosage_mg, start_date, end_date, now.isoformat(), now.isoformat(), medication_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при установке настроек курса: {e}")
            return False

    def get_active_course_settings(self, medication_id: int = 1) -> Optional[Tuple]:
        """Получить активные настройки курса для конкретного препарата"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, daily_quantity, dosage_mg, start_date, end_date, created_at
            FROM course_settings
            WHERE is_active = 1 AND medication_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (medication_id,))
        
        result = cursor.fetchone()
        conn.close()
        return result

    def get_course_progress(self, medication_id: int = 1) -> dict:
        """Получить прогресс курса для конкретного препарата"""
        settings = self.get_active_course_settings(medication_id=medication_id)
        if not settings:
            return None
        
        _, daily_quantity, dosage_mg, start_date_str, end_date_str, _ = settings
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        today = date.today()
        
        # Вычисляем количество дней курса
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            total_days = (end_date - start_date).days + 1
            days_passed = (today - start_date).days + 1
        else:
            total_days = (today - start_date).days + 1
            days_passed = total_days
            end_date = None
        
        # Получаем статистику по приемам за период курса
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT date, 
                   SUM(quantity) as total_quantity,
                   SUM(quantity * dosage_mg) as total_dosage_mg
            FROM medication_log
            WHERE date >= ? AND date <= ? AND medication_id = ?
            GROUP BY date
            ORDER BY date
        """, (start_date_str, today.strftime("%Y-%m-%d"), medication_id))
        
        daily_stats = cursor.fetchall()
        conn.close()
        
        # Подсчитываем общую статистику
        total_taken_quantity = sum(row[1] for row in daily_stats)
        total_taken_dosage = sum(row[2] for row in daily_stats)
        total_planned_quantity = daily_quantity * days_passed
        total_planned_dosage = daily_quantity * dosage_mg * days_passed
        
        # Подсчитываем дни с приемом
        days_with_medication = len(daily_stats)
        
        return {
            'daily_quantity': daily_quantity,
            'dosage_mg': dosage_mg,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'total_days': total_days,
            'days_passed': days_passed,
            'total_planned_quantity': total_planned_quantity,
            'total_taken_quantity': total_taken_quantity,
            'total_planned_dosage': total_planned_dosage,
            'total_taken_dosage': total_taken_dosage,
            'days_with_medication': days_with_medication,
            'completion_percentage': (total_taken_quantity / total_planned_quantity * 100) if total_planned_quantity > 0 else 0
        }

    # ---------- Методы работы с сущностью "препарат" ----------

    def create_medication(self, name: str, description: Optional[str] = None) -> Optional[int]:
        """Создать новый препарат и вернуть его id"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO medications (name, description, created_at, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (name, description, now),
            )
            med_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return med_id
        except Exception as e:
            print(f"Ошибка при создании препарата: {e}")
            return None

    def get_medications(self) -> List[Tuple]:
        """Получить список активных препаратов"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description
            FROM medications
            WHERE is_active = 1
            ORDER BY id
            """
        )
        meds = cursor.fetchall()
        conn.close()
        return meds

    def get_medication(self, medication_id: int) -> Optional[Tuple]:
        """Получить информацию о конкретном препарате"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, description
            FROM medications
            WHERE id = ? AND is_active = 1
            """,
            (medication_id,),
        )
        med = cursor.fetchone()
        conn.close()
        return med

    def get_total_statistics(self, medication_id: int = 1) -> dict:
        """Получить общую статистику за все время по конкретному препарату"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT date) as total_days,
                SUM(quantity) as total_quantity,
                SUM(quantity * dosage_mg) as total_dosage_mg
            FROM medication_log
            WHERE medication_id = ?
        """, (medication_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] is not None:
            return {
                'total_days': result[0],
                'total_quantity': result[1] or 0,
                'total_dosage_mg': result[2] or 0
            }
        else:
            return {
                'total_days': 0,
                'total_quantity': 0,
                'total_dosage_mg': 0
            }

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
        
        # Таблица для хранения информации о приемах
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medication_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                dosage_mg REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Таблица для хранения настроек напоминаний
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
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
                updated_at TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()

    def add_medication(self, quantity: int, dosage_mg: float) -> bool:
        """Добавить запись о приеме препарата"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now = datetime.now()
            
            cursor.execute("""
                INSERT INTO medication_log (date, time, quantity, dosage_mg, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                quantity,
                dosage_mg,
                now.isoformat()
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении записи: {e}")
            return False

    def get_today_medications(self) -> List[Tuple]:
        """Получить все приемы за сегодня"""
        conn = self.get_connection()
        cursor = conn.cursor()
        today = date.today().strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT time, quantity, dosage_mg
            FROM medication_log
            WHERE date = ?
            ORDER BY time
        """, (today,))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def get_medications_by_date(self, target_date: date) -> List[Tuple]:
        """Получить все приемы за указанную дату"""
        conn = self.get_connection()
        cursor = conn.cursor()
        date_str = target_date.strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT time, quantity, dosage_mg
            FROM medication_log
            WHERE date = ?
            ORDER BY time
        """, (date_str,))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def get_medications_summary(self, days: int = 7) -> dict:
        """Получить сводку за последние N дней"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT date, 
                   SUM(quantity) as total_quantity,
                   SUM(quantity * dosage_mg) as total_dosage_mg
            FROM medication_log
            WHERE date >= date('now', '-' || ? || ' days')
            GROUP BY date
            ORDER BY date DESC
        """, (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        summary = {}
        for row in results:
            summary[row[0]] = {
                'quantity': row[1],
                'total_dosage_mg': row[2]
            }
        
        return summary

    def get_total_statistics(self) -> dict:
        """Получить общую статистику за все время"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Получаем общее количество дней с приемами и общее количество таблеток
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT date) as total_days,
                SUM(quantity) as total_quantity,
                SUM(quantity * dosage_mg) as total_dosage_mg
            FROM medication_log
        """)
        
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

    def add_reminder(self, time_str: str) -> bool:
        """Добавить напоминание"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now = datetime.now()
            
            cursor.execute("""
                INSERT INTO reminders (time, enabled, created_at)
                VALUES (?, 1, ?)
            """, (time_str, now.isoformat()))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при добавлении напоминания: {e}")
            return False

    def get_reminders(self) -> List[Tuple]:
        """Получить все активные напоминания"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, time
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

    def get_all_medications(self, days: int = None) -> List[Tuple]:
        """Получить все записи о приеме препарата"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if days:
            cursor.execute("""
                SELECT date, time, quantity, dosage_mg, created_at
                FROM medication_log
                WHERE date >= date('now', '-' || ? || ' days')
                ORDER BY date DESC, time DESC
            """, (days,))
        else:
            cursor.execute("""
                SELECT date, time, quantity, dosage_mg, created_at
                FROM medication_log
                ORDER BY date DESC, time DESC
            """)
        
        results = cursor.fetchall()
        conn.close()
        return results

    def generate_statistics_csv(self, file_path: str, days: int = 30) -> bool:
        """Генерировать CSV файл со статистикой"""
        try:
            import csv
            medications = self.get_all_medications(days=days)
            
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

    def set_course_settings(self, daily_quantity: int, dosage_mg: float, start_date: str = None, end_date: str = None) -> bool:
        """Установить настройки курса"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now = datetime.now()
            
            # Деактивируем предыдущие настройки
            cursor.execute("""
                UPDATE course_settings
                SET is_active = 0
                WHERE is_active = 1
            """)
            
            # Если дата начала не указана, используем сегодня
            if start_date is None:
                start_date = date.today().strftime("%Y-%m-%d")
            
            # Добавляем новые настройки
            cursor.execute("""
                INSERT INTO course_settings (daily_quantity, dosage_mg, start_date, end_date, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (daily_quantity, dosage_mg, start_date, end_date, now.isoformat(), now.isoformat()))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Ошибка при установке настроек курса: {e}")
            return False

    def get_active_course_settings(self) -> Optional[Tuple]:
        """Получить активные настройки курса"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, daily_quantity, dosage_mg, start_date, end_date, created_at
            FROM course_settings
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        conn.close()
        return result

    def get_course_progress(self) -> dict:
        """Получить прогресс курса"""
        settings = self.get_active_course_settings()
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
            WHERE date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date
        """, (start_date_str, today.strftime("%Y-%m-%d")))
        
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

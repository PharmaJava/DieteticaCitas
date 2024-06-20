import os
import pickle
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from tkcalendar import DateEntry, Calendar
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from database_setup import init_db, get_stored_session, store_session, clear_session

SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google():
    creds = None
    flow = InstalledAppFlow.from_client_config({
        "installed": {
            "client_id": "370930727035-20f67n22rpj38cgq28612ecu20p5mhc5.apps.googleusercontent.com",
            "project_id": "tactile-octagon-394207",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "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",
            "redirect_uris": ["http://localhost"]
        }
    }, SCOPES)
    creds = flow.run_local_server(port=0)
    service = build('calendar', 'v3', credentials=creds)
    return service

def add_event_to_google_calendar(service, title, date, time, description):
    start_datetime = f"{date}T{time}:00"
    end_datetime = (datetime.strptime(start_datetime, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    event = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_datetime,
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_datetime,
            'timeZone': 'UTC',
        },
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event

def fetch_google_calendar_events(service, month, year):
    start_time = datetime(year, month, 1).isoformat() + 'Z'
    end_time = (datetime(year, month + 1, 1) - timedelta(seconds=1)).isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary', timeMin=start_time, timeMax=end_time, singleEvents=True,
        orderBy='startTime').execute()
    return events_result.get('items', [])

class DietDetailsWindow(tk.Toplevel):
    def __init__(self, parent, client_id, db_name, refresh_callback, diet_id=None):
        super().__init__(parent)
        self.client_id = client_id
        self.db_name = db_name
        self.refresh_callback = refresh_callback
        self.diet_id = diet_id
        self.title("Dieta")
        self.geometry("400x300")
        self.configure(bg='#b3e7dc')
        self.create_widgets()
        if self.diet_id:
            self.load_diet()

    def create_widgets(self):
        tk.Label(self, text="Dieta:", bg='#b3e7dc').grid(row=0, column=0, padx=10, pady=10)
        self.diet_text = tk.Text(self, height=10, width=30)
        self.diet_text.grid(row=1, column=0, padx=10, pady=10)

        self.save_button = tk.Button(self, text="Guardar", command=self.save_diet)
        self.save_button.grid(row=2, column=0, padx=10, pady=10)

    def load_diet(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT diet FROM diets WHERE id=?", (self.diet_id,))
        diet = c.fetchone()
        conn.close()
        if diet:
            self.diet_text.insert(tk.END, diet[0])

    def save_diet(self):
        diet = self.diet_text.get("1.0", tk.END).strip()
        if diet:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            if self.diet_id:
                c.execute("UPDATE diets SET diet=? WHERE id=?", (diet, self.diet_id))
            else:
                c.execute("INSERT INTO diets (client_id, date, diet) VALUES (?, ?, ?)", 
                          (self.client_id, datetime.now().strftime('%d/%m/%Y'), diet))
            conn.commit()
            conn.close()
            messagebox.showinfo("Éxito", "Dieta guardada exitosamente!")
            self.refresh_callback()
            self.destroy()
        else:
            messagebox.showwarning("Error", "Por favor, ingrese la dieta.")

class AppointmentDetailsWindow(tk.Toplevel):
    def __init__(self, parent, appointment, db_name):
        super().__init__(parent)
        self.appointment = appointment
        self.db_name = db_name
        self.title("Detalles de la Cita")
        self.geometry("400x300")
        self.configure(bg='#b3e7dc')
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="Fecha:", bg='#b3e7dc').grid(row=0, column=0, padx=10, pady=5)
        tk.Label(self, text=self.appointment[0], bg='#b3e7dc').grid(row=0, column=1, padx=10, pady=5)

        tk.Label(self, text="Hora:", bg='#b3e7dc').grid(row=1, column=0, padx=10, pady=5)
        tk.Label(self, text=self.appointment[1], bg='#b3e7dc').grid(row=1, column=1, padx=10, pady=5)

        tk.Label(self, text="Descripción:", bg='#b3e7dc').grid(row=2, column=0, padx=10, pady=5)
        tk.Label(self, text=self.appointment[2], bg='#b3e7dc').grid(row=2, column=1, padx=10, pady=5)

        tk.Button(self, text="Borrar Cita", command=self.delete_appointment).grid(row=3, column=0, columnspan=2, pady=10)

    def delete_appointment(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("DELETE FROM appointments WHERE date=? AND time=? AND description=?", self.appointment)
        conn.commit()
        conn.close()
        messagebox.showinfo("Éxito", "Cita borrada exitosamente!")
        self.destroy()

class ClientDetailsWindow(tk.Toplevel):
    def __init__(self, parent, client_id, db_name):
        super().__init__(parent)
        self.client_id = client_id
        self.db_name = db_name
        self.title("Detalles del Cliente")
        self.geometry("800x600")
        self.configure(bg='#b3e7dc')
        self.create_widgets()
        self.load_client_details()
        self.load_appointments()
        self.load_diets()

    def create_widgets(self):
        tk.Label(self, text="Nombre:", bg='#b3e7dc').grid(row=0, column=0, padx=10, pady=5)
        self.name_entry = tk.Entry(self)
        self.name_entry.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(self, text="Apellidos:", bg='#b3e7dc').grid(row=1, column=0, padx=10, pady=5)
        self.surname_entry = tk.Entry(self)
        self.surname_entry.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(self, text="Dirección:", bg='#b3e7dc').grid(row=2, column=0, padx=10, pady=5)
        self.address_entry = tk.Entry(self)
        self.address_entry.grid(row=2, column=1, padx=10, pady=5)

        tk.Label(self, text="Teléfono:", bg='#b3e7dc').grid(row=3, column=0, padx=10, pady=5)
        self.phone_entry = tk.Entry(self)
        self.phone_entry.grid(row=3, column=1, padx=10, pady=5)

        tk.Label(self, text="Email:", bg='#b3e7dc').grid(row=4, column=0, padx=10, pady=5)
        self.email_entry = tk.Entry(self)
        self.email_entry.grid(row=4, column=1, padx=10, pady=5)

        tk.Label(self, text="Dietas:", bg='#b3e7dc').grid(row=5, column=0, padx=10, pady=5)
        self.diets_listbox = tk.Listbox(self)
        self.diets_listbox.grid(row=5, column=1, padx=10, pady=5)
        self.diets_listbox.bind('<Double-1>', self.view_diet)

        self.add_diet_button = tk.Button(self, text="Nueva Dieta", command=self.add_diet)
        self.add_diet_button.grid(row=6, column=0, columnspan=2, pady=10)

        self.save_button = tk.Button(self, text="Guardar", command=self.save_client_details)
        self.save_button.grid(row=7, column=0, columnspan=2, pady=10)

        tk.Label(self, text="Citas:", bg='#b3e7dc').grid(row=5, column=2, padx=10, pady=5)
        self.appointments_listbox = tk.Listbox(self)
        self.appointments_listbox.grid(row=5, column=3, padx=10, pady=5)
        self.appointments_listbox.bind('<Double-1>', self.view_appointment)

        self.add_appointment_button = tk.Button(self, text="Agregar Cita", command=self.add_appointment_offline)
        self.add_appointment_button.grid(row=6, column=2, columnspan=2, pady=10)

        tk.Label(self, text="Fecha (dd/mm/yyyy):", bg='#b3e7dc').grid(row=7, column=2, padx=10, pady=5)
        self.date_entry = DateEntry(self, date_pattern='dd/mm/yyyy')
        self.date_entry.grid(row=7, column=3, padx=10, pady=5)

        tk.Label(self, text="Hora (HH:MM):", bg='#b3e7dc').grid(row=8, column=2, padx=10, pady=5)
        self.time_entry = ttk.Spinbox(self, from_=0, to=23, format="%02.0f", increment=1, width=5)
        self.time_entry.grid(row=8, column=3, padx=10, pady=5)
        self.time_entry.insert(0, "00")

        self.minute_entry = ttk.Spinbox(self, from_=0, to=59, format="%02.0f", increment=1, width=5)
        self.minute_entry.grid(row=8, column=4, padx=10, pady=5)
        self.minute_entry.insert(0, "00")

        tk.Label(self, text="Descripción:", bg='#b3e7dc').grid(row=9, column=2, padx=10, pady=5)
        self.description_entry = tk.Entry(self)
        self.description_entry.grid(row=9, column=3, padx=10, pady=5)

    def load_client_details(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT name, surname, address, phone, email FROM clients WHERE id=?", (self.client_id,))
        client = c.fetchone()
        conn.close()
        if client:
            self.name_entry.insert(0, client[0])
            self.surname_entry.insert(0, client[1])
            self.address_entry.insert(0, client[2])
            self.phone_entry.insert(0, client[3])
            self.email_entry.insert(0, client[4])

    def save_client_details(self):
        name = self.name_entry.get()
        surname = self.surname_entry.get()
        address = self.address_entry.get()
        phone = self.phone_entry.get()
        email = self.email_entry.get()
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        if self.client_id:
            c.execute("UPDATE clients SET name=?, surname=?, address=?, phone=?, email=? WHERE id=?", 
                      (name, surname, address, phone, email, self.client_id))
        else:
            c.execute("INSERT INTO clients (name, surname, address, phone, email) VALUES (?, ?, ?, ?, ?)", 
                      (name, surname, address, phone, email))
            self.client_id = c.lastrowid
        conn.commit()
        conn.close()
        messagebox.showinfo("Éxito", "Detalles del cliente guardados exitosamente!")
        self.load_diets()
        self.load_appointments()

    def load_appointments(self):
        self.appointments_listbox.delete(0, tk.END)
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT date, time, description FROM appointments WHERE client_id=?", (self.client_id,))
        appointments = c.fetchall()
        conn.close()
        for appointment in appointments:
            self.appointments_listbox.insert(tk.END, f"{appointment[0]} {appointment[1]} - {appointment[2]}")

    def load_diets(self):
        self.diets_listbox.delete(0, tk.END)
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT id, date, diet FROM diets WHERE client_id=?", (self.client_id,))
        diets = c.fetchall()
        conn.close()
        for diet in diets:
            self.diets_listbox.insert(tk.END, f"{diet[0]} - {diet[1]}")

    def add_diet(self):
        DietDetailsWindow(self, self.client_id, self.db_name, self.load_diets)

    def view_diet(self, event):
        selection = self.diets_listbox.curselection()
        if selection:
            diet_id = int(self.diets_listbox.get(selection[0]).split(' ')[0])
            DietDetailsWindow(self, self.client_id, self.db_name, self.load_diets, diet_id)

    def view_appointment(self, event):
        selection = self.appointments_listbox.curselection()
        if selection:
            appointment = self.appointments_listbox.get(selection[0]).split(' - ')
            appointment_date, appointment_time = appointment[0].split(' ')
            appointment_description = appointment[1]
            AppointmentDetailsWindow(self, (appointment_date, appointment_time, appointment_description), self.db_name)

    def add_appointment_offline(self):
        date = self.date_entry.get()
        time = f"{self.time_entry.get()}:{self.minute_entry.get()}"
        description = self.description_entry.get()

        if date and time and description:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("INSERT INTO appointments (client_id, date, time, description) VALUES (?, ?, ?, ?)", 
                      (self.client_id, datetime.strptime(date, '%d/%m/%Y').strftime('%Y-%m-%d'), time, description))
            conn.commit()
            conn.close()
            messagebox.showinfo("Éxito", "Cita offline agregada exitosamente!")
            self.load_appointments()
        else:
            messagebox.showwarning("Error", "Por favor, complete todos los campos.")

class AppointmentApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestor de Citas Dietéticas")
        self.root.geometry("900x600")
        self.root.configure(bg='#b3e7dc')

        self.logged_in_user = None
        self.google_service = None
        self.db_name = 'appointments.db'

        self.create_widgets()
        self.check_session()

    def create_widgets(self):
        main_frame = tk.Frame(self.root, padx=20, pady=20, bg='#b3e7dc')
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.login_button = tk.Button(main_frame, text="Iniciar Sesión con Google", command=self.login)
        self.login_button.grid(row=0, column=0, columnspan=2, pady=10)

        self.logout_button = tk.Button(main_frame, text="Cerrar Sesión", command=self.logout)
        self.logout_button.grid(row=0, column=2, columnspan=2, pady=10)
        self.logout_button.grid_remove()

        self.greeting_label = tk.Label(main_frame, text="", bg='#b3e7dc')
        self.greeting_label.grid(row=1, column=0, columnspan=4, pady=10)

        self.calendar = Calendar(main_frame, selectmode='day', date_pattern='dd/mm/yyyy')
        self.calendar.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
        self.load_offline_appointments()
        self.calendar.bind("<<CalendarSelected>>", self.view_day_appointments)

        self.sync_button = tk.Button(main_frame, text="Sincronizar Calendario", command=self.sync_calendar)
        self.sync_button.grid(row=3, column=0, columnspan=2, pady=10)

        self.download_button = tk.Button(main_frame, text="Descargar Calendario", command=self.download_calendar)
        self.download_button.grid(row=3, column=2, columnspan=2, pady=10)

        tk.Label(main_frame, text="Nombre del Cliente:", bg='#b3e7dc').grid(row=4, column=0, padx=10, pady=5)
        self.client_name_entry = tk.Entry(main_frame)
        self.client_name_entry.grid(row=4, column=1, padx=10, pady=5)
        self.client_name_entry.bind('<KeyRelease>', self.search_client)

        tk.Label(main_frame, text="Fecha (dd/mm/yyyy):", bg='#b3e7dc').grid(row=5, column=0, padx=10, pady=5)
        self.date_entry = DateEntry(main_frame, date_pattern='dd/mm/yyyy')
        self.date_entry.grid(row=5, column=1, padx=10, pady=5)

        tk.Label(main_frame, text="Hora (HH:MM):", bg='#b3e7dc').grid(row=6, column=0, padx=10, pady=5)
        self.time_entry = ttk.Spinbox(main_frame, from_=0, to=23, format="%02.0f", increment=1, width=5)
        self.time_entry.grid(row=6, column=1, padx=10, pady=5)
        self.time_entry.insert(0, "00")

        self.minute_entry = ttk.Spinbox(main_frame, from_=0, to=59, format="%02.0f", increment=1, width=5)
        self.minute_entry.grid(row=6, column=2, padx=10, pady=5)
        self.minute_entry.insert(0, "00")

        tk.Label(main_frame, text="Descripción:", bg='#b3e7dc').grid(row=7, column=0, padx=10, pady=5)
        self.description_entry = tk.Entry(main_frame)
        self.description_entry.grid(row=7, column=1, padx=10, pady=5)

        tk.Button(main_frame, text="Agregar Cita", command=self.add_appointment).grid(row=8, column=0, columnspan=2, pady=10)
        tk.Button(main_frame, text="Agregar Cita Offline", command=self.add_appointment_offline).grid(row=8, column=2, columnspan=2, pady=10)
        tk.Button(main_frame, text="Crear Cliente", command=self.create_client).grid(row=9, column=0, columnspan=2, pady=10)
        tk.Button(main_frame, text="Buscar Cliente", command=self.search_client_by_name).grid(row=9, column=2, columnspan=2, pady=10)

        self.hide_list_button = tk.Button(main_frame, text="Ocultar Lista", command=self.hide_client_list)
        self.hide_list_button.grid(row=10, column=2, columnspan=2, pady=10)
        self.hide_list_button.grid_remove()

        self.client_listbox = tk.Listbox(main_frame)
        self.client_listbox.grid(row=2, column=3, rowspan=7, padx=10, pady=10, sticky="nsew")
        self.client_listbox.bind('<<ListboxSelect>>', self.show_client_details)
        self.client_listbox.grid_remove()  # Ocultar inicialmente

    def view_day_appointments(self, event):
        selected_date = self.calendar.selection_get()
        appointments = self.get_appointments_by_date(selected_date)
        DayAppointmentsWindow(self.root, selected_date, appointments, self.db_name)

    def get_appointments_by_date(self, date):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT time, description FROM appointments WHERE date=?", (date.strftime('%Y-%m-%d'),))
        appointments = c.fetchall()
        conn.close()
        return appointments

    def check_session(self):
        session = get_stored_session()
        if session:
            email, token = session
            self.logged_in_user = email
            self.google_service = authenticate_google()
            self.greeting_label.config(text=f"Hola, {self.logged_in_user}")
            self.login_button.grid_remove()
            self.logout_button.grid()

    def login(self):
        self.google_service = authenticate_google()
        self.logged_in_user = self.google_service._id_token
        self.greeting_label.config(text=f"Hola, {self.logged_in_user}")
        self.login_button.grid_remove()
        self.logout_button.grid()
        store_session(self.logged_in_user, self.google_service)

    def logout(self):
        clear_session()
        self.logged_in_user = None
        self.greeting_label.config(text="")
        self.logout_button.grid_remove()
        self.login_button.grid()

    def search_client(self, event):
        search_term = self.client_name_entry.get()
        self.client_listbox.delete(0, tk.END)
        self.client_listbox.grid()
        self.hide_list_button.grid()
        if search_term:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT id, name FROM clients WHERE name LIKE ?", ('%' + search_term + '%',))
            clients = c.fetchall()
            for client in clients:
                self.client_listbox.insert(tk.END, f"{client[0]}: {client[1]}")
            conn.close()

    def show_client_details(self, event):
        selection = self.client_listbox.curselection()
        if selection:
            client_id = int(self.client_listbox.get(selection[0]).split(':')[0])
            ClientDetailsWindow(self.root, client_id, self.db_name)

    def hide_client_list(self):
        self.client_listbox.grid_remove()
        self.hide_list_button.grid_remove()

    def add_appointment(self):
        client_name = self.client_name_entry.get()
        date = self.date_entry.get()
        time = f"{self.time_entry.get()}:{self.minute_entry.get()}"
        description = self.description_entry.get()

        if client_name and date and time:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT id FROM clients WHERE name=?", (client_name,))
            client = c.fetchone()
            if not client:
                c.execute("INSERT INTO clients (name) VALUES (?)", (client_name,))
                conn.commit()
                client_id = c.lastrowid
            else:
                client_id = client[0]
            c.execute("INSERT INTO appointments (client_id, date, time, description) VALUES (?, ?, ?, ?)", 
                      (client_id, datetime.strptime(date, '%d/%m/%Y').strftime('%Y-%m-%d'), time, description))
            conn.commit()
            conn.close()

            # Add to Google Calendar
            if not self.google_service:
                self.google_service = authenticate_google()
            event = add_event_to_google_calendar(self.google_service, client_name, datetime.strptime(date, '%d/%m/%Y').strftime('%Y-%m-%d'), time, description)
            google_event_id = event['id']

            # Update appointment with Google Event ID
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("UPDATE appointments SET google_event_id=? WHERE id=?", (google_event_id, c.lastrowid))
            conn.commit()
            conn.close()

            messagebox.showinfo("Éxito", "Cita agregada exitosamente!")
            self.clear_entries()
            self.load_offline_appointments()  # Refresh the calendar
        else:
            messagebox.showwarning("Error", "Por favor, complete todos los campos.")

    def add_appointment_offline(self):
        client_name = self.client_name_entry.get()
        date = self.date_entry.get()
        time = f"{self.time_entry.get()}:{self.minute_entry.get()}"
        description = self.description_entry.get()

        if client_name and date and time:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT id FROM clients WHERE name=?", (client_name,))
            client = c.fetchone()
            if not client:
                c.execute("INSERT INTO clients (name) VALUES (?)", (client_name,))
                conn.commit()
                client_id = c.lastrowid
            else:
                client_id = client[0]
            c.execute("INSERT INTO appointments (client_id, date, time, description) VALUES (?, ?, ?, ?)", 
                      (client_id, datetime.strptime(date, '%d/%m/%Y').strftime('%Y-%m-%d'), time, description))
            conn.commit()
            conn.close()

            messagebox.showinfo("Éxito", "Cita offline agregada exitosamente!")
            self.clear_entries()
            self.load_offline_appointments()  # Refresh the calendar
        else:
            messagebox.showwarning("Error", "Por favor, complete todos los campos.")

    def create_client(self):
        ClientDetailsWindow(self.root, None, self.db_name)

    def search_client_by_name(self):
        self.client_listbox.delete(0, tk.END)
        self.client_listbox.grid()
        self.hide_list_button.grid()
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT id, name FROM clients")
        clients = c.fetchall()
        for client in clients:
            self.client_listbox.insert(tk.END, f"{client[0]}: {client[1]}")
        conn.close()

    def clear_entries(self):
        self.client_name_entry.delete(0, tk.END)
        self.date_entry.set_date(datetime.today())
        self.time_entry.set("00")
        self.minute_entry.set("00")
        self.description_entry.delete(0, tk.END)

    def load_offline_appointments(self):
        self.calendar.calevent_remove('all')
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT date FROM appointments")
        appointments = c.fetchall()
        conn.close()
        for appointment in appointments:
            date = datetime.strptime(appointment[0], '%Y-%m-%d').strftime('%d/%m/%Y')
            self.calendar.calevent_create(datetime.strptime(date, '%d/%m/%Y'), 'Appointment', 'appointment')
        self.calendar.tag_config('appointment', background='yellow', foreground='black')

    def sync_calendar(self):
        if not self.google_service:
            messagebox.showwarning("Error", "Por favor, inicie sesión con Google primero.")
            return

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT id, client_id, date, time, description FROM appointments WHERE google_event_id IS NULL")
        appointments = c.fetchall()
        for appointment in appointments:
            _, client_id, date, time, description = appointment
            c.execute("SELECT name FROM clients WHERE id=?", (client_id,))
            client_name = c.fetchone()[0]
            event = add_event_to_google_calendar(self.google_service, client_name, date, time, description)
            google_event_id = event['id']
            c.execute("UPDATE appointments SET google_event_id=? WHERE id=?", (google_event_id, appointment[0]))
        conn.commit()
        conn.close()
        messagebox.showinfo("Éxito", "Calendario sincronizado exitosamente!")

    def download_calendar(self):
        if not self.google_service:
            messagebox.showwarning("Error", "Por favor, inicie sesión con Google primero.")
            return

        now = datetime.utcnow()
        month = now.month
        year = now.year
        events = fetch_google_calendar_events(self.google_service, month, year)

        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            date, time = start.split('T')
            time = time.split('+')[0]
            description = event.get('summary', '')
            google_event_id = event['id']
            c.execute("SELECT id FROM appointments WHERE google_event_id=?", (google_event_id,))
            existing_event = c.fetchone()
            if not existing_event:
                c.execute("INSERT INTO appointments (client_id, date, time, description, google_event_id) VALUES (?, ?, ?, ?, ?)", 
                          (None, date, time, description, google_event_id))
        conn.commit()
        conn.close()
        messagebox.showinfo("Éxito", "Calendario descargado exitosamente!")
        self.load_offline_appointments()

class DayAppointmentsWindow(tk.Toplevel):
    def __init__(self, parent, date, appointments, db_name):
        super().__init__(parent)
        self.date = date
        self.db_name = db_name
        self.title(f"Citas para {date.strftime('%d/%m/%Y')}")
        self.geometry("400x400")
        self.configure(bg='#b3e7dc')
        self.create_widgets(appointments)

    def create_widgets(self, appointments):
        self.appointments_listbox = tk.Listbox(self)
        self.appointments_listbox.grid(row=0, column=0, padx=10, pady=10)
        for appointment in appointments:
            self.appointments_listbox.insert(tk.END, f"{appointment[0]} - {appointment[1]}")
        self.appointments_listbox.bind('<Double-1>', self.view_appointment_details)

        tk.Label(self, text="Descripción:", bg='#b3e7dc').grid(row=1, column=0, padx=10, pady=5)
        self.description_entry = tk.Entry(self)
        self.description_entry.grid(row=2, column=0, padx=10, pady=5)

        tk.Label(self, text="Hora (HH:MM):", bg='#b3e7dc').grid(row=3, column=0, padx=10, pady=5)
        self.time_entry = ttk.Spinbox(self, from_=0, to=23, format="%02.0f", increment=1, width=5)
        self.time_entry.grid(row=4, column=0, padx=10, pady=5)
        self.time_entry.insert(0, "00")

        self.minute_entry = ttk.Spinbox(self, from_=0, to=59, format="%02.0f", increment=1, width=5)
        self.minute_entry.grid(row=5, column=0, padx=10, pady=5)
        self.minute_entry.insert(0, "00")

        self.add_appointment_button = tk.Button(self, text="Agregar Cita", command=self.add_appointment)
        self.add_appointment_button.grid(row=6, column=0, padx=10, pady=10)
        self.delete_appointment_button = tk.Button(self, text="Borrar Cita", command=self.delete_appointment)
        self.delete_appointment_button.grid(row=7, column=0, padx=10, pady=10)

    def add_appointment(self):
        description = self.description_entry.get()
        time = f"{self.time_entry.get()}:{self.minute_entry.get()}"

        if description and time:
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("INSERT INTO appointments (client_id, date, time, description) VALUES (?, ?, ?, ?)", 
                      (None, self.date.strftime('%Y-%m-%d'), time, description))
            conn.commit()
            conn.close()
            messagebox.showinfo("Éxito", "Cita agregada exitosamente!")
            self.destroy()
        else:
            messagebox.showwarning("Error", "Por favor, complete todos los campos.")

    def delete_appointment(self):
        selection = self.appointments_listbox.curselection()
        if selection:
            appointment = self.appointments_listbox.get(selection[0]).split(' - ')
            appointment_time = appointment[0]
            appointment_description = appointment[1]
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("DELETE FROM appointments WHERE time=? AND description=?", (appointment_time, appointment_description))
            conn.commit()
            conn.close()
            messagebox.showinfo("Éxito", "Cita borrada exitosamente!")
            self.destroy()

    def view_appointment_details(self, event):
        selection = self.appointments_listbox.curselection()
        if selection:
            appointment = self.appointments_listbox.get(selection[0]).split(' - ')
            appointment_time = appointment[0]
            appointment_description = appointment[1]
            conn = sqlite3.connect(self.db_name)
            c = conn.cursor()
            c.execute("SELECT clients.name FROM appointments JOIN clients ON appointments.client_id = clients.id WHERE appointments.time = ? AND appointments.description = ?", 
                      (appointment_time, appointment_description))
            client_name = c.fetchone()
            conn.close()
            if client_name:
                messagebox.showinfo("Detalles de la Cita", f"Cliente: {client_name[0]}")

if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = AppointmentApp(root)
    root.mainloop()

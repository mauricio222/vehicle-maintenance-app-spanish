from flask_app import get_db_connection

with get_db_connection() as conn:
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS Detalle_Vehiculo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            anio INTEGER NOT NULL,
            tipo TEXT,
            tipo_motor TEXT,
            tipo_transmision TEXT
        );
        
        CREATE TABLE IF NOT EXISTS Vehiculo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL,
            detalle_id INTEGER,
            FOREIGN KEY (detalle_id) REFERENCES Detalle_Vehiculo(id)
        );
        
        CREATE TABLE IF NOT EXISTS Mecánico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_mecanico TEXT NOT NULL,
            telefono_mecanico TEXT
        );
        
        CREATE TABLE IF NOT EXISTS Tipo_Mantenimiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            categoria TEXT NOT NULL,
            meses_proximo_mantenimiento INTEGER,
            kilometros_proximo_mantenimiento INTEGER,
            vehiculo_detalle_id INTEGER NOT NULL,
            FOREIGN KEY (vehiculo_detalle_id) REFERENCES Detalle_Vehiculo(id)
        );
        
        CREATE TABLE IF NOT EXISTS Kilometraje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehiculo_id INTEGER,
            fecha DATE NOT NULL,
            kilometraje INTEGER NOT NULL,
            FOREIGN KEY (vehiculo_id) REFERENCES Vehiculo(id)
        );
        
        CREATE TABLE IF NOT EXISTS Mantenimiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehiculo_id INTEGER,
            tipo_mantenimiento_id INTEGER,
            kilometraje_id INTEGER,
            mecanico_id INTEGER,
            fecha_proximo_mantenimiento DATE,
            precio REAL,
            FOREIGN KEY (vehiculo_id) REFERENCES Vehiculo(id),
            FOREIGN KEY (tipo_mantenimiento_id) REFERENCES Tipo_Mantenimiento(id),
            FOREIGN KEY (kilometraje_id) REFERENCES Kilometraje(id),
            FOREIGN KEY (mecanico_id) REFERENCES Mecánico(id)
        );

        CREATE TABLE IF NOT EXISTS Usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    ''')
    conn.commit()
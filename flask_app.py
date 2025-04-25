from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session, g
import sqlite3
from datetime import datetime
import pytz
import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash
import functools

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')  # Must be set in .env
app.config['JSON_AS_ASCII'] = False  # Add this for proper encoding

DB_PATH = Path(os.environ.get('DB_PATH', 'mantenimiento.db'))

# Configure Gemini (add your API key in environment variables)
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def get_cr_time():
    cr_tz = pytz.timezone('America/Costa_Rica')
    return datetime.now(cr_tz)

# Function to load user before each request
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        g.user = conn.execute(
            'SELECT * FROM Usuario WHERE id = ?', (user_id,)
        ).fetchone()
        conn.close()

# Decorator for routes that require login
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

@app.route('/')
# @login_required # Removed decorator
def index():
    # Always redirect to login page when accessing the root
    return redirect(url_for('login'))
    # Original index logic removed:
    # conn = get_db_connection()
    # vehiculos = conn.execute('''
    #     SELECT v.id, v.alias, d.marca, d.modelo, d.anio
    #     FROM Vehiculo v
    #     JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
    # ''').fetchall()
    #
    # # Fetch mechanics for the new section
    # mecanicos = conn.execute('SELECT * FROM Mecánico ORDER BY nombre_mecanico').fetchall()
    #
    # conn.close()
    # return render_template('index.html', vehiculos=vehiculos, mecanicos=mecanicos)

@app.route('/dashboard')
@login_required
def dashboard():
    # This is the new route for the main page after login
    conn = get_db_connection()
    vehiculos = conn.execute('''
        SELECT v.id, v.alias, d.marca, d.modelo, d.anio
        FROM Vehiculo v
        JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
    ''').fetchall()

    # Fetch mechanics for the new section
    mecanicos = conn.execute('SELECT * FROM Mecánico ORDER BY nombre_mecanico').fetchall()

    conn.close()
    return render_template('index.html', vehiculos=vehiculos, mecanicos=mecanicos)

@app.route('/registro')
@login_required
def registro():
    conn = get_db_connection()
    vehiculos = conn.execute('''
        SELECT v.id, v.alias, d.marca, d.modelo, d.anio, d.id as detalle_id
        FROM Vehiculo v
        JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
    ''').fetchall()
    mecanicos = conn.execute('SELECT * FROM Mecánico').fetchall()
    conn.close()
    return render_template('mantenimiento_registro.html', vehiculos=vehiculos, mecanicos=mecanicos)

@app.route('/mantenimientos/<int:vehiculo_id>')
@login_required
def ver_mantenimientos(vehiculo_id):
    conn = get_db_connection()
    vehiculos = conn.execute('''
        SELECT v.id, v.alias, d.marca, d.modelo, d.anio
        FROM Vehiculo v
        JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
    ''').fetchall()

    # Obtener información del vehículo
    vehiculo = conn.execute('''
        SELECT v.id, v.alias,
            (SELECT k.kilometraje
             FROM Kilometraje k
             WHERE k.vehiculo_id = v.id
             ORDER BY k.fecha DESC, k.id DESC
             LIMIT 1) as ultimo_kilometraje
        FROM Vehiculo v
        JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
        WHERE v.id = ?
    ''', (vehiculo_id,)).fetchone()

    # Obtener mantenimientos
    mantenimientos = conn.execute('''
        SELECT
            strftime('%d/%m/%Y', k.fecha) as fecha,
            k.fecha as fecha_iso,
            k.kilometraje,
            t.nombre as tipo_mantenimiento,
            t.categoria,
            m.nombre_mecanico as mecanico,
            man.precio,
            t.kilometros_proximo_mantenimiento,
            CASE
                WHEN man.fecha_proximo_mantenimiento IS NULL THEN ''
                ELSE strftime('%d/%m/%Y', man.fecha_proximo_mantenimiento)
            END as fecha_proximo,
            man.fecha_proximo_mantenimiento as fecha_proximo_iso,
            CASE
                WHEN t.kilometros_proximo_mantenimiento IS NOT NULL THEN
                k.kilometraje + t.kilometros_proximo_mantenimiento
                ELSE NULL
            END as proximo_km
        FROM Mantenimiento man
        JOIN Kilometraje k ON man.kilometraje_id = k.id
        JOIN Tipo_Mantenimiento t ON man.tipo_mantenimiento_id = t.id
        JOIN Mecánico m ON man.mecanico_id = m.id
        WHERE man.vehiculo_id = ?
        ORDER BY k.fecha DESC
    ''', (vehiculo_id,)).fetchall()

    # Obtener valores únicos para los filtros
    categorias_unicas = sorted(set(m['categoria'] for m in mantenimientos))
    tipos_unicos = sorted(set(m['tipo_mantenimiento'] for m in mantenimientos))
    mecanicos_unicos = sorted(set(m['mecanico'] for m in mantenimientos))

    conn.close()
    # Obtener fecha actual en formato ISO para comparación
    today_iso = get_cr_time().strftime('%Y-%m-%d')

    return render_template('mantenimientos.html',
                         vehiculos=vehiculos,
                         vehiculo=vehiculo,
                         mantenimientos=mantenimientos,
                         categorias_unicas=categorias_unicas,
                         tipos_unicos=tipos_unicos,
                         mecanicos_unicos=mecanicos_unicos,
                         today_iso=today_iso)

@app.route('/agregar_mecanico', methods=['POST'])
@login_required
def agregar_mecanico():
    nombre = request.form.get('nombre')
    telefono = request.form.get('telefono')

    conn = get_db_connection()
    try:
        # Verificar si ya existe un mecánico con el mismo nombre y teléfono
        mecanico_existente = conn.execute('''
            SELECT id
            FROM Mecánico
            WHERE nombre_mecanico = ? AND telefono_mecanico = ?
        ''', (nombre, telefono)).fetchone()

        if mecanico_existente:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Ya existe un mecánico con este nombre y teléfono'
            })

        conn.execute('INSERT INTO Mecánico (nombre_mecanico, telefono_mecanico) VALUES (?, ?)',
                    (nombre, telefono))
        conn.commit()
        nuevo_mecanico = conn.execute('SELECT * FROM Mecánico ORDER BY id DESC LIMIT 1').fetchone()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Mecánico agregado exitosamente',
            'mecanico': {
                'id': nuevo_mecanico['id'],
                'nombre': nuevo_mecanico['nombre_mecanico'],
                'telefono': nuevo_mecanico['telefono_mecanico']
            }
        })
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/agregar_tipo_mantenimiento', methods=['POST'])
@login_required
def agregar_tipo_mantenimiento():
    try:
        nombre = request.form.get('nombre')
        kilometros = request.form.get('kilometros') or None
        meses = request.form.get('meses') or None
        vehiculo_id = request.form.get('vehiculo_id')
        categoria = request.form.get('categoria')

        conn = get_db_connection()

        # Obtener el detalle_id del vehículo
        vehiculo = conn.execute('''
            SELECT d.id as detalle_id
            FROM Vehiculo v
            JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
            WHERE v.id = ?
        ''', (vehiculo_id,)).fetchone()

        if not vehiculo:
            conn.close()
            return jsonify({'success': False, 'error': 'Vehículo no encontrado'})

        # Verificar si ya existe un tipo de mantenimiento igual
        tipo_existente = conn.execute('''
            SELECT id
            FROM Tipo_Mantenimiento
            WHERE vehiculo_detalle_id = ?
            AND nombre = ?
            AND categoria = ?
            AND (
                (kilometros_proximo_mantenimiento IS NULL AND ? IS NULL) OR
                kilometros_proximo_mantenimiento = ?
            )
            AND (
                (meses_proximo_mantenimiento IS NULL AND ? IS NULL) OR
                meses_proximo_mantenimiento = ?
            )
        ''', (vehiculo['detalle_id'], nombre, categoria,
              kilometros, kilometros, meses, meses)).fetchone()

        if tipo_existente:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Ya existe un tipo de mantenimiento con estas características para este vehículo'
            })

        # Fix for the ID issue - ensure we're using INTEGER PRIMARY KEY AUTOINCREMENT
        # First, check if we need to fix the table structure
        table_info = conn.execute("PRAGMA table_info(Tipo_Mantenimiento)").fetchall()
        pk_column = next((col for col in table_info if col[5] == 1), None)

        if not pk_column:
            # Create a temporary table with proper structure
            conn.execute('''
                CREATE TABLE IF NOT EXISTS Tipo_Mantenimiento_temp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    kilometros_proximo_mantenimiento INTEGER,
                    meses_proximo_mantenimiento INTEGER,
                    vehiculo_detalle_id INTEGER NOT NULL,
                    categoria TEXT NOT NULL
                )
            ''')

            # Copy data from old table to new table
            conn.execute('''
                INSERT INTO Tipo_Mantenimiento_temp (id, nombre, kilometros_proximo_mantenimiento,
                                                   meses_proximo_mantenimiento, vehiculo_detalle_id, categoria)
                SELECT id, nombre, kilometros_proximo_mantenimiento,
                       meses_proximo_mantenimiento, vehiculo_detalle_id, categoria
                FROM Tipo_Mantenimiento
                WHERE id IS NOT NULL
            ''')

            # Insert rows with NULL id with new autoincremented ids
            conn.execute('''
                INSERT INTO Tipo_Mantenimiento_temp (nombre, kilometros_proximo_mantenimiento,
                                                   meses_proximo_mantenimiento, vehiculo_detalle_id, categoria)
                SELECT nombre, kilometros_proximo_mantenimiento,
                       meses_proximo_mantenimiento, vehiculo_detalle_id, categoria
                FROM Tipo_Mantenimiento
                WHERE id IS NULL
            ''')

            # Drop old table and rename new one
            conn.execute('DROP TABLE Tipo_Mantenimiento')
            conn.execute('ALTER TABLE Tipo_Mantenimiento_temp RENAME TO Tipo_Mantenimiento')
            conn.commit()

        # Now insert the new maintenance type
        conn.execute('''
            INSERT INTO Tipo_Mantenimiento
            (nombre, kilometros_proximo_mantenimiento, meses_proximo_mantenimiento,
             vehiculo_detalle_id, categoria)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, kilometros, meses, vehiculo['detalle_id'], categoria))
        conn.commit()

        nuevo_tipo = conn.execute('''
            SELECT * FROM Tipo_Mantenimiento ORDER BY id DESC LIMIT 1
        ''').fetchone()

        # Obtener los tipos de mantenimiento actualizados
        tipos = conn.execute('''
            SELECT id, nombre, categoria
            FROM Tipo_Mantenimiento
            WHERE vehiculo_detalle_id = ?
            ORDER BY categoria, nombre
        ''', (vehiculo['detalle_id'],)).fetchall()

        conn.close()

        return jsonify({
            'success': True,
            'nuevo_tipo_id': nuevo_tipo['id'],
            'tipo_mantenimiento': {
                'id': nuevo_tipo['id'],
                'nombre': nuevo_tipo['nombre'],
                'kilometros': nuevo_tipo['kilometros_proximo_mantenimiento'],
                'meses': nuevo_tipo['meses_proximo_mantenimiento'],
                'categoria': nuevo_tipo['categoria']
            },
            'tipos': [dict(tipo) for tipo in tipos]
        })
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_tipos_mantenimiento/<int:vehiculo_id>')
@login_required
def get_tipos_mantenimiento(vehiculo_id):
    conn = get_db_connection()
    # Primero obtenemos el detalle_id del vehículo
    vehiculo = conn.execute('''
        SELECT d.id as detalle_id
        FROM Vehiculo v
        JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
        WHERE v.id = ?
    ''', (vehiculo_id,)).fetchone()

    if vehiculo:
        # Obtenemos los tipos de mantenimiento para ese detalle_id
        tipos = conn.execute('''
            SELECT id, nombre, categoria
            FROM Tipo_Mantenimiento
            WHERE vehiculo_detalle_id = ?
            ORDER BY categoria, nombre
        ''', (vehiculo['detalle_id'],)).fetchall()

        conn.close()
        return jsonify({
            'success': True,
            'tipos': [dict(tipo) for tipo in tipos],
            'nuevo_tipo_id': request.args.get('nuevo_tipo_id')
        })

    conn.close()
    return jsonify({'success': False})

@app.route('/get_tipo_mantenimiento/<int:tipo_id>')
@login_required
def get_tipo_mantenimiento(tipo_id):
    conn = get_db_connection()
    tipo = conn.execute('''
        SELECT id, nombre, categoria,
               kilometros_proximo_mantenimiento,
               meses_proximo_mantenimiento
        FROM Tipo_Mantenimiento
        WHERE id = ?
    ''', (tipo_id,)).fetchone()
    conn.close()

    if tipo:
        return jsonify({
            'success': True,
            'tipo': dict(tipo)
        })
    return jsonify({'success': False})

@app.route('/guardar_mantenimiento', methods=['POST'])
@login_required
def guardar_mantenimiento():
    try:
        # Obtener datos del formulario
        vehiculo_id = request.form.get('vehiculo_id')
        fecha = request.form.get('fecha')
        # Asegurar que la fecha se guarde en la zona horaria de CR
        fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
        cr_tz = pytz.timezone('America/Costa_Rica')
        fecha = fecha_dt.replace(tzinfo=cr_tz).strftime('%Y-%m-%d')

        kilometraje = request.form.get('kilometraje')
        mecanico_id = request.form.get('mecanico_id')
        tipo_mantenimiento_id = request.form.get('tipo_mantenimiento_id')
        
        # Make price required and validate it's a positive number
        precio_str = request.form['precio']
        if not precio_str:
            return jsonify({
                'success': False,
                'error': 'El campo Precio es obligatorio.'
            })
        try:
            precio = float(precio_str)
            if precio <= 0:
                 return jsonify({
                    'success': False,
                    'error': 'El Precio debe ser un número positivo.'
                 })
        except ValueError:
             return jsonify({
                'success': False,
                'error': 'El Precio debe ser un número válido.'
             })

        conn = get_db_connection()

        # Verificar si ya existe el kilometraje para esa combinación
        kilometraje_existente = conn.execute('''
            SELECT id
            FROM Kilometraje
            WHERE vehiculo_id = ? AND fecha = ? AND kilometraje = ?
        ''', (vehiculo_id, fecha, kilometraje)).fetchone()

        if kilometraje_existente:
            kilometraje_id = kilometraje_existente['id']
        else:
            # Si no existe, insertamos el nuevo kilometraje
            conn.execute('''
                INSERT INTO Kilometraje (vehiculo_id, fecha, kilometraje)
                VALUES (?, ?, ?)
            ''', (vehiculo_id, fecha, kilometraje))
            conn.commit()
            # Obtenemos el id del kilometraje recién insertado
            kilometraje_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Calculamos la fecha del próximo mantenimiento
        tipo_mant = conn.execute('''
            SELECT kilometros_proximo_mantenimiento, meses_proximo_mantenimiento
            FROM Tipo_Mantenimiento
            WHERE id = ?
        ''', (tipo_mantenimiento_id,)).fetchone()

        # Verificar si ya existe un mantenimiento con esta combinación
        mantenimiento_existente = conn.execute('''
            SELECT id
            FROM Mantenimiento
            WHERE vehiculo_id = ? AND tipo_mantenimiento_id = ? AND kilometraje_id = ?
        ''', (vehiculo_id, tipo_mantenimiento_id, kilometraje_id)).fetchone()

        if mantenimiento_existente:
            return jsonify({
                'success': False,
                'error': 'Ya existe un mantenimiento registrado con estos datos'
            })

        # Calcular fecha_proximo_mantenimiento si hay meses especificados
        if tipo_mant['meses_proximo_mantenimiento']:
            conn.execute('''
                INSERT INTO Mantenimiento
                (vehiculo_id, tipo_mantenimiento_id, kilometraje_id, mecanico_id,
                 fecha_proximo_mantenimiento, precio)
                VALUES (?, ?, ?, ?, date(?, '+' || ? || ' months'), ?)
            ''', (vehiculo_id, tipo_mantenimiento_id, kilometraje_id, mecanico_id,
                  fecha, tipo_mant['meses_proximo_mantenimiento'], precio))
        else:
            conn.execute('''
                INSERT INTO Mantenimiento
                (vehiculo_id, tipo_mantenimiento_id, kilometraje_id, mecanico_id, precio)
                VALUES (?, ?, ?, ?, ?)
            ''', (vehiculo_id, tipo_mantenimiento_id, kilometraje_id, mecanico_id, precio))

        conn.commit()

        conn.close()
        return jsonify({
            'success': True,
            'message': 'Mantenimiento registrado exitosamente'
        })

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/agregar_vehiculo', methods=['POST'])
@login_required
def agregar_vehiculo():
    try:
        # Obtener datos del formulario
        alias = request.form['alias']
        marca = request.form['marca']
        modelo = request.form['modelo']
        anio = request.form['anio']
        tipo = request.form['tipo']
        tipo_motor = request.form['tipo_motor']
        tipo_transmision = request.form['tipo_transmision']

        conn = get_db_connection()

        # Primero insertar en Detalle_Vehiculo
        conn.execute('''
            INSERT INTO Detalle_Vehiculo
            (marca, modelo, anio, tipo, tipo_motor, tipo_transmision)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (marca, modelo, anio, tipo, tipo_motor, tipo_transmision))

        # Obtener el ID del detalle insertado
        detalle_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]

        # Insertar en Vehiculo
        conn.execute('''
            INSERT INTO Vehiculo (alias, detalle_id)
            VALUES (?, ?)
        ''', (alias, detalle_id))

        conn.commit()
        flash('Vehículo agregado exitosamente', 'success')
    except Exception as e:
        flash(f'Error al agregar vehículo: {str(e)}', 'danger')
    finally:
        conn.close()
        return redirect(url_for('index'))

@app.route('/sugerir_mantenimiento', methods=['POST'])
@login_required
def sugerir_mantenimiento():
    try:
        data = request.get_json()
        tipo_mantenimiento = data['tipo_mantenimiento']
        campo = data['campo']
        vehiculo_id = data['vehiculo_id']

        # Get vehicle details
        conn = get_db_connection()
        vehiculo = conn.execute('''
            SELECT d.marca, d.modelo, d.anio, d.tipo, d.tipo_motor, d.tipo_transmision
            FROM Vehiculo v
            JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
            WHERE v.id = ?
        ''', (vehiculo_id,)).fetchone()
        conn.close()

        if not vehiculo:
            return jsonify({'success': False, 'error': 'Vehículo no encontrado'})

        # Configure the Gemini model
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Expert-level prompts with mechanical considerations
        if campo == 'kilometros':
            prompt = f"""Como experto mecánico con 20 años de experiencia, considerando:
1. Recomendaciones del fabricante para {vehiculo['marca']} {vehiculo['modelo']} {vehiculo['anio']}
2. Tipo de motor: {vehiculo['tipo_motor']}
3. Tipo de transmisión: {vehiculo['tipo_transmision']}
4. Condiciones de manejo típicas en Costa Rica
5. Desgaste normal de componentes

Para el mantenimiento '{tipo_mantenimiento}', ¿cuál es el intervalo óptimo en KILÓMETROS?
Considera:
- Lubricantes sintéticos vs minerales
- Calidad de repuestos
- Condiciones climáticas tropicales
- Tipo de uso (urbano/rural)

Respuesta requerida: SOLO el número en kilómetros, sin texto. Ej: 10000"""
        else:
            prompt = f"""Como experto mecánico con 20 años de experiencia, considerando:
1. Recomendaciones del fabricante para {vehiculo['marca']} {vehiculo['modelo']} {vehiculo['anio']}
2. Tipo de motor: {vehiculo['tipo_motor']}
3. Tipo de transmisión: {vehiculo['tipo_transmision']}
4. Humedad y temperatura promedio en Costa Rica
5. Frecuencia de uso del vehículo

Para el mantenimiento '{tipo_mantenimiento}', ¿cuál es el intervalo óptimo en MESES?
Considera:
- Degradación de fluidos con el tiempo
- Corrosión por clima costero
- Uso en carreteras de montaña vs planas
- Tipo de almacenamiento

Respuesta requerida: SOLO el número en meses, sin texto. Ej: 6"""

        response = model.generate_content(prompt)
        sugerencia = response.text.strip()

        # Remove validation constraints
        try:
            # Handle ranges (e.g., "5000-7500" becomes 7500)
            if '-' in sugerencia:
                valores = [int(x.replace(',', '')) for x in sugerencia.split('-')]
                numero = max(valores)  # Use the upper limit
            else:
                numero = int(sugerencia.replace(',', ''))

            return jsonify({'success': True, 'sugerencia': numero})

        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Recomendación no válida: {sugerencia} - {str(e)}'
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/sugerir_categoria', methods=['POST'])
@login_required
def sugerir_categoria():
    try:
        data = request.get_json()
        tipo_mantenimiento = data['tipo_mantenimiento']
        vehiculo_id = data['vehiculo_id']

        # Get vehicle details
        conn = get_db_connection()
        vehiculo = conn.execute('''
            SELECT d.marca, d.modelo, d.anio, d.tipo, d.tipo_motor, d.tipo_transmision
            FROM Vehiculo v
            JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
            WHERE v.id = ?
        ''', (vehiculo_id,)).fetchone()
        conn.close()

        if not vehiculo:
            return jsonify({'success': False, 'error': 'Vehículo no encontrado'})

        # Configure the Gemini model
        model = genai.GenerativeModel('gemini-2.0-flash')

        # Expert-level prompt for category suggestion
        prompt = f"""Como experto mecánico con 20 años de experiencia, para un {vehiculo['marca']} {vehiculo['modelo']} {vehiculo['anio']} con motor {vehiculo['tipo_motor']} y transmisión {vehiculo['tipo_transmision']},
¿a qué categoría pertenece el mantenimiento '{tipo_mantenimiento}'?

Categorías disponibles:
- Motor
- Frenos
- Transmisión
- Suspensión
- Eléctrico
- Llantas
- Carrocería
- Refrigeración

Respuesta requerida: SOLO el nombre de la categoría, sin texto adicional. Ejemplo: "Motor" o "Frenos"."""

        response = model.generate_content(prompt)
        categoria = response.text.strip()

        # Validate that the category is one of the allowed options
        categorias_validas = ["Motor", "Frenos", "Transmisión", "Suspensión", "Eléctrico", "Llantas", "Carrocería", "Refrigeración"]

        if categoria not in categorias_validas:
            # Try to find the closest match
            for cat in categorias_validas:
                if cat.lower() in categoria.lower():
                    categoria = cat
                    break
            else:
                # If no match found, default to Motor
                categoria = "Motor"

        return jsonify({'success': True, 'categoria': categoria})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Add a new route to handle the direct mechanic addition from the index page
@app.route('/agregar_mecanico_directo', methods=['POST'])
@login_required
def agregar_mecanico_directo():
    try:
        nombre = request.form['nombre']
        telefono = request.form['telefono']

        conn = get_db_connection()

        # Check if mechanic already exists
        mecanico_existente = conn.execute('''
            SELECT id FROM Mecánico
            WHERE nombre_mecanico = ? AND telefono_mecanico = ?
        ''', (nombre, telefono)).fetchone()

        if mecanico_existente:
            flash('Ya existe un mecánico con este nombre y teléfono', 'warning')
        else:
            conn.execute('INSERT INTO Mecánico (nombre_mecanico, telefono_mecanico) VALUES (?, ?)',
                        (nombre, telefono))
            conn.commit()
            flash('Mecánico agregado exitosamente', 'success')

        conn.close()
    except Exception as e:
        flash(f'Error al agregar mecánico: {str(e)}', 'danger')

    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        error = None
        conn = None  # Initialize conn to None

        if not username:
            error = 'Se requiere nombre de usuario.'
        elif not password:
            error = 'Se requiere contraseña.'
        else:
            conn = get_db_connection()
            try:
                existing_user = conn.execute(
                    'SELECT id FROM Usuario WHERE username = ?',
                    (username,)
                ).fetchone()

                if existing_user:
                    error = f"La cuenta: {username}, ya está registrada."
                else:
                    conn.execute(
                        'INSERT INTO Usuario (username, password_hash) VALUES (?, ?)',
                        (username, generate_password_hash(password))
                    )
                    conn.commit()
                    flash('¡Registro exitoso! Por favor inicia sesión.', 'success')
                    # Redirect to a login page
                    return redirect(url_for('login'))
            except sqlite3.Error as e:
                 error = f"Error de base de datos: {e}"
            finally:
                if conn:
                    conn.close()

        if error:
            flash(error, 'danger')

    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        error = None
        user = conn.execute(
            'SELECT * FROM Usuario WHERE username = ?', (username,)
        ).fetchone()
        conn.close()

        if user is None:
            error = 'Nombre de usuario incorrecto.'
        elif not check_password_hash(user['password_hash'], password):
            error = 'Contraseña incorrecta.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            flash('¡Inicio de sesión exitoso!', 'success')
            return redirect(url_for('dashboard')) # Redirect to dashboard after login

        flash(error, 'danger')

    # If user is already logged in, redirect to dashboard
    if g.user:
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run()  # Remove debug=True for production

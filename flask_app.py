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
def index():
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    vehiculos = conn.execute('''
        SELECT v.id, v.alias, d.marca, d.modelo, d.anio
        FROM Vehiculo v
        JOIN Detalle_Vehiculo d ON v.detalle_id = d.id
    ''').fetchall()

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

    categorias_unicas = sorted(set(m['categoria'] for m in mantenimientos))
    tipos_unicos = sorted(set(m['tipo_mantenimiento'] for m in mantenimientos))
    mecanicos_unicos = sorted(set(m['mecanico'] for m in mantenimientos))

    conn.close()
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif conn.execute(
            'SELECT id FROM Usuario WHERE username = ?', (username,)
        ).fetchone() is not None:
            error = f'User {username} is already registered.'

        if error is None:
            conn.execute(
                'INSERT INTO Usuario (username, password_hash) VALUES (?, ?)',
                (username, generate_password_hash(password))
            )
            conn.commit()
            conn.close()
            flash('Registro exitoso. Por favor inicia sesión.', 'success')
            return redirect(url_for('login'))

        flash(error, 'error')
        conn.close()

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
            error = 'Usuario incorrecto.'
        elif not check_password_hash(user['password_hash'], password):
            error = 'Contraseña incorrecta.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))

        flash(error, 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
# Sistema de Mantenimiento de Vehículos

Aplicación web desarrollada con Flask para el registro y seguimiento del mantenimiento de vehículos. Esta aplicación permite a los usuarios mantener un registro detallado de los mantenimientos realizados a sus vehículos, incluyendo información sobre mecánicos, tipos de mantenimiento, y recordatorios para próximos servicios.

## Características

- **Gestión de Vehículos**
  - Registro de vehículos con detalles técnicos
  - Seguimiento de kilometraje
  - Historial de mantenimientos por vehículo

- **Mantenimientos**
  - Registro de mantenimientos realizados
  - Categorización de tipos de mantenimiento
  - Recordatorios de próximos servicios
  - Registro de costos y mecánicos

- **Sistema de Usuarios**
  - Autenticación de usuarios
  - Registro de nuevas cuentas
  - Gestión de sesiones

- **Características Avanzadas**
  - Integración con IA (Gemini) para sugerencias de mantenimiento
  - Cálculo automático de próximos servicios
  - Interfaz responsiva y moderna

## Requisitos Técnicos

- Python 3.7 o superior
- SQLite3
- Dependencias de Python (ver requirements.txt):
  - Flask 2.1.2
  - python-dotenv 1.0.0
  - google-generativeai >= 0.3.2
  - Werkzeug 2.3.8
  - pytz

## Instalación

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/mauricio222/vehicle-maintenance-app-spanish.git
   cd vehicle-maintenance-app-spanish
   ```

2. Crear y activar un entorno virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # En Windows: .venv\Scripts\activate
   ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Configurar variables de entorno:
   Crear un archivo `.env` en la raíz del proyecto con:
   ```
   FLASK_SECRET_KEY=tu_clave_secreta
   GEMINI_API_KEY=tu_api_key_de_gemini
   DB_PATH=mantenimiento.db
   ```

5. Inicializar la base de datos:
   ```bash
   python initialize_db.py
   ```

## Uso

1. Iniciar la aplicación:
   ```bash
   python flask_app.py
   ```

2. Acceder a la aplicación:
   - Abrir navegador web
   - Visitar `http://localhost:5000`
   - Registrar una nueva cuenta o iniciar sesión

## Estructura del Proyecto

```
.
├── flask_app.py           # Aplicación principal
├── initialize_db.py       # Script de inicialización de BD
├── requirements.txt       # Dependencias del proyecto
├── .env                   # Variables de entorno (no incluido)
├── mantenimiento.db      # Base de datos SQLite (generado)
└── templates/            # Plantillas HTML
    ├── index.html        # Página principal/dashboard
    ├── login.html        # Página de inicio de sesión
    ├── register.html     # Página de registro
    ├── mantenimientos.html    # Vista de mantenimientos
    └── mantenimiento_registro.html  # Formulario de registro
```

## Seguridad

- Contraseñas hasheadas usando Werkzeug
- Protección contra SQL injection
- Manejo seguro de sesiones
- Variables de entorno para datos sensibles

## Contribuir

1. Fork el repositorio
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles.

## Contacto

Para preguntas o sugerencias, por favor abrir un issue en este repositorio.
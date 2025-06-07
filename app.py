# app.py

# 1. Importaciones
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import os
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# 2. Configuración de la Aplicación Flask
app = Flask(__name__)
# Usa la variable de entorno DATABASE_URL para Render, o SQLite para desarrollo local
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///mk_nails.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Clave secreta para la seguridad de las sesiones de Flask. ¡MUY IMPORTANTE!
# En producción, usa una cadena más compleja y generada de forma segura.
# Puedes obtenerla de una variable de entorno en producción:
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una_clave_secreta_muy_segura_y_larga_para_mk_nails_cambiar_en_produccion')


# 3. Inicialización de SQLAlchemy (db) y Flask-Login (login_manager)
# db = SQLAlchemy(app) DEBE estar ANTES de los modelos que usan db.Model
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app) # Inicializa Flask-Login con tu app
login_manager.login_view = 'login' # La ruta a la que se redirigirá si no está logueado


# 4. Definición de los Modelos de la Base de Datos
# Modelo User para la autenticación
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Aumentar longitud para username por si acaso
    username = db.Column(db.String(120), unique=True, nullable=False)
    # Aumentar longitud para password_hash (¡CRÍTICO para Werkzeug!)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        # Hashea la contraseña antes de guardarla.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # Verifica una contraseña con el hash guardado.
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"

# Modelo Cita
class Cita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.String(5), nullable=False)
    servicio = db.Column(db.String(100), nullable=True)
    monto = db.Column(db.Float, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    # Relación uno a uno con Ingreso, para vincular el monto de la cita a un registro de ingreso
    ingreso_id = db.Column(db.Integer, db.ForeignKey('ingreso.id'), nullable=True)
    ingreso = db.relationship('Ingreso', backref='cita_asociada', uselist=False)

    def __repr__(self):
        return f"<Cita {self.cliente} - {self.fecha} {self.hora}>"

# Modelo Ingreso
class Ingreso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(200), nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    # 'tipo' para distinguir si es un ingreso de 'cita' o 'manual'
    tipo = db.Column(db.String(50), nullable=False, default='manual')

    def __repr__(self):
        return f"<Ingreso {self.fecha} - ${self.monto:.2f}>"


# 5. Funciones de Carga de Usuario para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """
    Esta función es necesaria para Flask-Login.
    Recupera un objeto User por su ID.
    """
    return User.query.get(int(user_id))

# 6. Creación de la Base de Datos (Si no existe)
# Este bloque se ejecuta cuando el script se corre directamente.
# Crea las tablas en la base de datos si aún no existen.
with app.app_context():
    db.create_all()

    # Opcional: Crear un usuario administrador inicial si no existe
    # ¡ADVERTENCIA! Esto es solo para la primera vez o para desarrollo.
    # EN PRODUCCIÓN, elimina esta sección o implementa un sistema más seguro para crear usuarios.
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin')
        admin_user.set_password('admin123') # ¡CAMBIA ESTA CONTRASEÑA EN PRODUCCIÓN!
        db.session.add(admin_user)
        db.session.commit()
        print("--- Usuario 'admin' creado con contraseña 'admin123'. ¡CAMBIA ESTO URGENTEMENTE EN PRODUCCIÓN! ---")


# 7. Rutas de la Aplicación

# Rutas de Autenticación
@app.route('/register', methods=['GET', 'POST'])
def register():
    # En una aplicación real, querrías más seguridad para permitir registros,
    # como un código de invitación o solo permitir el registro por un admin.
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('El nombre de usuario ya existe. Por favor, elige otro.', 'error')
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('¡Registro exitoso! Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # Si el usuario ya está logueado, redirige al índice
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user) # Inicia la sesión del usuario
            flash('Inicio de sesión exitoso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required # Solo permite cerrar sesión si ya estás logueado
def logout():
    logout_user() # Cierra la sesión del usuario
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login')) # Redirige a la página de login

# Ruta principal: Muestra el tablero con citas del día y del día siguiente, y contabilidad.
@app.route('/')
@login_required # Protege esta ruta, requiere inicio de sesión
def index():
    today = date.today()
    tomorrow = today + timedelta(days=1)

    citas_hoy = Cita.query.filter_by(fecha=today).order_by(Cita.hora).all()
    citas_manana = Cita.query.filter_by(fecha=tomorrow).order_by(Cita.hora).all()

    ingresos_hoy = sum(ingreso.monto for ingreso in Ingreso.query.filter_by(fecha=today).all())
    fecha_hace_7_dias = today - timedelta(days=6)
    ingresos_semana = sum(ingreso.monto for ingreso in Ingreso.query.filter(
        Ingreso.fecha >= fecha_hace_7_dias, Ingreso.fecha <= today
    ).all())
    ingresos_mes = sum(ingreso.monto for ingreso in Ingreso.query.filter(
        db.extract('month', Ingreso.fecha) == today.month,
        db.extract('year', Ingreso.fecha) == today.year
    ).all())

    return render_template('index.html',
                           citas_hoy=citas_hoy,
                           citas_manana=citas_manana,
                           ingresos_hoy=ingresos_hoy,
                           ingresos_semana=ingresos_semana,
                           ingresos_mes=ingresos_mes,
                           today=today,
                           tomorrow=tomorrow)

# Ruta para agendar una nueva cita
@app.route('/agendar_cita', methods=['GET', 'POST'])
@login_required # Protege esta ruta
def agendar_cita():
    if request.method == 'POST':
        cliente = request.form['cliente']
        fecha_str = request.form['fecha']
        hora = request.form['hora']
        servicio = request.form.get('servicio')
        monto_str = request.form.get('monto')

        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            monto = float(monto_str) if monto_str else None

            if fecha < date.today():
                flash('No puedes agendar citas en el pasado.', 'error')
                return redirect(url_for('agendar_cita'))

            ingreso_asociado = None
            if monto is not None:
                # El tipo de ingreso es 'cita'
                ingreso_asociado = Ingreso(fecha=fecha, monto=monto,
                                          descripcion=f"Cita de {cliente} - {servicio or 'Sin servicio'}",
                                          tipo='cita')
                db.session.add(ingreso_asociado)
                db.session.commit() # Guarda el ingreso para obtener su ID

            # Luego creamos la cita y la vinculamos al ingreso
            nueva_cita = Cita(cliente=cliente, fecha=fecha, hora=hora, servicio=servicio, monto=monto)
            if ingreso_asociado:
                nueva_cita.ingreso_id = ingreso_asociado.id # Vincula el ingreso al cita

            db.session.add(nueva_cita)
            db.session.commit()

            flash('Cita agendada con éxito!', 'success')
            return redirect(url_for('index'))
        except ValueError:
            flash('Error en el formato de fecha o monto. Por favor, revisa tus datos.', 'error')
            # Si el ingreso se creó y hubo un error en la cita, podemos intentar revertirlo
            if ingreso_asociado and ingreso_asociado.id:
                db.session.rollback() # Revierte la transacción si algo falla después de crear el ingreso
                flash('Se ha revertido el registro de ingreso debido a un error en la cita.', 'error')
        except Exception as e:
            flash(f'Ocurrió un error al agendar la cita: {e}', 'error')
            if 'ingreso_asociado' in locals() and ingreso_asociado and ingreso_asociado.id:
                db.session.rollback() # Revierte la transacción
    return render_template('agendar_cita.html')

# Ruta para registrar un ingreso manual
@app.route('/registrar_ingreso', methods=['GET', 'POST'])
@login_required # Protege esta ruta
def registrar_ingreso():
    today = date.today()
    if request.method == 'POST':
        fecha_str = request.form['fecha']
        monto_str = request.form['monto']
        descripcion = request.form.get('descripcion')

        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            monto = float(monto_str)

            if monto <= 0:
                flash('El monto del ingreso debe ser positivo.', 'error')
                return redirect(url_for('registrar_ingreso'))

            # El tipo de ingreso es 'manual'
            nuevo_ingreso = Ingreso(fecha=fecha, monto=monto, descripcion=descripcion, tipo='manual')
            db.session.add(nuevo_ingreso)
            db.session.commit()
            flash('Ingreso registrado con éxito!', 'success')
            return redirect(url_for('index'))
        except ValueError:
            flash('Error en el formato de fecha o monto. Por favor, revisa tus datos.', 'error')
        except Exception as e:
            flash(f'Ocurrió un error al registrar el ingreso: {e}', 'error')
    return render_template('registrar_ingreso.html', today=today)


# Ruta para ver todas las citas (opcional, para gestión)
@app.route('/ver_todas_citas')
@login_required # Protege esta ruta
def ver_todas_citas():
    # Ordenar citas por fecha y luego por hora
    todas_citas = Cita.query.order_by(Cita.fecha.asc(), Cita.hora.asc()).all()
    return render_template('ver_todas_citas.html', todas_citas=todas_citas)

# Ruta para eliminar una cita (ahora también elimina el ingreso asociado)
@app.route('/eliminar_cita/<int:cita_id>', methods=['POST'])
@login_required # Protege esta ruta
def eliminar_cita(cita_id):
    cita_a_eliminar = Cita.query.get_or_404(cita_id)
    try:
        # Si la cita tiene un ingreso_id asociado, intenta eliminar también ese ingreso
        if cita_a_eliminar.ingreso_id:
            ingreso_asociado = Ingreso.query.get(cita_a_eliminar.ingreso_id)
            if ingreso_asociado:
                db.session.delete(ingreso_asociado)
                flash(f'Ingreso asociado (${ingreso_asociado.monto:.2f}) eliminado.', 'info')

        db.session.delete(cita_a_eliminar)
        db.session.commit()
        flash('Cita eliminada con éxito.', 'success')
    except Exception as e:
        db.session.rollback() # Si algo falla, revierte los cambios para evitar datos inconsistentes
        flash(f'Error al eliminar la cita y su ingreso asociado: {e}', 'error')
    return redirect(request.referrer or url_for('index')) # Regresa a la página anterior o al inicio

# Ruta para ver todos los ingresos
@app.route('/ver_todos_ingresos')
@login_required # Protege esta ruta
def ver_todos_ingresos():
    # Ordenar ingresos por fecha descendente
    todos_ingresos = Ingreso.query.order_by(Ingreso.fecha.desc(), Ingreso.fecha_registro.desc()).all()
    return render_template('ver_todos_ingresos.html', todos_ingresos=todos_ingresos)

# Ruta para eliminar un ingreso (solo manuales directamente)
@app.route('/eliminar_ingreso/<int:ingreso_id>', methods=['POST'])
@login_required # Protege esta ruta
def eliminar_ingreso(ingreso_id):
    ingreso_a_eliminar = Ingreso.query.get_or_404(ingreso_id)
    try:
        # IMPORTANTE: Asegurarse de que no estamos eliminando un ingreso que tiene una cita vinculada.
        if ingreso_a_eliminar.tipo == 'cita':
            flash('No puedes eliminar un ingreso vinculado a una cita directamente. Elimina la cita para eliminar su ingreso asociado.', 'error')
            return redirect(request.referrer or url_for('ver_todos_ingresos'))

        db.session.delete(ingreso_a_eliminar)
        db.session.commit()
        flash('Ingreso eliminado con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el ingreso: {e}', 'error')
    return redirect(request.referrer or url_for('ver_todos_ingresos'))


# Ruta para editar un ingreso
@app.route('/editar_ingreso/<int:ingreso_id>', methods=['GET', 'POST'])
@login_required # Protege esta ruta
def editar_ingreso(ingreso_id):
    ingreso = Ingreso.query.get_or_404(ingreso_id)
    today = date.today()

    if request.method == 'POST':
        fecha_str = request.form['fecha']
        monto_str = request.form['monto']
        descripcion = request.form.get('descripcion')

        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            monto = float(monto_str)

            if monto <= 0:
                flash('El monto del ingreso debe ser positivo.', 'error')
                return redirect(url_for('editar_ingreso', ingreso_id=ingreso.id))

            ingreso.fecha = fecha
            ingreso.monto = monto
            ingreso.descripcion = descripcion

            db.session.commit()
            flash('Ingreso actualizado con éxito!', 'success')
            return redirect(url_for('ver_todos_ingresos'))
        except ValueError:
            flash('Error en el formato de fecha o monto. Por favor, revisa tus datos.', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error al actualizar el ingreso: {e}', 'error')

    return render_template('editar_ingreso.html', ingreso=ingreso, today=today)


# 8. Ejecución de la Aplicación
if __name__ == '__main__':
    # Esto iniciará el servidor de desarrollo de Flask.
    # debug=True permite recargar automáticamente el servidor en cambios
    # y muestra errores detallados en el navegador.
    # host='0.0.0.0' permite acceder desde otros dispositivos en la misma red local.
    app.run(debug=True, host='0.0.0.0')
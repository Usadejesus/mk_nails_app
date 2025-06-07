## app.py

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import os # <-- ¡Asegúrate de que esta línea esté presente al principio del archivo!

# --- Configuración de la Aplicación Flask ---
app = Flask(__name__)

# Configura la base de datos. Usará la variable de entorno 'DATABASE_URL' si existe (en Render).
# Si no existe (en tu entorno de desarrollo local), volverá a usar 'sqlite:///mk_nails.db'.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///mk_nails.db')

# Deshabilita una advertencia de SQLAlchemy.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Se necesita una clave secreta para la seguridad de las sesiones de Flask.
# ¡IMPORTANTE! En un proyecto real, usa una cadena más compleja y segura,
# y preferiblemente también la obtendrías de una variable de entorno.
app.config['SECRET_KEY'] = 'una_clave_secreta_muy_segura_y_larga_para_mk_nails'

# Inicializa la extensión SQLAlchemy con la aplicación Flask.
db = SQLAlchemy(app)

# ... el resto de tu código para los modelos Cita e Ingreso, y las rutas ...

# Asegúrate de que esta sección esté presente para crear las tablas
# tanto en SQLite (local) como en PostgreSQL (Render) si no existen.
with app.app_context():
    db.create_all()

# ... el resto de tus rutas y la ejecución de la aplicación ...

# --- Definición de los Modelos de la Base de Datos ---

class Cita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.String(5), nullable=False)
    servicio = db.Column(db.String(100), nullable=True)
    monto = db.Column(db.Float, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    # Añadimos una columna para vincular Cita con Ingreso
    # Puede ser nulo porque un ingreso manual no está vinculado a una cita
    ingreso_id = db.Column(db.Integer, db.ForeignKey('ingreso.id'), nullable=True)
    ingreso = db.relationship('Ingreso', backref='cita', uselist=False) # Relación uno a uno

    def __repr__(self):
        return f"<Cita {self.cliente} - {self.fecha} {self.hora}>"

class Ingreso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    monto = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(200), nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    # `tipo` para distinguir si es un ingreso de cita o manual
    tipo = db.Column(db.String(50), nullable=False, default='manual') # 'cita' o 'manual'


    def __repr__(self):
        return f"<Ingreso {self.fecha} - ${self.monto:.2f}>"

# --- Creación de la Base de Datos (Si no existe) ---
with app.app_context():
    db.create_all()

# --- Rutas de la Aplicación (Funciones que manejan las solicitudes web) ---

@app.route('/')
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

@app.route('/agendar_cita', methods=['GET', 'POST'])
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

            # Primero creamos el ingreso si hay monto
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

@app.route('/registrar_ingreso', methods=['GET', 'POST'])
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


@app.route('/ver_todas_citas')
def ver_todas_citas():
    todas_citas = Cita.query.order_by(Cita.fecha.asc(), Cita.hora.asc()).all()
    return render_template('ver_todas_citas.html', todas_citas=todas_citas)

# MODIFICACIÓN: Ruta para eliminar una cita (ahora también elimina el ingreso asociado)
@app.route('/eliminar_cita/<int:cita_id>', methods=['POST'])
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
    return redirect(request.referrer or url_for('index'))

# NUEVA RUTA: Ver todos los ingresos
@app.route('/ver_todos_ingresos')
def ver_todos_ingresos():
    # Ordenar ingresos por fecha descendente
    todos_ingresos = Ingreso.query.order_by(Ingreso.fecha.desc(), Ingreso.fecha_registro.desc()).all()
    return render_template('ver_todos_ingresos.html', todos_ingresos=todos_ingresos)

# NUEVA RUTA: Eliminar un ingreso manual
@app.route('/eliminar_ingreso/<int:ingreso_id>', methods=['POST'])
def eliminar_ingreso(ingreso_id):
    ingreso_a_eliminar = Ingreso.query.get_or_404(ingreso_id)
    try:
        # IMPORTANTE: Asegurarse de que no estamos eliminando un ingreso que tiene una cita vinculada.
        # Esto evita eliminar el ingreso de una cita sin eliminar la cita misma.
        # Si un ingreso es de tipo 'cita', no permitimos eliminarlo directamente desde aquí.
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


# NUEVA RUTA: Editar un ingreso
@app.route('/editar_ingreso/<int:ingreso_id>', methods=['GET', 'POST'])
def editar_ingreso(ingreso_id):
    ingreso = Ingreso.query.get_or_404(ingreso_id)
    today = date.today() # Para el campo de fecha si se necesita

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

            # Si este ingreso estaba asociado a una cita, y el monto de la cita
            # es el mismo que el del ingreso, actualizamos también el monto de la cita.
            # Esto es un poco más complejo, pero si la relación es 1:1, podemos considerarlo.
            # Para la simplicidad de este ejercicio, nos enfocaremos en actualizar el ingreso.
            # Si se quiere, podríamos añadir una lógica para buscar la cita asociada por ingreso_id y actualizarla.

            db.session.commit()
            flash('Ingreso actualizado con éxito!', 'success')
            return redirect(url_for('ver_todos_ingresos'))
        except ValueError:
            flash('Error en el formato de fecha o monto. Por favor, revisa tus datos.', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Ocurrió un error al actualizar el ingreso: {e}', 'error')

    return render_template('editar_ingreso.html', ingreso=ingreso, today=today)


# --- Ejecución de la Aplicación ---
if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template, request, redirect, session, g, url_for, flash, jsonify
from app.db import get_db
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates")
)
# Use an environment variable in production
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ---------------- INDEX ----------------
@app.route("/")
def index():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Estadísticas generales
    cursor.execute("SELECT COUNT(*) as total FROM clientes")
    total_clientes = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM vehiculos")
    total_vehiculos = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM empleados")
    total_empleados = cursor.fetchone()['total']
    
    cursor.execute("SELECT SUM(total) as total FROM ventas")
    total_ventas_result = cursor.fetchone()['total']
    total_ventas = float(total_ventas_result) if total_ventas_result else 0
    
    # Últimas 5 ventas
    cursor.execute("""
        SELECT v.id, v.fecha, v.total, c.nombre as cliente
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        ORDER BY v.id DESC
        LIMIT 5
    """)
    ultimas_ventas = cursor.fetchall()
    
    # Empleados por departamento
    cursor.execute("""
        SELECT departamento, COUNT(*) as cantidad
        FROM empleados
        GROUP BY departamento
    """)
    empleados_dept = cursor.fetchall()
    
    # Stock total por almacén
    cursor.execute("""
        SELECT a.ubicacion, SUM(e.cantidad) as cantidad_total
        FROM almacenes a
        LEFT JOIN existencias e ON a.id = e.almacen_id
        GROUP BY a.id, a.ubicacion
    """)
    almacenes_stock = cursor.fetchall()
    
    db.close()
    
    return render_template("index.html", 
                         total_clientes=total_clientes,
                         total_vehiculos=total_vehiculos,
                         total_empleados=total_empleados,
                         total_ventas=total_ventas,
                         ultimas_ventas=ultimas_ventas,
                         empleados_dept=empleados_dept,
                         almacenes_stock=almacenes_stock)

# ---------------- AUTH ----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "empleado_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def normalize_role(role):
    if not role:
        return None
    mapping = {
        'admin': 'jefe',
        'gerente': 'jefe',
        'compras': 'supervisor',
        'vendedor': 'empleado',
        'almacenista': 'empleado',
        'tecnico': 'empleado'
    }
    return mapping.get(role, role)

# Define permissions by action for the three roles
permissions = {
    'jefe': {'view': True, 'add': True, 'edit': True, 'delete': True},
    'supervisor': {'view': True, 'add': True, 'edit': True, 'delete': False},
    'empleado': {'view': True, 'add': True, 'edit': False, 'delete': False},
}

# Validacion de Contraseña 
def is_valid_password(p):
    if not isinstance(p, str):
        return False
    if len(p) < 4:
        return False
    if not p.isalnum():
        return False
    has_digit = any(c.isdigit() for c in p)
    has_alpha = any(c.isalpha() for c in p)
    return has_digit and has_alpha

MONEY_PLACES = Decimal("0.01")

def to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None

def to_int_quantity(value):
    dec = to_decimal(value)
    if dec is None:
        return None
    if dec != dec.to_integral_value():
        return None
    return int(dec)

def quantize_money(value):
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)

@app.context_processor
def inject_permissions():
    def has_permission(action):
        role = normalize_role(session.get('empleado_role'))
        if not role:
            return False
        if role == 'jefe':
            return True
        return permissions.get(role, {}).get(action, False)
    return dict(has_permission=has_permission)


def role_required(*roles, action=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            role = normalize_role(session.get("empleado_role"))
            if role == 'jefe':
                return f(*args, **kwargs)
            if roles:
                normalized_roles = [normalize_role(r) for r in roles]
                if role in normalized_roles:
                    return f(*args, **kwargs)
                flash("No autorizado", "error")
                return redirect(url_for("index"))
            if action:
                if permissions.get(role, {}).get(action):
                    return f(*args, **kwargs)
                flash("No autorizado", "error")
                return redirect(url_for("index"))
            # Default: allow view for any logged-in user
            return f(*args, **kwargs)
        return wrapped
    return decorator


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM empleados WHERE correo=%s", (request.form["correo"],))
        empleado = cursor.fetchone()
        db.close()
        if empleado and check_password_hash(empleado.get("contrasena",""), request.form["contrasena"]):
            session["empleado_id"] = empleado["id"]
            session["empleado_nombre"] = empleado["nombre"]
            raw_role = empleado.get("role") or 'empleado'
            role = normalize_role(raw_role)
            session["empleado_role"] = role
            # If role missing in DB, set default to 'empleado'
            if empleado.get("role") is None:
                db = get_db()
                cur2 = db.cursor()
                try:
                    cur2.execute("UPDATE empleados SET role=%s WHERE id=%s", (role, empleado['id']))
                    db.commit()
                except Exception:
                    pass
                cur2.close()
                db.close()
            return redirect("/")
        flash("Credenciales incorrectas", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/register", methods=["GET", "POST"])
def register():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM empleados WHERE role='jefe'")
    jefe_exists = cur.fetchone()[0] > 0

    # Build department options: jefe can choose all; if no jefe exists allow jefe option for first registration
    departments = ['Ventas', 'Almacén', 'Compras', 'Técnico']
    if not jefe_exists or normalize_role(session.get('empleado_role')) == 'jefe':
        departments = ['Administración', 'Gerencia'] + departments

    # Roles available at registration
    roles = ['supervisor','empleado']
    if not jefe_exists or normalize_role(session.get('empleado_role')) == 'jefe':
        roles = ['jefe'] + roles

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        dni = request.form.get("dni", "").strip()
        correo = request.form.get("correo", "").strip()
        direccion = request.form.get("direccion", "").strip()
        departamento = request.form.get("departamento", "").strip()
        salario = request.form.get("salario") or 0
        contrasena = request.form.get("contrasena", "")
        contrasena2 = request.form.get("contrasena2", "")

        # Validaciones básicas
        if not nombre or not dni or not correo or not contrasena:
            flash("Rellena nombre, DNI, correo y contraseña", "error")
            return render_template("register.html", departments=departments)
        if contrasena != contrasena2:
            flash("Las contraseñas no coinciden", "error")
            return render_template("register.html", departments=departments)

        if not is_valid_password(contrasena):
            flash("La contraseña debe tener al menos 4 caracteres, contener letras y números, y no incluir símbolos.", "error")
            return render_template("register.html", departments=departments, roles=roles)

        # Revisa duplicados de correo o DNI
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id FROM empleados WHERE correo=%s OR dni=%s", (correo, dni))
        if cursor.fetchone():
            db.close()
            flash("Correo o DNI ya registrado", "error")
            return render_template("register.html", departments=departments)

        # Validar departamento y rol
        selected_dept = departamento
        selected_role = request.form.get('role') or 'empleado'
        if selected_role not in roles:
            db.close()
            flash("Rol no permitido", "error")
            return render_template("register.html", departments=departments, roles=roles)
        if selected_role == 'jefe' and normalize_role(session.get('empleado_role')) != 'jefe' and jefe_exists:
            # Solo el jefe puede asignar el rol de jefe si ya existe uno
            db.close()
            flash("No está permitido asignar Jefe", "error")
            return render_template("register.html", departments=departments, roles=roles)

        hashed = generate_password_hash(contrasena)
        cursor2 = db.cursor()
        cursor2.execute("""
            INSERT INTO empleados (nombre,dni,correo,direccion,departamento,salario,contrasena,role)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            nombre,
            dni,
            correo,
            direccion,
            selected_dept,
            salario,
            hashed,
            selected_role
        ))
        db.commit()
        emp_id = cursor2.lastrowid
        db.close()

        # Auto-login después del registro
        session["empleado_id"] = emp_id
        session["empleado_nombre"] = nombre
        session["empleado_role"] = normalize_role(selected_role)
        flash("Registro exitoso. Has iniciado sesión.", "success")
        return redirect("/")

    # GET
    cur.close()
    db.close()
    return render_template("register.html", departments=departments, roles=roles)

# ---------------- CLIENTES ----------------
@app.route("/clientes")
@login_required
def clientes():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    q = request.args.get('q', '').strip()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    # Build filter
    params = []
    where = ''
    if q:
        like = f"%{q}%"
        where = "WHERE nombre LIKE %s OR dni LIKE %s OR correo LIKE %s"
        params = [like, like, like]
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM clientes {where}", tuple(params))
    total = cursor.fetchone()['cnt']
    params2 = params + [per_page, offset]
    cursor.execute(f"SELECT * FROM clientes {where} LIMIT %s OFFSET %s", tuple(params2))
    data = cursor.fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    db.close()
    return render_template("clientes.html", clientes=data, page=page, per_page=per_page, total=total, pages=pages, q=q)

@app.route("/clientes/nuevo", methods=["GET", "POST"])
@login_required
@role_required(action='add')
def nuevo_cliente():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO clientes VALUES (NULL,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["nombre"],
            request.form["dni"],
            request.form["correo"],
            request.form["telefono"],
            request.form["pais"],
            request.form["tipo"]
        ))
        db.commit()
        db.close()
        return redirect("/clientes")
    return render_template("clientes_form.html")

@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
@login_required
@role_required(action='edit')
def editar_cliente(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == "POST":
        cursor.execute("""
            UPDATE clientes SET nombre=%s, dni=%s, correo=%s, telefono=%s, pais=%s, tipo=%s
            WHERE id=%s
        """, (
            request.form["nombre"],
            request.form["dni"],
            request.form["correo"],
            request.form["telefono"],
            request.form["pais"],
            request.form["tipo"],
            id
        ))
        db.commit()
        db.close()
        return redirect("/clientes")
    cursor.execute("SELECT * FROM clientes WHERE id=%s", (id,))
    cliente = cursor.fetchone()
    db.close()
    return render_template("clientes_form.html", cliente=cliente)

@app.route("/clientes/eliminar/<int:id>")
@login_required
@role_required(action='delete')
def eliminar_cliente(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM clientes WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/clientes")


@app.route("/clientes/buscar")
@login_required
def buscar_clientes():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    like = f"%{q}%"
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, nombre, dni, correo, telefono, pais, tipo
        FROM clientes
        WHERE nombre LIKE %s OR dni LIKE %s
        ORDER BY nombre
        LIMIT 10
        """,
        (like, like)
    )
    data = cursor.fetchall()
    db.close()
    return jsonify(data)


@app.route("/almacenes/<int:almacen_id>/articulos/buscar")
@login_required
def buscar_articulos_almacen(almacen_id):
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    like = f"%{q}%"
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT a.id, a.nombre, e.cantidad
        FROM existencias e
        JOIN articulos a ON a.id = e.articulo_id
        WHERE e.almacen_id = %s AND e.cantidad > 0 AND a.nombre LIKE %s
        ORDER BY a.nombre
        LIMIT 10
        """,
        (almacen_id, like)
    )
    data = cursor.fetchall()
    db.close()
    return jsonify(data)

# ---------------- EMPLEADOS ----------------
@app.route("/empleados")
@login_required
@role_required(action='view')
def empleados():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    q = request.args.get('q', '').strip()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    params = []
    where = ''
    if q:
        like = f"%{q}%"
        where = "WHERE nombre LIKE %s OR dni LIKE %s OR correo LIKE %s OR departamento LIKE %s OR role LIKE %s"
        params = [like, like, like, like, like]
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM empleados {where}", tuple(params))
    total = cursor.fetchone()['cnt']
    params2 = params + [per_page, offset]
    cursor.execute(f"SELECT * FROM empleados {where} LIMIT %s OFFSET %s", tuple(params2))
    data = cursor.fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    db.close()
    return render_template("empleados.html", empleados=data, page=page, per_page=per_page, total=total, pages=pages, q=q)

@app.route("/empleados/nuevo", methods=["GET", "POST"])
@login_required
@role_required(action='add')
def nuevo_empleado():
    # Departments allowed for jefe
    departments = ['Administración','Gerencia','Ventas','Almacén','Compras','Técnico']
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM empleados WHERE role='jefe'")
    jefe_exists = cur.fetchone()[0] > 0

    roles = ['supervisor','empleado']
    if not jefe_exists or normalize_role(session.get('empleado_role')) == 'jefe':
        roles = ['jefe'] + roles

    if request.method == "POST":
        departamento = request.form.get('departamento')
        selected_role = request.form.get('role') or 'empleado'
        if selected_role not in roles:
            db.close()
            flash('Rol no permitido', 'error')
            return render_template('empleados_form.html', departments=departments, roles=roles)
        # Prevent non-jefe from assigning jefe if one exists
        if selected_role == 'jefe' and normalize_role(session.get('empleado_role')) != 'jefe' and jefe_exists:
            db.close()
            flash('No está permitido asignar Jefe', 'error')
            return render_template('empleados_form.html', departments=departments, roles=roles)
        pw = request.form.get("contrasena", "")
        if not is_valid_password(pw):
            db.close()
            flash("La contraseña debe tener al menos 4 caracteres, contener letras y números, y no incluir símbolos.", "error")
            return render_template('empleados_form.html', departments=departments, roles=roles)
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO empleados (nombre,dni,correo,direccion,departamento,salario,contrasena,role) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["nombre"],
            request.form["dni"],
            request.form["correo"],
            request.form["direccion"],
            departamento,
            request.form["salario"],
            generate_password_hash(request.form.get("contrasena", "")),
            selected_role
        ))
        db.commit()
        db.close()
        return redirect("/empleados")
    return render_template("empleados_form.html", departments=departments, roles=roles)

@app.route("/empleados/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_empleado(id):
    # Allow jefe/supervisor or the employee themselves to edit
    if normalize_role(session.get("empleado_role")) not in ('jefe','supervisor') and session.get("empleado_id") != id:
        flash("No autorizado", "error")
        return redirect("/empleados")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    # prepare departments list
    cur2 = db.cursor()
    cur2.execute("SELECT COUNT(*) FROM empleados WHERE role='jefe'")
    jefe_exists = cur2.fetchone()[0] > 0
    cur2.close()
    departments = ['Ventas','Almacén','Compras','Técnico']
    if not jefe_exists or session.get('empleado_role') == 'jefe':
        departments = ['Administración','Gerencia'] + departments
    roles = ['supervisor','empleado']
    if not jefe_exists or session.get('empleado_role') == 'jefe':
        roles = ['jefe'] + roles

    if request.method == "POST":
        departamento = request.form.get('departamento')
        selected_role = request.form.get('role') or 'empleado'
        if selected_role not in roles:
            flash('Rol no permitido', 'error')
            return redirect(f'/empleados/editar/{id}')
        # Prevent non-jefe from assigning jefe if one exists
        if selected_role == 'jefe' and normalize_role(session.get('empleado_role')) != 'jefe' and jefe_exists:
            flash('No está permitido asignar Jefe', 'error')
            return redirect(f'/empleados/editar/{id}')
        role = selected_role

        # Self-edit and role validation handled above (jefe assignment already validated)
        if request.method == 'POST' and request.form.get('contrasena'):
            pw = request.form.get('contrasena')
            if not is_valid_password(pw):
                flash("La contraseña debe tener al menos 4 caracteres, contener letras y números, y no incluir símbolos.", "error")
                return redirect(f'/empleados/editar/{id}')
            # Password change
            cursor.execute('''
                UPDATE empleados SET nombre=%s, dni=%s, correo=%s, direccion=%s, departamento=%s, salario=%s, contrasena=%s, role=%s
                WHERE id=%s
            ''', (
                request.form["nombre"],
                request.form["dni"],
                request.form["correo"],
                request.form["direccion"],
                departamento,
                request.form["salario"],
                generate_password_hash(request.form.get("contrasena")),
                role,
                id
            ))
        else:
            # No password change
            cursor.execute('''
                UPDATE empleados SET nombre=%s, dni=%s, correo=%s, direccion=%s, departamento=%s, salario=%s, role=%s
                WHERE id=%s
            ''', (
                request.form["nombre"],
                request.form["dni"],
                request.form["correo"],
                request.form["direccion"],
                departamento,
                request.form["salario"],
                role,
                id
            ))
        db.commit()
        db.close()
        return redirect("/empleados")
    cursor.execute("SELECT * FROM empleados WHERE id=%s", (id,))
    empleado = cursor.fetchone()
    db.close()
    return render_template("empleados_form.html", empleado=empleado, departments=departments, roles=roles)

@app.route("/empleados/eliminar/<int:id>")
@login_required
@role_required(action='delete')
def eliminar_empleado(id):
    # Prevent deleting yourself
    if session.get("empleado_id") == id:
        flash("No puedes eliminar tu propio usuario", "error")
        return redirect("/empleados")
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM empleados WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/empleados")

# ---------------- VEHICULOS ----------------
@app.route("/vehiculos")
@login_required
def vehiculos():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    q = request.args.get('q', '').strip()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    params = []
    where = ''
    if q:
        like = f"%{q}%"
        where = "WHERE modelo LIKE %s OR tipo LIKE %s OR color LIKE %s"
        params = [like, like, like]
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM vehiculos {where}", tuple(params))
    total = cursor.fetchone()['cnt']
    params2 = params + [per_page, offset]
    cursor.execute(f"SELECT * FROM vehiculos {where} LIMIT %s OFFSET %s", tuple(params2))
    data = cursor.fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    db.close()
    return render_template("vehiculos.html", vehiculos=data, page=page, per_page=per_page, total=total, pages=pages, q=q)

@app.route("/vehiculos/nuevo", methods=["GET", "POST"])
@login_required
@role_required(action='add')
def nuevo_vehiculo():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO vehiculos VALUES (NULL,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["modelo"],
            request.form["tipo"],
            request.form["anio"],
            request.form["color"],
            request.form["precio"],
            request.form["costo"]
        ))
        db.commit()
        db.close()
        return redirect("/vehiculos")
    return render_template("vehiculos_form.html")

@app.route("/vehiculos/editar/<int:id>", methods=["GET", "POST"])
@login_required
@role_required(action='edit')
def editar_vehiculo(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == "POST":
        cursor.execute("""
            UPDATE vehiculos SET modelo=%s, tipo=%s, anio=%s, color=%s, precio_venta=%s, costo_fabricante=%s
            WHERE id=%s
        """, (
            request.form["modelo"],
            request.form["tipo"],
            request.form["anio"],
            request.form["color"],
            request.form["precio"],
            request.form["costo"],
            id
        ))
        db.commit()
        db.close()
        return redirect("/vehiculos")
    cursor.execute("SELECT * FROM vehiculos WHERE id=%s", (id,))
    vehiculo = cursor.fetchone()
    db.close()
    return render_template("vehiculos_form.html", vehiculo=vehiculo)

@app.route("/vehiculos/eliminar/<int:id>")
@login_required
@role_required(action='delete')
def eliminar_vehiculo(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM vehiculos WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/vehiculos")

# ---------------- VENTAS ----------------
@app.route("/ventas")
@login_required
def ventas():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    q = request.args.get('q', '').strip()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if q:
        like = f"%{q}%"
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM ventas v
            JOIN clientes c ON v.cliente_id = c.id
            JOIN almacenes a ON v.almacen_id = a.id
            WHERE v.id LIKE %s OR c.nombre LIKE %s OR v.fecha LIKE %s OR a.ubicacion LIKE %s
        """, (like, like, like, like))
        total = cursor.fetchone()['cnt']
        cursor.execute("""
            SELECT v.id, v.fecha, v.total, c.nombre AS cliente, a.ubicacion AS almacen
            FROM ventas v
            JOIN clientes c ON v.cliente_id = c.id
            JOIN almacenes a ON v.almacen_id = a.id
            WHERE v.id LIKE %s OR c.nombre LIKE %s OR v.fecha LIKE %s OR a.ubicacion LIKE %s
            LIMIT %s OFFSET %s
        """, (like, like, like, like, per_page, offset))
    else:
        cursor.execute("SELECT COUNT(*) AS cnt FROM ventas")
        total = cursor.fetchone()['cnt']
        cursor.execute("""
            SELECT v.id, v.fecha, v.total, c.nombre AS cliente, a.ubicacion AS almacen
            FROM ventas v
            JOIN clientes c ON v.cliente_id = c.id
            JOIN almacenes a ON v.almacen_id = a.id
            LIMIT %s OFFSET %s
        """, (per_page, offset))
    data = cursor.fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    db.close()
    return render_template("ventas.html", ventas=data, page=page, per_page=per_page, total=total, pages=pages, q=q)

@app.route("/ventas/nuevo", methods=["GET", "POST"])
@login_required
@role_required(action='add')
def nueva_venta():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM clientes ORDER BY nombre")
    clientes = cursor.fetchall()
    cursor.execute("SELECT id, ubicacion FROM almacenes ORDER BY ubicacion")
    almacenes = cursor.fetchall()

    lineas = []

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id")
        cliente_nombre = request.form.get("cliente_nombre", "").strip()
        cliente_dni = request.form.get("cliente_dni", "").strip()
        cliente_correo = request.form.get("cliente_correo", "").strip()
        cliente_telefono = request.form.get("cliente_telefono", "").strip()
        cliente_pais = request.form.get("cliente_pais", "").strip()
        cliente_tipo = request.form.get("cliente_tipo", "").strip()
        fecha = request.form.get("fecha", "").strip()
        almacen_id = request.form.get("almacen")

        nombres = request.form.getlist("linea_nombre")
        cantidades = request.form.getlist("linea_cantidad")
        precios = request.form.getlist("linea_precio")
        ivas = request.form.getlist("linea_iva")
        descuentos = request.form.getlist("linea_descuento")

        max_len = max(len(nombres), len(cantidades), len(precios), len(ivas), len(descuentos))
        errors = []

        if not fecha or not almacen_id:
            errors.append("Completa todos los datos de la cabecera")

        if not cliente_id:
            if not cliente_nombre or not cliente_dni:
                errors.append("Indica un cliente existente o completa los datos del nuevo cliente")

        articulos_cache = {}
        for i in range(max_len):
            nombre = (nombres[i] if i < len(nombres) else "").strip()
            cantidad_raw = (cantidades[i] if i < len(cantidades) else "").strip()
            precio_raw = (precios[i] if i < len(precios) else "").strip()
            iva_raw = (ivas[i] if i < len(ivas) else "").strip()
            descuento_raw = (descuentos[i] if i < len(descuentos) else "").strip()

            if not any([nombre, cantidad_raw, precio_raw]):
                continue

            if not nombre:
                errors.append(f"Linea {i + 1}: falta el nombre del articulo")
                continue

            cantidad = to_int_quantity(cantidad_raw)
            precio = to_decimal(precio_raw)
            iva_pct = to_decimal(iva_raw) if iva_raw else Decimal("0")
            descuento_pct = to_decimal(descuento_raw) if descuento_raw else Decimal("0")
            if cantidad is None or cantidad <= 0:
                errors.append(f"Linea {i + 1}: cantidad invalida (solo enteros)")
                continue
            if precio is None or precio < 0:
                errors.append(f"Linea {i + 1}: precio invalido")
                continue
            if iva_pct is None or iva_pct < 0:
                errors.append(f"Linea {i + 1}: IVA invalido")
                continue
            if descuento_pct is None or descuento_pct < 0:
                errors.append(f"Linea {i + 1}: descuento invalido")
                continue

            if nombre in articulos_cache:
                articulo = articulos_cache[nombre]
            else:
                cursor.execute(
                    """
                    SELECT a.id, a.nombre
                    FROM existencias e
                    JOIN articulos a ON a.id = e.articulo_id
                    WHERE e.almacen_id = %s AND a.nombre = %s
                    """,
                    (almacen_id, nombre)
                )
                articulo = cursor.fetchone()
                articulos_cache[nombre] = articulo

            if not articulo:
                errors.append(f"Linea {i + 1}: el articulo no existe en el almacen seleccionado")
                continue

            articulo_id = articulo['id']
            nombre_final = articulo['nombre']

            base = Decimal(cantidad) * precio
            total_con_iva = base * (Decimal("1") + (iva_pct / Decimal("100")))
            total_linea = total_con_iva * (Decimal("1") - (descuento_pct / Decimal("100")))

            lineas.append({
                "nombre": nombre_final or nombre,
                "cantidad": cantidad,
                "precio": precio,
                "iva_pct": iva_pct,
                "descuento_pct": descuento_pct,
                "total": quantize_money(total_linea),
                "articulo_id": articulo_id
            })

        if not lineas:
            errors.append("Agrega al menos una linea de venta")

        if errors:
            for err in errors:
                flash(err, "error")
            db.close()
            if not lineas:
                lineas = [{} for _ in range(3)]
            return render_template(
                "ventas_form.html",
                clientes=clientes,
                almacenes=almacenes,
                lineas=lineas,
                cabecera={
                    "cliente_id": cliente_id,
                    "cliente_nombre": cliente_nombre,
                    "cliente_dni": cliente_dni,
                    "cliente_correo": cliente_correo,
                    "cliente_telefono": cliente_telefono,
                    "cliente_pais": cliente_pais,
                    "cliente_tipo": cliente_tipo,
                    "fecha": fecha,
                    "almacen_id": almacen_id
                }
            )

        total_venta = quantize_money(sum((l["total"] for l in lineas), Decimal("0")))
        total_unidades = sum((l["cantidad"] for l in lineas), 0)

        try:
            cur2 = db.cursor(dictionary=True)
            cur2.execute(
                "SELECT id FROM almacenes WHERE id=%s FOR UPDATE",
                (almacen_id,)
            )
            almacen = cur2.fetchone()
            if not almacen:
                raise ValueError("Almacen no encontrado")

            cur2 = db.cursor()

            required = {}
            for linea in lineas:
                required[linea["articulo_id"]] = required.get(linea["articulo_id"], 0) + linea["cantidad"]

            placeholders = ", ".join(["%s"] * len(required))
            cur3 = db.cursor(dictionary=True)
            cur3.execute(
                f"""
                SELECT articulo_id, cantidad
                FROM existencias
                WHERE almacen_id=%s AND articulo_id IN ({placeholders})
                FOR UPDATE
                """,
                (almacen_id, *required.keys())
            )
            stock_rows = cur3.fetchall()
            stock_map = {row["articulo_id"]: (to_int_quantity(row["cantidad"]) or 0) for row in stock_rows}

            for articulo_id, qty in required.items():
                disponible = stock_map.get(articulo_id, 0)
                if disponible < qty:
                    nombre_articulo = next((l["nombre"] for l in lineas if l["articulo_id"] == articulo_id), f"ID {articulo_id}")
                    raise ValueError(f"Stock insuficiente para el articulo {nombre_articulo}")

            if not cliente_id:
                cur2.execute(
                    """
                    INSERT INTO clientes (nombre, dni, correo, telefono, pais, tipo)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        cliente_nombre,
                        cliente_dni,
                        cliente_correo or None,
                        cliente_telefono or None,
                        cliente_pais or None,
                        cliente_tipo or None
                    )
                )
                cliente_id = cur2.lastrowid

            cur2.execute(
                """
                INSERT INTO ventas (fecha, total, cliente_id, almacen_id)
                VALUES (%s, %s, %s, %s)
                """,
                (fecha, total_venta, cliente_id, almacen_id)
            )
            venta_id = cur2.lastrowid

            for idx, linea in enumerate(lineas, start=1):
                cur2.execute(
                    """
                    INSERT INTO ventas_lineas
                    (venta_id, linea_num, articulo_id, cantidad, precio_venta, iva_pct, descuento_pct, total_linea)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        venta_id,
                        idx,
                        linea["articulo_id"],
                        linea["cantidad"],
                        linea["precio"],
                        linea["iva_pct"],
                        linea["descuento_pct"],
                        linea["total"]
                    )
                )

                cur2.execute(
                    """
                    INSERT INTO existencias (almacen_id, articulo_id, cantidad)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE cantidad = cantidad - VALUES(cantidad)
                    """,
                    (almacen_id, linea["articulo_id"], linea["cantidad"])
                )

            cur2.execute(
                "UPDATE almacenes SET disponible = disponible + %s WHERE id=%s",
                (total_unidades, almacen_id)
            )

            db.commit()
            db.close()
            flash("Factura de venta guardada", "success")
            return redirect("/ventas")
        except Exception as e:
            db.rollback()
            db.close()
            flash(f"Error al guardar la venta: {e}", "error")
            return render_template(
                "ventas_form.html",
                clientes=clientes,
                almacenes=almacenes,
                lineas=lineas,
                cabecera={
                    "cliente_id": cliente_id,
                    "cliente_nombre": cliente_nombre,
                    "cliente_dni": cliente_dni,
                    "cliente_correo": cliente_correo,
                    "cliente_telefono": cliente_telefono,
                    "cliente_pais": cliente_pais,
                    "cliente_tipo": cliente_tipo,
                    "fecha": fecha,
                    "almacen_id": almacen_id
                }
            )

    db.close()
    lineas = [{} for _ in range(3)]
    return render_template(
        "ventas_form.html",
        clientes=clientes,
        almacenes=almacenes,
        lineas=lineas,
        cabecera={}
    )

@app.route("/ventas/editar/<int:id>", methods=["GET", "POST"])
@login_required
@role_required(action='edit')
def editar_venta(id):
    flash("La edicion de ventas no esta disponible. Elimina y crea una nueva.", "error")
    return redirect("/ventas")


@app.route("/ventas/<int:id>")
@login_required
def venta_detalle(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT v.id, v.fecha, v.total,
               c.id AS cliente_id, c.nombre AS cliente,
               a.id AS almacen_id, a.ubicacion AS almacen
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        JOIN almacenes a ON v.almacen_id = a.id
        WHERE v.id = %s
        """,
        (id,)
    )
    venta = cursor.fetchone()
    if not venta:
        db.close()
        flash("Venta no encontrada", "error")
        return redirect("/ventas")

    cursor.execute(
        """
        SELECT vl.linea_num, a.nombre, vl.cantidad, vl.precio_venta,
               vl.iva_pct, vl.descuento_pct, vl.total_linea
        FROM ventas_lineas vl
        JOIN articulos a ON vl.articulo_id = a.id
        WHERE vl.venta_id = %s
        ORDER BY vl.linea_num ASC
        """,
        (id,)
    )
    lineas = cursor.fetchall()
    db.close()
    return render_template("ventas_detalle.html", venta=venta, lineas=lineas)

@app.route("/ventas/eliminar/<int:id>")
@login_required
@role_required(action='delete')
def eliminar_venta(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT almacen_id FROM ventas WHERE id=%s", (id,))
    venta = cursor.fetchone()
    if not venta:
        db.close()
        flash("Venta no encontrada", "error")
        return redirect("/ventas")

    cursor.execute(
        """
        SELECT articulo_id, cantidad
        FROM ventas_lineas
        WHERE venta_id = %s
        """,
        (id,)
    )
    lineas = cursor.fetchall()

    try:
        cur2 = db.cursor()
        total_unidades = sum((to_int_quantity(l['cantidad']) or 0 for l in lineas), 0)
        for linea in lineas:
            cantidad_linea = to_int_quantity(linea['cantidad']) or 0
            cur2.execute(
                """
                INSERT INTO existencias (almacen_id, articulo_id, cantidad)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE cantidad = cantidad + VALUES(cantidad)
                """,
                (venta['almacen_id'], linea['articulo_id'], cantidad_linea)
            )

        cur2.execute(
            "UPDATE almacenes SET disponible = disponible - %s WHERE id=%s",
            (total_unidades, venta['almacen_id'])
        )

        cur2.execute("DELETE FROM ventas WHERE id=%s", (id,))
        db.commit()
        db.close()
        flash("Venta eliminada", "success")
        return redirect("/ventas")
    except Exception as e:
        db.rollback()
        db.close()
        flash(f"Error al eliminar la venta: {e}", "error")
        return redirect("/ventas")

# ---------------- ALMACENES ----------------
@app.route("/almacenes")
@login_required
def almacenes():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    q = request.args.get('q', '').strip()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    params = []
    where = ''
    if q:
        like = f"%{q}%"
        where = "WHERE ubicacion LIKE %s OR tipo_almacen LIKE %s"
        params = [like, like]
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM almacenes {where}", tuple(params))
    total = cursor.fetchone()['cnt']
    params2 = params + [per_page, offset]
    cursor.execute(f"SELECT * FROM almacenes {where} LIMIT %s OFFSET %s", tuple(params2))
    data = cursor.fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    db.close()
    return render_template("almacenes.html", almacenes=data, page=page, per_page=per_page, total=total, pages=pages, q=q)

@app.route("/almacenes/<int:id>/detalle")
@login_required
def detalle_almacen(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Obtener información del almacén
    cursor.execute("SELECT * FROM almacenes WHERE id=%s", (id,))
    almacen = cursor.fetchone()
    
    if not almacen:
        db.close()
        flash("Almacén no encontrado", "error")
        return redirect("/almacenes")
    
    # Obtener artículos/existencias en el almacén
    cursor.execute("""
        SELECT 
            e.articulo_id,
            a.nombre,
            e.cantidad
        FROM existencias e
        JOIN articulos a ON e.articulo_id = a.id
        WHERE e.almacen_id = %s
        ORDER BY a.nombre
    """, (id,))
    articulos = cursor.fetchall()

    # Obtener vehículos terminados en el almacén (si existen)
    cursor.execute(
        """
        SELECT
            sv.vehiculo_id,
            v.modelo,
            sv.cantidad
        FROM stock_vehiculos sv
        JOIN vehiculos v ON sv.vehiculo_id = v.id
        WHERE sv.almacen_id = %s
        ORDER BY v.modelo
        """,
        (id,)
    )
    vehiculos = cursor.fetchall()
    
    # Calcular ocupación total (artículos + vehículos terminados)
    cantidad_articulos = sum((to_int_quantity(art['cantidad']) or 0) for art in articulos) if articulos else 0
    cantidad_vehiculos = sum((to_int_quantity(v['cantidad']) or 0) for v in vehiculos) if vehiculos else 0
    cantidad_total = cantidad_articulos + cantidad_vehiculos
    
    # Calcular porcentaje de ocupación
    capacidad = int(almacen['capacidad']) if almacen['capacidad'] else 1
    porcentaje_ocupado = (cantidad_total / capacidad * 100) if capacidad > 0 else 0
    porcentaje_disponible = 100 - porcentaje_ocupado
    
    db.close()
    
    return render_template("almacenes_detalle.html", 
                         almacen=almacen, 
                         articulos=articulos,
                         vehiculos=vehiculos,
                         cantidad_articulos=cantidad_articulos,
                         cantidad_vehiculos=cantidad_vehiculos,
                         cantidad_total=cantidad_total,
                         porcentaje_ocupado=porcentaje_ocupado,
                         porcentaje_disponible=porcentaje_disponible)

@app.route("/almacenes/nuevo", methods=["GET", "POST"])
@login_required
@role_required(action='add')
def nuevo_almacen():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO almacenes VALUES (NULL,%s,%s,%s,%s,%s)
        """, (
            request.form["ubicacion"],
            request.form["correo"],
            request.form["tipo_almacen"],
            request.form["capacidad"],
            request.form["disponible"]
        ))
        db.commit()
        db.close()
        return redirect("/almacenes")
    return render_template("almacenes_form.html", almacen=None)

@app.route("/almacenes/editar/<int:id>", methods=["GET", "POST"])
@login_required
@role_required(action='edit')
def editar_almacen(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == "POST":
        cursor.execute("""
            UPDATE almacenes SET ubicacion=%s, correo=%s, tipo_almacen=%s, capacidad=%s, disponible=%s WHERE id=%s
        """, (
            request.form["ubicacion"],
            request.form["correo"],
            request.form["tipo_almacen"],
            request.form["capacidad"],
            request.form["disponible"],
            id
        ))
        db.commit()
        db.close()
        return redirect("/almacenes")
    cursor.execute("SELECT * FROM almacenes WHERE id=%s", (id,))
    almacen = cursor.fetchone()
    db.close()
    return render_template("almacenes_form.html", almacen=almacen)

@app.route("/almacenes/eliminar/<int:id>")
@login_required
@role_required(action='delete')
def eliminar_almacen(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM almacenes WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/almacenes")


@app.route("/almacenes/<int:almacen_id>/articulos/<int:articulo_id>/eliminar", methods=["POST"])
@login_required
@role_required(action='delete')
def eliminar_articulo_almacen(almacen_id, articulo_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT e.cantidad, a.nombre
        FROM existencias e
        JOIN articulos a ON a.id = e.articulo_id
        WHERE e.almacen_id = %s AND e.articulo_id = %s
        FOR UPDATE
        """,
        (almacen_id, articulo_id)
    )
    row = cursor.fetchone()

    if not row:
        db.close()
        flash("Artículo no encontrado en este almacén", "error")
        return redirect(f"/almacenes/{almacen_id}/detalle")

    cantidad = to_int_quantity(row["cantidad"]) or 0

    try:
        cur2 = db.cursor()
        cur2.execute(
            "DELETE FROM existencias WHERE almacen_id=%s AND articulo_id=%s",
            (almacen_id, articulo_id)
        )
        cur2.execute(
            "UPDATE almacenes SET disponible = disponible + %s WHERE id=%s",
            (cantidad, almacen_id)
        )
        db.commit()
        db.close()
        flash(f"Artículo '{row['nombre']}' eliminado del almacén", "success")
        return redirect(f"/almacenes/{almacen_id}/detalle")
    except Exception as e:
        db.rollback()
        db.close()
        flash(f"Error al eliminar el artículo: {e}", "error")
        return redirect(f"/almacenes/{almacen_id}/detalle")



# ---------------- PROVEEDORES ----------------
@app.route("/proveedores")
@login_required
def proveedores():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    q = request.args.get('q', '').strip()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    params = []
    where = ''
    if q:
        like = f"%{q}%"
        where = "WHERE nombre LIKE %s OR dni LIKE %s OR correo LIKE %s"
        params = [like, like, like]
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM proveedores {where}", tuple(params))
    total = cursor.fetchone()['cnt']
    params2 = params + [per_page, offset]
    cursor.execute(f"SELECT * FROM proveedores {where} LIMIT %s OFFSET %s", tuple(params2))
    data = cursor.fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    db.close()
    return render_template("proveedores.html", proveedores=data, page=page, per_page=per_page, total=total, pages=pages, q=q)


@app.before_request
def ensure_role_column():
    # Run once per app lifetime: ensure the 'role' column exists and set initial 'jefe' for admin@example.com
    if app.config.get('ROLE_COLUMN_CHECKED'):
        return
    db = None
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME='role'", ('erp_toyota','empleados'))
        exists = cur.fetchone()[0]
        if not exists:
            cur.execute("ALTER TABLE empleados ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'empleado'")
            db.commit()
            print('Added role column to empleados')
        try:
            cur.execute("UPDATE empleados SET role='jefe' WHERE correo=%s", ('admin@example.com',))
            db.commit()
        except Exception:
            pass
        cur.close()
        app.config['ROLE_COLUMN_CHECKED'] = True
    except Exception as e:
        print('ensure_role_column error:', e)
    finally:
        if db:
            db.close()

@app.route("/proveedores/nuevo", methods=["GET", "POST"])
@login_required
@role_required(action='add')
def nuevo_proveedor():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO proveedores VALUES (NULL,%s,%s,%s,%s,%s)
        """, (
            request.form["nombre"],
            request.form["dni"],
            request.form["correo"],
            request.form["contacto"],
            request.form["tipo_suministro"]
        ))
        db.commit()
        db.close()
        return redirect("/proveedores")
    return render_template("proveedores_form.html", proveedor=None)

@app.route("/proveedores/editar/<int:id>", methods=["GET", "POST"])
@login_required
@role_required(action='edit')
def editar_proveedor(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        cursor.execute("""
            UPDATE proveedores
            SET nombre=%s, dni=%s, correo=%s, contacto=%s, tipo_suministro=%s
            WHERE id=%s
        """, (
            request.form["nombre"],
            request.form["dni"],
            request.form["correo"],
            request.form["contacto"],
            request.form["tipo_suministro"],
            id
        ))
        db.commit()
        db.close()
        return redirect("/proveedores")

    # GET: traer datos del proveedor a editar
    cursor.execute("SELECT * FROM proveedores WHERE id=%s", (id,))
    proveedor = cursor.fetchone()
    db.close()
    return render_template("proveedores_form.html", proveedor=proveedor)

@app.route("/proveedores/eliminar/<int:id>")
@login_required
@role_required(action='delete')
def eliminar_proveedor(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM proveedores WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/proveedores")


@app.route("/proveedores/buscar")
@login_required
def buscar_proveedores():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    like = f"%{q}%"
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, nombre, dni, correo, contacto, tipo_suministro
        FROM proveedores
        WHERE nombre LIKE %s OR dni LIKE %s
        ORDER BY nombre
        LIMIT 10
        """,
        (like, like)
    )
    data = cursor.fetchall()
    db.close()
    return jsonify(data)


# ---------------- COMPRAS ----------------
@app.route("/compras")
@login_required
def compras():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    proveedor = request.args.get('proveedor', '').strip()
    fecha = request.args.get('fecha', '').strip()

    where_clauses = []
    params = []
    if proveedor:
        like = f"%{proveedor}%"
        where_clauses.append("(p.nombre LIKE %s OR CAST(p.id AS CHAR) LIKE %s)")
        params.extend([like, like])
    if fecha:
        where_clauses.append("c.fecha = %s")
        params.append(fecha)

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(f"""
        SELECT COUNT(*) AS cnt
        FROM compras c
        JOIN proveedores p ON c.proveedor_id = p.id
        {where_sql}
    """, tuple(params))
    total = cursor.fetchone()['cnt']

    cursor.execute(f"""
        SELECT c.id, c.fecha, c.total,
               p.nombre AS proveedor, a.ubicacion AS almacen
        FROM compras c
        JOIN proveedores p ON c.proveedor_id = p.id
        JOIN almacenes a ON c.almacen_id = a.id
        {where_sql}
        ORDER BY c.id DESC
        LIMIT %s OFFSET %s
    """, tuple(params + [per_page, offset]))
    data = cursor.fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    db.close()
    return render_template(
        "compras.html",
        compras=data,
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        proveedor=proveedor,
        fecha=fecha
    )


@app.route("/compras/nuevo", methods=["GET", "POST"])
@login_required
@role_required(action='add')
def nueva_compra():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
    proveedores = cursor.fetchall()
    cursor.execute("SELECT id, ubicacion FROM almacenes ORDER BY ubicacion")
    almacenes = cursor.fetchall()

    lineas = []
    if request.method == "POST":
        proveedor_id = request.form.get("proveedor_id")
        proveedor_nombre = request.form.get("proveedor_nombre", "").strip()
        proveedor_apellido = request.form.get("proveedor_apellido", "").strip()
        proveedor_dni = request.form.get("proveedor_dni", "").strip()
        proveedor_correo = request.form.get("proveedor_correo", "").strip()
        proveedor_contacto = request.form.get("proveedor_contacto", "").strip()
        proveedor_tipo = request.form.get("proveedor_tipo", "").strip()
        fecha = request.form.get("fecha", "").strip()
        almacen_id = request.form.get("almacen")

        nombres = request.form.getlist("linea_nombre")
        cantidades = request.form.getlist("linea_cantidad")
        precios = request.form.getlist("linea_precio")
        ivas = request.form.getlist("linea_iva")
        descuentos = request.form.getlist("linea_descuento")

        max_len = max(len(nombres), len(cantidades), len(precios), len(ivas), len(descuentos))
        errors = []

        if not fecha or not almacen_id:
            errors.append("Completa todos los datos de la cabecera")

        if not proveedor_id:
            if not proveedor_nombre or not proveedor_dni:
                errors.append("Indica un proveedor existente o completa los datos del nuevo proveedor")

        articulos_cache = {}
        for i in range(max_len):
            nombre = (nombres[i] if i < len(nombres) else "").strip()
            cantidad_raw = (cantidades[i] if i < len(cantidades) else "").strip()
            precio_raw = (precios[i] if i < len(precios) else "").strip()
            iva_raw = (ivas[i] if i < len(ivas) else "").strip()
            descuento_raw = (descuentos[i] if i < len(descuentos) else "").strip()

            if not any([nombre, cantidad_raw, precio_raw]):
                continue

            if not nombre:
                errors.append(f"Linea {i + 1}: falta el nombre del articulo")
                continue

            cantidad = to_int_quantity(cantidad_raw)
            precio = to_decimal(precio_raw)
            iva_pct = to_decimal(iva_raw) if iva_raw else Decimal("0")
            descuento_pct = to_decimal(descuento_raw) if descuento_raw else Decimal("0")
            if cantidad is None or cantidad <= 0:
                errors.append(f"Linea {i + 1}: cantidad invalida (solo enteros)")
                continue
            if precio is None or precio < 0:
                errors.append(f"Linea {i + 1}: precio invalido")
                continue
            if iva_pct is None or iva_pct < 0:
                errors.append(f"Linea {i + 1}: IVA invalido")
                continue
            if descuento_pct is None or descuento_pct < 0:
                errors.append(f"Linea {i + 1}: descuento invalido")
                continue

            if nombre in articulos_cache:
                articulo = articulos_cache[nombre]
            else:
                cursor.execute("SELECT id, nombre FROM articulos WHERE nombre=%s", (nombre,))
                articulo = cursor.fetchone()
                articulos_cache[nombre] = articulo

            articulo_id = articulo['id'] if articulo else None
            nombre_final = articulo['nombre'] if articulo else nombre

            base = Decimal(cantidad) * precio
            total_con_iva = base * (Decimal("1") + (iva_pct / Decimal("100")))
            total_linea = total_con_iva * (Decimal("1") - (descuento_pct / Decimal("100")))

            lineas.append({
                "nombre": nombre_final or nombre,
                "cantidad": cantidad,
                "precio": precio,
                "iva_pct": iva_pct,
                "descuento_pct": descuento_pct,
                "total": quantize_money(total_linea),
                "articulo_id": articulo_id,
                "actualizar_nombre": bool(articulo and nombre and nombre != articulo['nombre'])
            })

        if not lineas:
            errors.append("Agrega al menos una linea de compra")

        if errors:
            for err in errors:
                flash(err, "error")
            db.close()
            if not lineas:
                lineas = [{} for _ in range(3)]
            return render_template(
                "compras_form.html",
                proveedores=proveedores,
                almacenes=almacenes,
                lineas=lineas,
                cabecera={
                    "proveedor_id": proveedor_id,
                    "proveedor_nombre": proveedor_nombre,
                    "proveedor_apellido": proveedor_apellido,
                    "proveedor_dni": proveedor_dni,
                    "proveedor_correo": proveedor_correo,
                    "proveedor_contacto": proveedor_contacto,
                    "proveedor_tipo": proveedor_tipo,
                    "fecha": fecha,
                    "almacen_id": almacen_id
                }
            )

        total_compra = quantize_money(sum((l["total"] for l in lineas), Decimal("0")))
        total_unidades = sum((l["cantidad"] for l in lineas), 0)

        try:
            cur2 = db.cursor(dictionary=True)
            cur2.execute(
                "SELECT disponible FROM almacenes WHERE id=%s FOR UPDATE",
                (almacen_id,)
            )
            almacen = cur2.fetchone()
            if not almacen:
                raise ValueError("Almacen no encontrado")
            disponible = to_int_quantity(almacen.get("disponible")) or 0
            if disponible - total_unidades < 0:
                raise ValueError("No hay espacio disponible suficiente en el almacen seleccionado")

            cur2 = db.cursor()
            articulo_ids_creados = {}
            for linea in lineas:
                if linea["articulo_id"] is None:
                    if linea["nombre"] in articulo_ids_creados:
                        linea["articulo_id"] = articulo_ids_creados[linea["nombre"]]
                    else:
                        cur2.execute(
                            "INSERT INTO articulos (nombre) VALUES (%s)",
                            (linea["nombre"],)
                        )
                        linea["articulo_id"] = cur2.lastrowid
                        articulo_ids_creados[linea["nombre"]] = linea["articulo_id"]
                elif linea["actualizar_nombre"]:
                    cur2.execute(
                        "UPDATE articulos SET nombre=%s WHERE id=%s",
                        (linea["nombre"], linea["articulo_id"])
                    )

            if not proveedor_id:
                proveedor_full = proveedor_nombre
                if proveedor_apellido:
                    proveedor_full = f"{proveedor_nombre} {proveedor_apellido}".strip()
                cur2.execute(
                    """
                    INSERT INTO proveedores (nombre, dni, correo, contacto, tipo_suministro)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        proveedor_full,
                        proveedor_dni,
                        proveedor_correo or None,
                        proveedor_contacto or None,
                        proveedor_tipo or None
                    )
                )
                proveedor_id = cur2.lastrowid

            cur2.execute(
                """
                INSERT INTO compras (proveedor_id, fecha, almacen_id, total)
                VALUES (%s, %s, %s, %s)
                """,
                (proveedor_id, fecha, almacen_id, total_compra)
            )
            compra_id = cur2.lastrowid

            for idx, linea in enumerate(lineas, start=1):
                cur2.execute(
                    """
                    INSERT INTO compras_lineas
                    (compra_id, linea_num, articulo_id, cantidad, precio_compra, iva_pct, descuento_pct, total_linea)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        compra_id,
                        idx,
                        linea["articulo_id"],
                        linea["cantidad"],
                        linea["precio"],
                        linea["iva_pct"],
                        linea["descuento_pct"],
                        linea["total"]
                    )
                )

                cur2.execute(
                    """
                    INSERT INTO existencias (almacen_id, articulo_id, cantidad)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE cantidad = cantidad + VALUES(cantidad)
                    """,
                    (almacen_id, linea["articulo_id"], linea["cantidad"])
                )

            cur2.execute(
                "UPDATE almacenes SET disponible = disponible - %s WHERE id=%s",
                (total_unidades, almacen_id)
            )

            db.commit()
            db.close()
            flash("Factura de compra guardada", "success")
            return redirect("/compras")
        except Exception as e:
            db.rollback()
            db.close()
            flash(f"Error al guardar la compra: {e}", "error")
            return render_template(
                "compras_form.html",
                proveedores=proveedores,
                almacenes=almacenes,
                lineas=lineas,
                cabecera={
                    "proveedor_id": proveedor_id,
                    "proveedor_nombre": proveedor_nombre,
                    "proveedor_apellido": proveedor_apellido,
                    "proveedor_dni": proveedor_dni,
                    "proveedor_correo": proveedor_correo,
                    "proveedor_contacto": proveedor_contacto,
                    "proveedor_tipo": proveedor_tipo,
                    "fecha": fecha,
                    "almacen_id": almacen_id
                }
            )

    db.close()
    
    # Precargar artículo desde parámetros de consulta (para fabricación)
    lineas = [{} for _ in range(3)]
    articulo_id = request.args.get("articulo_id")
    cantidad_str = request.args.get("cantidad", "")
    
    if articulo_id:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, nombre FROM articulos WHERE id=%s", (articulo_id,))
        articulo = cursor.fetchone()
        db.close()
        
        if articulo:
            cantidad = to_int_quantity(cantidad_str) if cantidad_str else 1
            lineas[0] = {
                "nombre": articulo['nombre'],
                "cantidad": cantidad,
                "precio": "",
                "iva_pct": "",
                "descuento_pct": ""
            }
    
    return render_template(
        "compras_form.html",
        proveedores=proveedores,
        almacenes=almacenes,
        lineas=lineas,
        cabecera={}
    )


@app.route("/compras/<int:id>")
@login_required
def compra_detalle(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT c.id, c.fecha, c.total,
               p.id AS proveedor_id, p.nombre AS proveedor,
               a.id AS almacen_id, a.ubicacion AS almacen
        FROM compras c
        JOIN proveedores p ON c.proveedor_id = p.id
        JOIN almacenes a ON c.almacen_id = a.id
        WHERE c.id = %s
        """,
        (id,)
    )
    compra = cursor.fetchone()
    if not compra:
        db.close()
        flash("Compra no encontrada", "error")
        return redirect("/compras")

    cursor.execute(
        """
         SELECT cl.linea_num, a.nombre, cl.cantidad, cl.precio_compra,
             cl.iva_pct, cl.descuento_pct, cl.total_linea
        FROM compras_lineas cl
        JOIN articulos a ON cl.articulo_id = a.id
        WHERE cl.compra_id = %s
        ORDER BY cl.linea_num ASC
        """,
        (id,)
    )
    lineas = cursor.fetchall()
    db.close()
    return render_template("compras_detalle.html", compra=compra, lineas=lineas)


@app.route("/compras/eliminar/<int:id>")
@login_required
@role_required(action='delete')
def eliminar_compra(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT almacen_id FROM compras WHERE id=%s", (id,))
    compra = cursor.fetchone()
    if not compra:
        db.close()
        flash("Compra no encontrada", "error")
        return redirect("/compras")

    cursor.execute(
        """
        SELECT articulo_id, cantidad
        FROM compras_lineas
        WHERE compra_id = %s
        """,
        (id,)
    )
    lineas = cursor.fetchall()

    try:
        cur2 = db.cursor()
        total_unidades = sum((to_int_quantity(l['cantidad']) or 0 for l in lineas), 0)
        for linea in lineas:
            cantidad_linea = to_int_quantity(linea['cantidad']) or 0
            cur2.execute(
                """
                INSERT INTO existencias (almacen_id, articulo_id, cantidad)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE cantidad = cantidad + VALUES(cantidad)
                """,
                (compra['almacen_id'], linea['articulo_id'], -cantidad_linea)
            )

        cur2.execute(
            "UPDATE almacenes SET disponible = disponible + %s WHERE id=%s",
            (total_unidades, compra['almacen_id'])
        )

        cur2.execute("DELETE FROM compras WHERE id=%s", (id,))
        db.commit()
        db.close()
        flash("Compra eliminada", "success")
        return redirect("/compras")
    except Exception as e:
        db.rollback()
        db.close()
        flash(f"Error al eliminar la compra: {e}", "error")
        return redirect("/compras")


# ---------------- FABRICACION ----------------
@app.route("/fabricacion")
@login_required
def fabricacion():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    q = request.args.get('q', '').strip()

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if q:
        like = f"%{q}%"
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM fabricacion_ordenes fo
            JOIN vehiculos v ON fo.vehiculo_id = v.id
            JOIN almacenes a ON fo.almacen_destino_id = a.id
            WHERE fo.id LIKE %s OR v.modelo LIKE %s OR a.ubicacion LIKE %s OR fo.estado LIKE %s
            """,
            (like, like, like, like)
        )
        total = cursor.fetchone()['cnt']
        cursor.execute(
            """
            SELECT fo.id, fo.fecha, fo.cantidad, fo.estado, fo.observaciones,
                   v.modelo AS vehiculo,
                   a.ubicacion AS almacen_destino
            FROM fabricacion_ordenes fo
            JOIN vehiculos v ON fo.vehiculo_id = v.id
            JOIN almacenes a ON fo.almacen_destino_id = a.id
            WHERE fo.id LIKE %s OR v.modelo LIKE %s OR a.ubicacion LIKE %s OR fo.estado LIKE %s
            ORDER BY fo.id DESC
            LIMIT %s OFFSET %s
            """,
            (like, like, like, like, per_page, offset)
        )
    else:
        cursor.execute("SELECT COUNT(*) AS cnt FROM fabricacion_ordenes")
        total = cursor.fetchone()['cnt']
        cursor.execute(
            """
            SELECT fo.id, fo.fecha, fo.cantidad, fo.estado, fo.observaciones,
                   v.modelo AS vehiculo,
                   a.ubicacion AS almacen_destino
            FROM fabricacion_ordenes fo
            JOIN vehiculos v ON fo.vehiculo_id = v.id
            JOIN almacenes a ON fo.almacen_destino_id = a.id
            ORDER BY fo.id DESC
            LIMIT %s OFFSET %s
            """,
            (per_page, offset)
        )

    ordenes = cursor.fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    db.close()

    return render_template(
        "fabricacion.html",
        ordenes=ordenes,
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        q=q
    )


@app.route("/fabricacion/nueva", methods=["GET", "POST"])
@login_required
@role_required(action='add')
def nueva_fabricacion():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT id, modelo, tipo, anio FROM vehiculos ORDER BY modelo")
    vehiculos = cursor.fetchall()

    cursor.execute("SELECT id, ubicacion, disponible FROM almacenes WHERE tipo_almacen='Vehiculos' ORDER BY ubicacion")
    almacenes_destino = cursor.fetchall()

    if request.method == "POST":
        vehiculo_id = request.form.get("vehiculo_id")
        almacen_destino_id = request.form.get("almacen_destino_id")
        cantidad_raw = request.form.get("cantidad", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        errors = []
        cantidad = to_int_quantity(cantidad_raw)
        if not vehiculo_id:
            errors.append("Selecciona un vehículo")
        if not almacen_destino_id:
            errors.append("Selecciona un almacén destino de vehículos")
        if cantidad is None or cantidad <= 0:
            errors.append("La cantidad a fabricar debe ser un entero mayor a 0")

        if errors:
            for err in errors:
                flash(err, "error")
            db.close()
            return render_template(
                "fabricacion_form.html",
                vehiculos=vehiculos,
                almacenes_destino=almacenes_destino,
                cabecera={
                    "vehiculo_id": vehiculo_id,
                    "almacen_destino_id": almacen_destino_id,
                    "cantidad": cantidad_raw,
                    "observaciones": observaciones,
                }
            )

        try:
            c_lock = db.cursor(dictionary=True)

            c_lock.execute(
                "SELECT id, disponible, tipo_almacen FROM almacenes WHERE id=%s FOR UPDATE",
                (almacen_destino_id,)
            )
            almacen_destino = c_lock.fetchone()
            if not almacen_destino:
                raise ValueError("Almacén destino no encontrado")
            if almacen_destino['tipo_almacen'] != 'Vehiculos':
                raise ValueError("El almacén destino debe ser de tipo 'Vehiculos'")

            disponible_destino = to_int_quantity(almacen_destino.get('disponible')) or 0
            if disponible_destino < cantidad:
                raise ValueError("No hay capacidad disponible suficiente en el almacén destino")

            c_lock.execute(
                """
                SELECT articulo_id, cantidad_por_unidad
                FROM fabricacion_bom
                WHERE vehiculo_id = %s
                """,
                (vehiculo_id,)
            )
            bom_rows = c_lock.fetchall()
            if not bom_rows:
                raise ValueError("El vehículo seleccionado no tiene BOM definido")

            required = {}
            for row in bom_rows:
                qpu = to_int_quantity(row['cantidad_por_unidad'])
                if qpu is None or qpu <= 0:
                    raise ValueError("La BOM contiene cantidades inválidas (deben ser enteras)")
                req = qpu * cantidad
                required[row['articulo_id']] = req

            allocations = []
            consumed_by_almacen = {}

            for articulo_id, qty_required in required.items():
                remaining = qty_required
                c_lock.execute(
                    """
                    SELECT e.almacen_id, e.cantidad
                    FROM existencias e
                    JOIN almacenes a ON a.id = e.almacen_id
                    WHERE e.articulo_id = %s
                      AND a.tipo_almacen <> 'Vehiculos'
                      AND e.cantidad > 0
                    ORDER BY e.cantidad DESC
                    FOR UPDATE
                    """,
                    (articulo_id,)
                )
                stocks = c_lock.fetchall()

                for stock in stocks:
                    if remaining <= 0:
                        break
                    available = to_int_quantity(stock['cantidad']) or 0
                    if available <= 0:
                        continue
                    take = available if available <= remaining else remaining
                    if take <= 0:
                        continue

                    allocations.append({
                        "articulo_id": articulo_id,
                        "almacen_origen_id": stock['almacen_id'],
                        "cantidad": take
                    })

                    consumed_by_almacen[stock['almacen_id']] = (
                        consumed_by_almacen.get(stock['almacen_id'], 0) + take
                    )
                    remaining = remaining - take

                if remaining > 0:
                    c_lock.execute("SELECT nombre FROM articulos WHERE id=%s", (articulo_id,))
                    art = c_lock.fetchone()
                    nombre = art['nombre'] if art else f"ID {articulo_id}"
                    raise ValueError(f"Stock insuficiente para el artículo {nombre}")

            c_write = db.cursor()
            c_write.execute(
                """
                INSERT INTO fabricacion_ordenes (vehiculo_id, cantidad, almacen_destino_id, estado, observaciones)
                VALUES (%s, %s, %s, 'confirmada', %s)
                """,
                (vehiculo_id, cantidad, almacen_destino_id, observaciones or None)
            )
            orden_id = c_write.lastrowid

            for alloc in allocations:
                c_write.execute(
                    """
                    INSERT INTO fabricacion_consumos (orden_id, articulo_id, almacen_origen_id, cantidad)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (orden_id, alloc['articulo_id'], alloc['almacen_origen_id'], alloc['cantidad'])
                )

                c_write.execute(
                    """
                    UPDATE existencias
                    SET cantidad = cantidad - %s
                    WHERE almacen_id = %s AND articulo_id = %s
                    """,
                    (alloc['cantidad'], alloc['almacen_origen_id'], alloc['articulo_id'])
                )

            for almacen_origen_id, cantidad_consumida in consumed_by_almacen.items():
                c_write.execute(
                    "UPDATE almacenes SET disponible = disponible + %s WHERE id = %s",
                    (cantidad_consumida, almacen_origen_id)
                )

            c_write.execute(
                "UPDATE almacenes SET disponible = disponible - %s WHERE id = %s",
                (cantidad, almacen_destino_id)
            )

            c_write.execute(
                """
                INSERT INTO stock_vehiculos (almacen_id, vehiculo_id, cantidad)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE cantidad = cantidad + VALUES(cantidad)
                """,
                (almacen_destino_id, vehiculo_id, cantidad)
            )

            db.commit()
            db.close()
            flash("Orden de fabricación confirmada", "success")
            return redirect(f"/fabricacion/{orden_id}")
        except Exception as e:
            db.rollback()
            db.close()
            flash(f"Error al confirmar la fabricación: {e}", "error")
            return render_template(
                "fabricacion_form.html",
                vehiculos=vehiculos,
                almacenes_destino=almacenes_destino,
                cabecera={
                    "vehiculo_id": vehiculo_id,
                    "almacen_destino_id": almacen_destino_id,
                    "cantidad": cantidad_raw,
                    "observaciones": observaciones,
                }
            )

    db.close()
    return render_template(
        "fabricacion_form.html",
        vehiculos=vehiculos,
        almacenes_destino=almacenes_destino,
        cabecera={}
    )


@app.route("/api/fabricacion/preview", methods=["POST"])
@login_required
def api_fabricacion_preview():
    """API para obtener preview de materiales necesarios para una orden de fabricación"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        vehiculo_id = request.json.get("vehiculo_id")
        cantidad_raw = request.json.get("cantidad", "0")
        
        if not vehiculo_id:
            return jsonify({"error": "Vehículo no especificado"}), 400
        
        cantidad = to_int_quantity(cantidad_raw)
        if cantidad is None or cantidad <= 0:
            return jsonify({"error": "Cantidad inválida"}), 400
        
        # Obtener BOM del vehículo
        cursor.execute(
            """
            SELECT articulo_id, cantidad_por_unidad
            FROM fabricacion_bom
            WHERE vehiculo_id = %s
            """,
            (vehiculo_id,)
        )
        bom_rows = cursor.fetchall()
        
        if not bom_rows:
            return jsonify({"error": "El vehículo no tiene BOM definido"}), 400
        
        # Calcular cantidades requeridas
        required = {}
        for row in bom_rows:
            qpu = to_int_quantity(row['cantidad_por_unidad'])
            if qpu is None or qpu <= 0:
                return jsonify({"error": "BOM contiene cantidades inválidas"}), 400
            req = qpu * cantidad
            required[row['articulo_id']] = req
        
        # Mapear materiales con almacenes de origen disponibles
        materials = []
        for articulo_id, qty_required in required.items():
            cursor.execute("SELECT nombre FROM articulos WHERE id=%s", (articulo_id,))
            art = cursor.fetchone()
            articulo_nombre = art['nombre'] if art else f"ID {articulo_id}"
            
            # Obtener stocks disponibles de este artículo
            cursor.execute(
                """
                SELECT e.almacen_id, e.cantidad, a.ubicacion
                FROM existencias e
                JOIN almacenes a ON a.id = e.almacen_id
                WHERE e.articulo_id = %s
                  AND a.tipo_almacen <> 'Vehiculos'
                  AND e.cantidad > 0
                ORDER BY e.cantidad DESC
                """,
                (articulo_id,)
            )
            stocks = cursor.fetchall()
            
            # Distribuir cantidad requerida entre almacenes
            remaining = qty_required
            sources = []
            for stock in stocks:
                if remaining <= 0:
                    break
                available = to_int_quantity(stock['cantidad']) or 0
                if available <= 0:
                    continue
                take = available if available <= remaining else remaining
                if take <= 0:
                    continue
                sources.append({
                    "almacen": stock['ubicacion'],
                    "cantidad": take
                })
                remaining -= take
            
            materials.append({
                "articulo_id": articulo_id,
                "articulo": articulo_nombre,
                "cantidad_total": qty_required,
                "almacenes": sources,
                "pendiente": remaining
            })
        
        db.close()
        return jsonify({"success": True, "materiales": materials})
    
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 500


@app.route("/fabricacion/<int:id>")
@login_required
def fabricacion_detalle(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT fo.id, fo.fecha, fo.cantidad, fo.estado, fo.observaciones,
               v.id AS vehiculo_id, v.modelo AS vehiculo,
               a.id AS almacen_destino_id, a.ubicacion AS almacen_destino
        FROM fabricacion_ordenes fo
        JOIN vehiculos v ON fo.vehiculo_id = v.id
        JOIN almacenes a ON fo.almacen_destino_id = a.id
        WHERE fo.id = %s
        """,
        (id,)
    )
    orden = cursor.fetchone()
    if not orden:
        db.close()
        flash("Orden de fabricación no encontrada", "error")
        return redirect("/fabricacion")

    cursor.execute(
        """
        SELECT fc.articulo_id, ar.nombre AS articulo,
               fc.almacen_origen_id, ao.ubicacion AS almacen_origen,
               fc.cantidad
        FROM fabricacion_consumos fc
        JOIN articulos ar ON ar.id = fc.articulo_id
        JOIN almacenes ao ON ao.id = fc.almacen_origen_id
        WHERE fc.orden_id = %s
        ORDER BY ar.nombre, ao.ubicacion
        """,
        (id,)
    )
    consumos = cursor.fetchall()

    db.close()
    return render_template("fabricacion_detalle.html", orden=orden, consumos=consumos)


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)

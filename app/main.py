from flask import Flask, render_template, request, redirect, session, g, url_for, flash
from app.db import get_db
import os
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates")
)
# Use an environment variable in production
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ---------------- INDEX ----------------
@app.route("/")
def index():
    return render_template("index.html")

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
            JOIN empleados e ON v.empleado_id = e.id
            WHERE v.id LIKE %s OR e.nombre LIKE %s OR v.fecha LIKE %s
        """, (like, like, like))
        total = cursor.fetchone()['cnt']
        cursor.execute("""
            SELECT v.id, v.fecha, v.total, e.nombre AS empleado
            FROM ventas v
            JOIN empleados e ON v.empleado_id = e.id
            WHERE v.id LIKE %s OR e.nombre LIKE %s OR v.fecha LIKE %s
            LIMIT %s OFFSET %s
        """, (like, like, like, per_page, offset))
    else:
        cursor.execute("SELECT COUNT(*) AS cnt FROM ventas")
        total = cursor.fetchone()['cnt']
        cursor.execute("""
            SELECT v.id, v.fecha, v.total, e.nombre AS empleado
            FROM ventas v
            JOIN empleados e ON v.empleado_id = e.id
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
    cursor.execute("SELECT * FROM empleados")
    empleados = cursor.fetchall()

    if request.method == "POST":
        cursor2 = db.cursor()
        cursor2.execute("""
            INSERT INTO ventas VALUES (NULL,%s,%s,%s)
        """, (
            request.form["fecha"],
            request.form["total"],
            request.form["empleado"]
        ))
        db.commit()
        db.close()
        return redirect("/ventas")

    return render_template("ventas_form.html", empleados=empleados)

@app.route("/ventas/editar/<int:id>", methods=["GET", "POST"])
@login_required
@role_required(action='edit')
def editar_venta(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados")
    empleados = cursor.fetchall()

    if request.method == "POST":
        cursor2 = db.cursor()
        cursor2.execute("""
            UPDATE ventas SET fecha=%s, total=%s, empleado_id=%s
            WHERE id=%s
        """, (
            request.form["fecha"],
            request.form["total"],
            request.form["empleado"],
            id
        ))
        db.commit()
        db.close()
        return redirect("/ventas")

    cursor.execute("SELECT * FROM ventas WHERE id=%s", (id,))
    venta = cursor.fetchone()
    db.close()
    return render_template("ventas_form.html", venta=venta, empleados=empleados)

@app.route("/ventas/eliminar/<int:id>")
@login_required
@role_required(action='delete')
def eliminar_venta(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM ventas WHERE id=%s", (id,))
    db.commit()
    db.close()
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


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, redirect
from app.db import get_db
import os

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates")
)

# ---------------- INDEX ----------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------- CLIENTES ----------------
@app.route("/clientes")
def clientes():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clientes")
    data = cursor.fetchall()
    db.close()
    return render_template("clientes.html", clientes=data)

@app.route("/clientes/nuevo", methods=["GET", "POST"])
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
def eliminar_cliente(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM clientes WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/clientes")

# ---------------- EMPLEADOS ----------------
@app.route("/empleados")
def empleados():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM empleados")
    data = cursor.fetchall()
    db.close()
    return render_template("empleados.html", empleados=data)

@app.route("/empleados/nuevo", methods=["GET", "POST"])
def nuevo_empleado():
    if request.method == "POST":
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO empleados VALUES (NULL,%s,%s,%s,%s,%s,%s)
        """, (
            request.form["nombre"],
            request.form["dni"],
            request.form["correo"],
            request.form["direccion"],
            request.form["departamento"],
            request.form["salario"]
        ))
        db.commit()
        db.close()
        return redirect("/empleados")
    return render_template("empleados_form.html")

@app.route("/empleados/editar/<int:id>", methods=["GET", "POST"])
def editar_empleado(id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if request.method == "POST":
        cursor.execute("""
            UPDATE empleados SET nombre=%s, dni=%s, correo=%s, direccion=%s, departamento=%s, salario=%s
            WHERE id=%s
        """, (
            request.form["nombre"],
            request.form["dni"],
            request.form["correo"],
            request.form["direccion"],
            request.form["departamento"],
            request.form["salario"],
            id
        ))
        db.commit()
        db.close()
        return redirect("/empleados")
    cursor.execute("SELECT * FROM empleados WHERE id=%s", (id,))
    empleado = cursor.fetchone()
    db.close()
    return render_template("empleados_form.html", empleado=empleado)

@app.route("/empleados/eliminar/<int:id>")
def eliminar_empleado(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM empleados WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/empleados")

# ---------------- VEHICULOS ----------------
@app.route("/vehiculos")
def vehiculos():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM vehiculos")
    data = cursor.fetchall()
    db.close()
    return render_template("vehiculos.html", vehiculos=data)

@app.route("/vehiculos/nuevo", methods=["GET", "POST"])
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
def eliminar_vehiculo(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM vehiculos WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/vehiculos")

# ---------------- VENTAS ----------------
@app.route("/ventas")
def ventas():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT v.id, v.fecha, v.total, e.nombre AS empleado
        FROM ventas v
        JOIN empleados e ON v.empleado_id = e.id
    """)
    data = cursor.fetchall()
    db.close()
    return render_template("ventas.html", ventas=data)

@app.route("/ventas/nuevo", methods=["GET", "POST"])
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
def eliminar_venta(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM ventas WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/ventas")

# ---------------- ALMACENES ----------------
@app.route("/almacenes")
def almacenes():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM almacenes")
    data = cursor.fetchall()
    db.close()
    return render_template("almacenes.html", almacenes=data)

@app.route("/almacenes/nuevo", methods=["GET", "POST"])
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
def eliminar_almacen(id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM almacenes WHERE id=%s", (id,))
    db.commit()
    db.close()
    return redirect("/almacenes")

@app.route("/proveedores")
def proveedores():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM proveedores")
    data = cursor.fetchall()
    db.close()
    return render_template("proveedores.html", proveedores=data)

@app.route("/proveedores/nuevo", methods=["GET", "POST"])
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



# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)

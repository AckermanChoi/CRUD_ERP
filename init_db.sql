DROP DATABASE IF EXISTS erp_toyota;
CREATE DATABASE erp_toyota;
USE erp_toyota;

-- 1. TABLA EMPLEADOS (Con campos de login)
CREATE TABLE empleados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    dni VARCHAR(20) NOT NULL UNIQUE,
    correo VARCHAR(100) NOT NULL UNIQUE, 
    direccion VARCHAR(200),
    departamento VARCHAR(50),
    salario DECIMAL(10,2),
    contrasena VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'empleado'
);

-- 2. TABLA CLIENTES
CREATE TABLE clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    dni VARCHAR(20) UNIQUE,
    correo VARCHAR(100),
    telefono VARCHAR(20),
    pais VARCHAR(50),
    tipo VARCHAR(50)
);

-- 3. TABLA PROVEEDORES
CREATE TABLE proveedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    dni VARCHAR(20) UNIQUE,
    correo VARCHAR(100),
    contacto VARCHAR(100),
    tipo_suministro VARCHAR(100)
);

-- 4. TABLA VEHICULOS
CREATE TABLE vehiculos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    modelo VARCHAR(100),
    tipo VARCHAR(50),
    anio INT,
    color VARCHAR(50),
    precio_venta DECIMAL(10,2),
    costo_fabricante DECIMAL(10,2)
);

-- 5. TABLA ALMACENES
CREATE TABLE almacenes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ubicacion VARCHAR(100),
    correo VARCHAR(100),
    tipo_almacen VARCHAR(50),
    capacidad INT,
    disponible INT
);

-- 6. TABLA VENTAS
CREATE TABLE ventas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha DATE,
    total DECIMAL(10,2),
    cliente_id INT,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
);

-- 7. TABLA ARTICULOS
CREATE TABLE articulos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL
);

-- 8. TABLA COMPRAS (CABECERA)
CREATE TABLE compras (
    id INT AUTO_INCREMENT PRIMARY KEY,
    numero_factura VARCHAR(50) NOT NULL,
    proveedor_id INT NOT NULL,
    fecha DATE NOT NULL,
    almacen_id INT NOT NULL,
    total DECIMAL(12,2) NOT NULL DEFAULT 0,
    FOREIGN KEY (proveedor_id) REFERENCES proveedores(id),
    FOREIGN KEY (almacen_id) REFERENCES almacenes(id)
);

-- 9. TABLA COMPRAS_LINEAS (DETALLE)
CREATE TABLE compras_lineas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    compra_id INT NOT NULL,
    linea_num INT NOT NULL,
    articulo_id INT NOT NULL,
    cantidad DECIMAL(12,2) NOT NULL,
    precio_compra DECIMAL(12,2) NOT NULL,
    iva_pct DECIMAL(5,2) NOT NULL DEFAULT 0,
    descuento_pct DECIMAL(5,2) NOT NULL DEFAULT 0,
    total_linea DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (compra_id) REFERENCES compras(id) ON DELETE CASCADE,
    FOREIGN KEY (articulo_id) REFERENCES articulos(id)
);

-- 10. TABLA EXISTENCIAS (POR ALMACEN Y ARTICULO)
CREATE TABLE existencias (
    almacen_id INT NOT NULL,
    articulo_id INT NOT NULL,
    cantidad DECIMAL(12,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (almacen_id, articulo_id),
    FOREIGN KEY (almacen_id) REFERENCES almacenes(id),
    FOREIGN KEY (articulo_id) REFERENCES articulos(id)
);

-- DATOS INICIALES
-- Passwords de ejemplo: admin123 / super123 / emple123
INSERT INTO empleados (nombre, dni, correo, direccion, departamento, salario, contrasena, role) VALUES
('Admin General', '00000000A', 'admin@example.com', 'Calle Admin 1', 'Administracion', 3500.00,
 'scrypt:32768:8:1$duHX46AVTzMvGC3N$1ff4d7c0aa94ba17e823c734ce9f1093771b298927a4f4e351f61b98d92a96e635ec84240f2584b832d839ce5bac8e323877d08492a38cb6f745e6cf8a8ee9a9',
 'jefe'),
('Supervisor Compras', '00000001B', 'supervisor@example.com', 'Calle Supervisor 2', 'Compras', 2400.00,
 'scrypt:32768:8:1$7XxC0d4oBCt3dLEt$829bf4d79b885e5f6df006273f72ef414ce14ca9baa051716735ea5e93f0f6ae0e9991589cfe357abd0c5efaa70318aa24c9167e26d6c7f6f07dc2a99b83e132',
 'supervisor'),
('Empleado Ventas', '00000002C', 'empleado@example.com', 'Calle Empleado 3', 'Ventas', 1800.00,
 'scrypt:32768:8:1$6uwj9OT40CO5hrjX$b1c6f4448e8bb564240e496c5831b778ad510e9c135e2f05949e836bf77301b5243f78ddb739b31c0c380babef675a76629b97d80eb0c73ed9a486cd79254eb0',
 'empleado');

INSERT INTO clientes (nombre, dni, correo, telefono, pais, tipo) VALUES
('Ana Lopez', '12345678A', 'ana@example.com', '600111222', 'Espana', 'Empresa'),
('Carlos Ruiz', '87654321B', 'carlos@example.com', '600333444', 'Espana', 'Particular');

INSERT INTO proveedores (nombre, dni, correo, contacto, tipo_suministro) VALUES
('Proveedor Norte', 'B12345678', 'norte@example.com', '600111999', 'Electronica'),
('Suministros Centro', 'B87654321', 'centro@example.com', '600222888', 'Mecanica');

INSERT INTO vehiculos (modelo, tipo, anio, color, precio_venta, costo_fabricante) VALUES
('Corolla', 'Sedan', 2024, 'Blanco', 22000.00, 16000.00),
('Hilux', 'Pickup', 2023, 'Gris', 32000.00, 24000.00);

INSERT INTO almacenes (ubicacion, correo, tipo_almacen, capacidad, disponible) VALUES
('Madrid Central', 'almacen-madrid@example.com', 'Principal', 1000, 600),
('Barcelona', 'almacen-bcn@example.com', 'Tienda', 500, 350);

INSERT INTO articulos (codigo, nombre) VALUES
('A-100', 'Filtro aceite'),
('A-200', 'Pastillas freno'),
('A-300', 'Bateria 12V');

INSERT INTO compras (numero_factura, proveedor_id, fecha, almacen_id, total) VALUES
('FAC-1001', 1, '2026-02-01', 1, 532.40),
('FAC-1002', 2, '2026-02-05', 2, 343.83);

INSERT INTO compras_lineas (compra_id, linea_num, articulo_id, cantidad, precio_compra, iva_pct, descuento_pct, total_linea) VALUES
(1, 1, 1, 10, 12.50, 21.00, 0.00, 151.25),
(1, 2, 2, 20, 10.00, 21.00, 5.00, 229.90),
(1, 3, 3, 5, 25.00, 21.00, 0.00, 151.25),
(2, 1, 1, 6, 12.50, 10.00, 0.00, 82.50),
(2, 2, 2, 10, 10.00, 10.00, 0.00, 110.00),
(2, 3, 3, 5, 29.00, 10.00, 5.00, 151.33);

INSERT INTO existencias (almacen_id, articulo_id, cantidad) VALUES
(1, 1, 10),
(1, 2, 20),
(1, 3, 5),
(2, 1, 6),
(2, 2, 10),
(2, 3, 5);


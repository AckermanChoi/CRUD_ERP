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
    fecha DATE NOT NULL,
    total DECIMAL(12,2) NOT NULL DEFAULT 0,
    cliente_id INT NOT NULL,
    almacen_id INT NOT NULL,
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
    FOREIGN KEY (almacen_id) REFERENCES almacenes(id)
);

-- 7. TABLA ARTICULOS
CREATE TABLE articulos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(120) NOT NULL UNIQUE
);

-- 8. TABLA COMPRAS (CABECERA)
CREATE TABLE compras (
    id INT AUTO_INCREMENT PRIMARY KEY,
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

-- 10. TABLA VENTAS_LINEAS (DETALLE)
CREATE TABLE ventas_lineas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    venta_id INT NOT NULL,
    linea_num INT NOT NULL,
    articulo_id INT NOT NULL,
    cantidad DECIMAL(12,2) NOT NULL,
    precio_venta DECIMAL(12,2) NOT NULL,
    iva_pct DECIMAL(5,2) NOT NULL DEFAULT 0,
    descuento_pct DECIMAL(5,2) NOT NULL DEFAULT 0,
    total_linea DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE,
    FOREIGN KEY (articulo_id) REFERENCES articulos(id)
);

-- 11. TABLA EXISTENCIAS (POR ALMACEN Y ARTICULO)
CREATE TABLE existencias (
    almacen_id INT NOT NULL,
    articulo_id INT NOT NULL,
    cantidad DECIMAL(12,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (almacen_id, articulo_id),
    FOREIGN KEY (almacen_id) REFERENCES almacenes(id),
    FOREIGN KEY (articulo_id) REFERENCES articulos(id)
);

-- 12. TABLA FABRICACION_BOM (LISTA DE MATERIALES POR VEHICULO)
CREATE TABLE fabricacion_bom (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehiculo_id INT NOT NULL,
    articulo_id INT NOT NULL,
    cantidad_por_unidad DECIMAL(12,2) NOT NULL,
    UNIQUE KEY uq_bom_vehiculo_articulo (vehiculo_id, articulo_id),
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
    FOREIGN KEY (articulo_id) REFERENCES articulos(id)
);

-- 13. TABLA FABRICACION_ORDENES
CREATE TABLE fabricacion_ordenes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    vehiculo_id INT NOT NULL,
    cantidad DECIMAL(12,2) NOT NULL,
    almacen_destino_id INT NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'borrador', -- borrador | confirmada | cancelada
    observaciones VARCHAR(255),
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id),
    FOREIGN KEY (almacen_destino_id) REFERENCES almacenes(id)
);

-- 14. TABLA FABRICACION_CONSUMOS (DETALLE DE QUE ALMACEN SALE CADA COMPONENTE)
CREATE TABLE fabricacion_consumos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    orden_id INT NOT NULL,
    articulo_id INT NOT NULL,
    almacen_origen_id INT NOT NULL,
    cantidad DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (orden_id) REFERENCES fabricacion_ordenes(id) ON DELETE CASCADE,
    FOREIGN KEY (articulo_id) REFERENCES articulos(id),
    FOREIGN KEY (almacen_origen_id) REFERENCES almacenes(id)
);

-- 15. TABLA STOCK_VEHICULOS (COCHES TERMINADOS POR ALMACEN)
CREATE TABLE stock_vehiculos (
    almacen_id INT NOT NULL,
    vehiculo_id INT NOT NULL,
    cantidad DECIMAL(12,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (almacen_id, vehiculo_id),
    FOREIGN KEY (almacen_id) REFERENCES almacenes(id),
    FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id)
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

-- Empleados adicionales (sin tocar los 3 masters)
INSERT INTO empleados (nombre, dni, correo, direccion, departamento, salario, contrasena, role) VALUES
('Laura Martin', '11111111D', 'laura.martin@toyota.local', 'Av. Europa 21, Madrid', 'Ventas', 2100.00,
 'scrypt:32768:8:1$6uwj9OT40CO5hrjX$b1c6f4448e8bb564240e496c5831b778ad510e9c135e2f05949e836bf77301b5243f78ddb739b31c0c380babef675a76629b97d80eb0c73ed9a486cd79254eb0',
 'empleado'),
('Javier Torres', '22222222E', 'javier.torres@toyota.local', 'Calle Toledo 58, Madrid', 'Almacen', 2050.00,
 'scrypt:32768:8:1$6uwj9OT40CO5hrjX$b1c6f4448e8bb564240e496c5831b778ad510e9c135e2f05949e836bf77301b5243f78ddb739b31c0c380babef675a76629b97d80eb0c73ed9a486cd79254eb0',
 'empleado'),
('Marta Prieto', '33333333F', 'marta.prieto@toyota.local', 'Passeig de Gracia 77, Barcelona', 'Compras', 2450.00,
 'scrypt:32768:8:1$7XxC0d4oBCt3dLEt$829bf4d79b885e5f6df006273f72ef414ce14ca9baa051716735ea5e93f0f6ae0e9991589cfe357abd0c5efaa70318aa24c9167e26d6c7f6f07dc2a99b83e132',
 'supervisor'),
('Diego Navarro', '44444444G', 'diego.navarro@toyota.local', 'Calle Gran Via 14, Valencia', 'Técnico', 2300.00,
 'scrypt:32768:8:1$6uwj9OT40CO5hrjX$b1c6f4448e8bb564240e496c5831b778ad510e9c135e2f05949e836bf77301b5243f78ddb739b31c0c380babef675a76629b97d80eb0c73ed9a486cd79254eb0',
 'empleado'),
('Sonia Gil', '55555555H', 'sonia.gil@toyota.local', 'Av. de la Constitucion 5, Sevilla', 'Ventas', 2200.00,
 'scrypt:32768:8:1$6uwj9OT40CO5hrjX$b1c6f4448e8bb564240e496c5831b778ad510e9c135e2f05949e836bf77301b5243f78ddb739b31c0c380babef675a76629b97d80eb0c73ed9a486cd79254eb0',
 'empleado');

INSERT INTO clientes (nombre, dni, correo, telefono, pais, tipo) VALUES
('Ana Lopez', '12345678A', 'ana@example.com', '600111222', 'Espana', 'empresa'),
('Carlos Ruiz', '87654321B', 'carlos@example.com', '600333444', 'Espana', 'Particular'),
('Lucia Fernandez', '11223344A', 'lucia.fernandez@gmail.com', '611223344', 'Espana', 'Particular'),
('Miguel Sanchez', '22334455B', 'miguel.sanchez@gmail.com', '622334455', 'Espana', 'Particular'),
('TransLog Iberia SL', 'B66554433', 'compras@translogiberia.es', '913556677', 'Espana', 'empresa'),
('Construcciones Rivera SA', 'A44332211', 'flota@rivera-sa.es', '914778899', 'Espana', 'empresa'),
('Marina Costa', '33445566C', 'marina.costa@gmail.com', '633445566', 'Espana', 'Particular'),
('Victor Olmedo', '44556677D', 'victor.olmedo@gmail.com', '644556677', 'Espana', 'Particular'),
('ElectroSur Mantenimiento', 'B90807060', 'operaciones@electrosur.com', '955334455', 'Espana', 'empresa'),
('Patricia Herrero', '55667788E', 'patri.herrero@gmail.com', '655667788', 'Espana', 'Particular');

INSERT INTO proveedores (nombre, dni, correo, contacto, tipo_suministro) VALUES
('Proveedor Norte', 'B12345678', 'norte@example.com', '600111999', 'Electronica'),
('Suministros Centro', 'B87654321', 'centro@example.com', '600222888', 'Mecanica'),
('Neumaticos Ibericos', 'B11224455', 'ventas@neumaticosibericos.com', '960112233', 'Neumaticos'),
('LubriMax Europa', 'B22335566', 'pedidos@lubrimax.eu', '961223344', 'Lubricantes'),
('Baterias Delta', 'B33446677', 'comercial@bateriasdelta.com', '962334455', 'Electricidad'),
('Cristales AutoLine', 'B44557788', 'atencion@autolineglass.es', '963445566', 'Carroceria');

INSERT INTO vehiculos (modelo, tipo, anio, color, precio_venta, costo_fabricante) VALUES
('Corolla', 'Sedan', 2024, 'Blanco', 22000.00, 16000.00),
('Hilux', 'Pickup', 2023, 'Gris', 32000.00, 24000.00),
('Yaris', 'Urbano', 2024, 'Rojo', 17800.00, 13200.00),
('Yaris Cross', 'SUV', 2025, 'Azul', 25900.00, 19850.00),
('RAV4 Hybrid', 'SUV', 2024, 'Negro', 38900.00, 29900.00),
('C-HR', 'Crossover', 2024, 'Gris Titanio', 31200.00, 24100.00),
('Corolla Touring Sports', 'Familiar', 2025, 'Plata', 29400.00, 22400.00),
('Camry Hybrid', 'Sedan', 2024, 'Negro', 41900.00, 32200.00),
('Land Cruiser', 'SUV', 2025, 'Verde Oliva', 74500.00, 58800.00),
('Proace City', 'Furgoneta', 2024, 'Blanco', 24800.00, 18900.00),
('Proace Verso', 'Monovolumen', 2024, 'Gris', 36100.00, 27900.00),
('bZ4X', 'Electrico', 2025, 'Blanco Pearl', 46800.00, 36600.00);

INSERT INTO almacenes (ubicacion, correo, tipo_almacen, capacidad, disponible) VALUES
('Madrid Central', 'almacen-madrid@example.com', 'Principal', 1000, 600),
('Barcelona', 'almacen-bcn@example.com', 'Tienda', 500, 350),
('Valencia Logistica', 'almacen-valencia@example.com', 'Distribucion', 800, 420),
('Sevilla Recambios', 'almacen-sevilla@example.com', 'Recambios', 700, 390),
('Madrid Vehiculos Terminados', 'vehiculos-madrid@example.com', 'Vehiculos', 300, 300),
('Barcelona Vehiculos Terminados', 'vehiculos-bcn@example.com', 'Vehiculos', 220, 220);

INSERT INTO articulos (nombre) VALUES
('Filtro aceite'),
('Pastillas freno'),
('Bateria 12V'),
('Aceite 5W30 5L'),
('Neumatico 205/55 R16'),
('Disco de freno delantero'),
('Kit embrague'),
('Lampara LED H7'),
('Escobilla limpiaparabrisas'),
('Liquido refrigerante 1L'),
('Alternador 12V'),
('Amortiguador delantero'),
('Tornillo M12'),
('Llanta 17" Aleacion'),
('Motor 2.0L Hibrido'),
('Caja cambios automatica'),
('Chasis compacto'),
('Asiento delantero');

INSERT INTO compras (proveedor_id, fecha, almacen_id, total) VALUES
(1, '2026-02-01', 1, 532.40),
(2, '2026-02-05', 2, 343.83),
(1, '2026-02-10', 1, 173.64),
(2, '2026-02-11', 2, 237.82),
(3, '2026-02-13', 1, 1254.90),
(4, '2026-02-16', 3, 986.40),
(5, '2026-02-18', 4, 1422.75),
(6, '2026-02-21', 2, 768.60),
(3, '2026-02-24', 3, 1120.35),
(4, '2026-02-26', 1, 654.20);

INSERT INTO compras_lineas (compra_id, linea_num, articulo_id, cantidad, precio_compra, iva_pct, descuento_pct, total_linea) VALUES
(1, 1, 1, 10, 12.50, 21.00, 0.00, 151.25),
(1, 2, 2, 20, 10.00, 21.00, 5.00, 229.90),
(1, 3, 3, 5, 25.00, 21.00, 0.00, 151.25),
(2, 1, 1, 6, 12.50, 10.00, 0.00, 82.50),
(2, 2, 2, 10, 10.00, 10.00, 0.00, 110.00),
(2, 3, 3, 5, 29.00, 10.00, 5.00, 151.33),
(3, 1, 1, 8, 12.00, 21.00, 0.00, 116.16),
(3, 2, 2, 5, 9.50, 21.00, 0.00, 57.48),
(4, 1, 3, 7, 26.00, 10.00, 0.00, 200.20),
(4, 2, 2, 4, 9.00, 10.00, 5.00, 37.62),
(5, 1, 5, 40, 20.00, 21.00, 0.00, 968.00),
(5, 2, 10, 15, 15.80, 21.00, 0.00, 286.90),
(6, 1, 4, 60, 9.00, 10.00, 0.00, 594.00),
(6, 2, 8, 20, 14.20, 10.00, 5.00, 296.78),
(7, 1, 6, 24, 38.00, 21.00, 0.00, 1103.52),
(7, 2, 11, 12, 21.90, 21.00, 0.00, 317.99),
(8, 1, 7, 10, 45.00, 21.00, 5.00, 517.28),
(8, 2, 2, 18, 10.50, 21.00, 0.00, 228.69),
(9, 1, 5, 30, 19.50, 21.00, 0.00, 707.85),
(9, 2, 9, 25, 6.20, 21.00, 0.00, 187.55),
(10, 1, 4, 35, 8.80, 10.00, 0.00, 338.80),
(10, 2, 1, 20, 11.20, 10.00, 0.00, 246.40);

INSERT INTO ventas (fecha, total, cliente_id, almacen_id) VALUES
('2026-02-08', 207.29, 1, 1),
('2026-02-09', 176.00, 2, 2),
('2026-02-12', 342.15, 3, 1),
('2026-02-14', 289.40, 4, 2),
('2026-02-15', 1248.60, 5, 3),
('2026-02-17', 418.35, 6, 1),
('2026-02-19', 96.80, 7, 4),
('2026-02-22', 675.25, 8, 2),
('2026-02-23', 520.10, 9, 3),
('2026-02-25', 233.90, 10, 1),
('2026-02-27', 1540.00, 5, 1),
('2026-02-28', 310.75, 2, 2);

INSERT INTO ventas_lineas (venta_id, linea_num, articulo_id, cantidad, precio_venta, iva_pct, descuento_pct, total_linea) VALUES
(1, 1, 1, 6, 20.00, 21.00, 0.00, 145.20),
(1, 2, 2, 3, 18.00, 21.00, 5.00, 62.09),
(2, 1, 3, 4, 40.00, 10.00, 0.00, 176.00),
(3, 1, 4, 8, 14.00, 21.00, 0.00, 135.52),
(3, 2, 9, 20, 8.50, 21.00, 0.00, 205.70),
(4, 1, 2, 10, 19.00, 21.00, 0.00, 229.90),
(4, 2, 10, 2, 24.50, 21.00, 0.00, 59.29),
(5, 1, 6, 6, 95.00, 21.00, 0.00, 689.70),
(5, 2, 7, 4, 115.00, 21.00, 0.00, 556.60),
(6, 1, 5, 12, 29.00, 21.00, 0.00, 421.08),
(7, 1, 11, 2, 40.00, 21.00, 0.00, 96.80),
(8, 1, 8, 5, 120.00, 10.00, 0.00, 660.00),
(9, 1, 6, 2, 215.00, 21.00, 0.00, 520.30),
(10, 1, 4, 10, 17.50, 21.00, 0.00, 211.75),
(10, 2, 1, 1, 18.31, 21.00, 0.00, 22.15),
(11, 1, 6, 8, 132.50, 21.00, 3.00, 1234.12),
(11, 2, 5, 10, 25.00, 21.00, 0.00, 302.50),
(12, 1, 2, 6, 17.50, 21.00, 0.00, 127.05),
(12, 2, 9, 12, 12.65, 21.00, 0.00, 183.70);

INSERT INTO existencias (almacen_id, articulo_id, cantidad) VALUES
(1, 1, 34),
(1, 2, 52),
(1, 3, 18),
(1, 4, 40),
(1, 5, 65),
(1, 6, 22),
(1, 7, 14),
(1, 8, 11),
(1, 9, 38),
(1, 10, 49),
(1, 11, 20),
(1, 12, 18),
(1, 13, 500),
(1, 14, 40),
(1, 15, 8),
(1, 16, 7),
(1, 17, 10),
(1, 18, 28),
(2, 1, 21),
(2, 2, 36),
(2, 3, 14),
(2, 4, 26),
(2, 5, 44),
(2, 6, 10),
(2, 7, 8),
(2, 8, 6),
(2, 9, 22),
(2, 10, 31),
(2, 11, 15),
(2, 12, 11),
(2, 13, 260),
(2, 14, 18),
(2, 15, 3),
(2, 16, 2),
(2, 17, 4),
(2, 18, 14),
(3, 1, 18),
(3, 2, 29),
(3, 3, 10),
(3, 4, 24),
(3, 5, 33),
(3, 6, 12),
(3, 7, 9),
(3, 8, 7),
(3, 9, 20),
(3, 10, 28),
(3, 11, 11),
(3, 12, 9),
(3, 13, 210),
(3, 14, 22),
(3, 15, 6),
(3, 16, 6),
(3, 17, 8),
(3, 18, 16),
(4, 1, 15),
(4, 2, 20),
(4, 3, 9),
(4, 4, 17),
(4, 5, 28),
(4, 6, 8),
(4, 7, 6),
(4, 8, 5),
(4, 9, 13),
(4, 10, 19),
(4, 11, 9),
(4, 12, 7),
(4, 13, 140),
(4, 14, 12),
(4, 15, 2),
(4, 16, 2),
(4, 17, 3),
(4, 18, 10);

-- BOM (receta) por modelo de vehículo
-- Corolla (vehiculo_id = 1)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(1, 13, 50), -- Tornillo M12
(1, 14, 4),  -- Llantas
(1, 15, 1),  -- Motor
(1, 16, 1),  -- Caja cambios
(1, 17, 1),  -- Chasis
(1, 18, 2);  -- Asientos delanteros

-- Hilux (vehiculo_id = 2)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(2, 13, 70),
(2, 14, 4),
(2, 15, 1),
(2, 16, 1),
(2, 17, 1),
(2, 18, 2);

-- Yaris (vehiculo_id = 3)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(3, 13, 45),
(3, 14, 4),
(3, 15, 1),
(3, 16, 1),
(3, 17, 1),
(3, 18, 2);

-- Yaris Cross (vehiculo_id = 4)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(4, 13, 55),
(4, 14, 4),
(4, 15, 1),
(4, 16, 1),
(4, 17, 1),
(4, 18, 2);

-- RAV4 Hybrid (vehiculo_id = 5)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(5, 13, 65),
(5, 14, 4),
(5, 15, 1),
(5, 16, 1),
(5, 17, 1),
(5, 18, 2);

-- C-HR (vehiculo_id = 6)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(6, 13, 58),
(6, 14, 4),
(6, 15, 1),
(6, 16, 1),
(6, 17, 1),
(6, 18, 2);

-- Corolla Touring Sports (vehiculo_id = 7)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(7, 13, 54),
(7, 14, 4),
(7, 15, 1),
(7, 16, 1),
(7, 17, 1),
(7, 18, 2);

-- Camry Hybrid (vehiculo_id = 8)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(8, 13, 62),
(8, 14, 4),
(8, 15, 1),
(8, 16, 1),
(8, 17, 1),
(8, 18, 2);

-- Land Cruiser (vehiculo_id = 9)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(9, 13, 90),
(9, 14, 4),
(9, 15, 1),
(9, 16, 1),
(9, 17, 1),
(9, 18, 2);

-- Proace City (vehiculo_id = 10)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(10, 13, 68),
(10, 14, 4),
(10, 15, 1),
(10, 16, 1),
(10, 17, 1),
(10, 18, 2);

-- Proace Verso (vehiculo_id = 11)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(11, 13, 74),
(11, 14, 4),
(11, 15, 1),
(11, 16, 1),
(11, 17, 1),
(11, 18, 2);

-- bZ4X (vehiculo_id = 12)
INSERT INTO fabricacion_bom (vehiculo_id, articulo_id, cantidad_por_unidad) VALUES
(12, 13, 52),
(12, 14, 4),
(12, 15, 1),
(12, 16, 1),
(12, 17, 1),
(12, 18, 2);

-- Orden de fabricación de ejemplo: 1 Corolla terminado en almacén exclusivo de vehículos (id 5)
INSERT INTO fabricacion_ordenes (fecha, vehiculo_id, cantidad, almacen_destino_id, estado, observaciones) VALUES
('2026-03-01 10:30:00', 1, 1, 5, 'confirmada', 'Orden piloto de ensamblaje usando componentes de múltiples almacenes');

-- Consumos reales de la orden 1 desde diferentes almacenes
INSERT INTO fabricacion_consumos (orden_id, articulo_id, almacen_origen_id, cantidad) VALUES
(1, 13, 1, 30), -- 30 tornillos desde Madrid Central
(1, 13, 2, 20), -- 20 tornillos desde Barcelona
(1, 14, 1, 4),  -- 4 llantas desde Madrid Central
(1, 15, 3, 1),  -- 1 motor desde Valencia Logistica
(1, 16, 3, 1),  -- 1 caja cambios desde Valencia Logistica
(1, 17, 4, 1),  -- 1 chasis desde Sevilla Recambios
(1, 18, 2, 2);  -- 2 asientos desde Barcelona

-- Stock de vehículos terminados en almacenes exclusivos
INSERT INTO stock_vehiculos (almacen_id, vehiculo_id, cantidad) VALUES
(5, 1, 1),  -- 1 Corolla fabricado
(5, 2, 2),
(5, 4, 1),
(6, 1, 3),
(6, 2, 1),
(6, 11, 1);


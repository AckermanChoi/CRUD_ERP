CREATE DATABASE IF NOT EXISTS erp_toyota;
USE erp_toyota;

CREATE TABLE IF NOT EXISTS clientes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    dni VARCHAR(20),
    correo VARCHAR(100),
    telefono VARCHAR(20),
    pais VARCHAR(50),
    tipo VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS empleados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    dni VARCHAR(20),
    correo VARCHAR(100),
    direccion VARCHAR(200),
    departamento VARCHAR(50),
    salario DECIMAL(10,2)
);

CREATE TABLE IF NOT EXISTS proveedores (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    dni VARCHAR(20),
    correo VARCHAR(100),
    contacto VARCHAR(100),
    tipo_suministro VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS vehiculos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    modelo VARCHAR(100),
    tipo VARCHAR(50),
    anio INT,
    color VARCHAR(50),
    precio_venta DECIMAL(10,2),
    costo_fabricante DECIMAL(10,2)
);

CREATE TABLE IF NOT EXISTS almacenes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ubicacion VARCHAR(100),
    correo VARCHAR(100),
    tipo_almacen VARCHAR(50),
    capacidad INT,
    disponible INT
);

CREATE TABLE IF NOT EXISTS ventas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    fecha DATE,
    total DECIMAL(10,2),
    empleado_id INT,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE CASCADE
);

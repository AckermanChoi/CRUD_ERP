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
    contrasena VARCHAR(255) NOT NULL 
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
    empleado_id INT,
    FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE CASCADE
);


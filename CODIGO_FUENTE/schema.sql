PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS mail_log;
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS envios_repuestos_detalles;
DROP TABLE IF EXISTS envios_repuestos;
DROP TABLE IF EXISTS repuestos_faltantes;
DROP TABLE IF EXISTS dml_repuestos;
DROP TABLE IF EXISTS dml_partes;
DROP TABLE IF EXISTS dml_fichas;
DROP TABLE IF EXISTS stock_ubicaciones;
DROP TABLE IF EXISTS stock_dml;
DROP TABLE IF EXISTS matriz_repuestos;
DROP TABLE IF EXISTS raypac_entries;
DROP TABLE IF EXISTS users;

-- Tabla de Usuarios
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    nombre TEXT,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tabla RAYPAC - Ingreso inicial
CREATE TABLE raypac_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_correlativo INTEGER,
    fecha_recepcion TEXT NOT NULL,
    tipo_solicitud TEXT NOT NULL,
    cliente TEXT NOT NULL,
    numero_serie TEXT NOT NULL UNIQUE,
    modelo_maquina TEXT NOT NULL,
    tipo_maquina TEXT NOT NULL,
    numero_bateria TEXT,
    numero_cargador TEXT,
    diagnostico_ingreso TEXT,
    comercial TEXT NOT NULL,
    mail_comercial TEXT NOT NULL,
    numero_remito TEXT,
    is_frozen INTEGER NOT NULL DEFAULT 0,
    frozen_at TEXT,
    unfrozen_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Matriz de Repuestos (catálogo)
CREATE TABLE matriz_repuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL UNIQUE,
    item TEXT NOT NULL,
    cantidad_inicial INTEGER NOT NULL,
    cantidad_actual INTEGER NOT NULL,
    ubicacion TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Stock DML (inventario general)
CREATE TABLE stock_dml (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_repuesto TEXT NOT NULL UNIQUE,
    item TEXT,
    cantidad INTEGER NOT NULL DEFAULT 0,
    cantidad_minima INTEGER DEFAULT 2,
    estado_alerta TEXT DEFAULT 'OK',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
);

-- Stock por Ubicación (RAYPAC y DML)
CREATE TABLE stock_ubicaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_repuesto TEXT NOT NULL,
    ubicacion TEXT NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(codigo_repuesto, ubicacion),
    FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
);

-- Tabla DML Fichas - Servicio Técnico
CREATE TABLE dml_fichas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_ficha INTEGER UNIQUE NOT NULL,
    raypac_id INTEGER NOT NULL,
    fecha_ingreso TEXT NOT NULL,
    tecnico TEXT NOT NULL,
    numero_ticket TEXT UNIQUE,
    diagnostico_inicial TEXT,
    diagnostico_reparacion TEXT,
    observaciones TEXT,
    estado_reparacion TEXT DEFAULT 'A LA ESPERA DE REVISIÓN',
    n_ciclos INTEGER,
    mecanizado_adic TEXT,
    horas_adic REAL,
    tipo_trabajo TEXT NOT NULL DEFAULT 'REPARACIÓN',
    tecnico_resp TEXT NOT NULL,
    fecha_egreso TEXT,
    numero_remito_salida TEXT,
    is_closed INTEGER NOT NULL DEFAULT 0,
    closed_at TEXT,
    ticket_enviado INTEGER DEFAULT 0,
    ficha_generada INTEGER DEFAULT 0,
    pdf_ficha BLOB,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(raypac_id) REFERENCES raypac_entries(id) ON DELETE CASCADE
);

-- Partes del Equipo (12 partes estándar)
CREATE TABLE dml_partes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ficha_id INTEGER NOT NULL,
    nombre_parte TEXT NOT NULL,
    estado TEXT NOT NULL,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE
);

-- Repuestos Utilizados en Reparación (hasta 15)
CREATE TABLE dml_repuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ficha_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    descripcion TEXT,
    cantidad INTEGER NOT NULL DEFAULT 1,
    cantidad_utilizada INTEGER DEFAULT 1,
    estado_repuesto TEXT DEFAULT 'INSPECCIONADO',
    en_stock INTEGER DEFAULT 0,
    en_falta INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE
);

-- Repuestos Faltantes en Transición
CREATE TABLE repuestos_faltantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ficha_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    descripcion TEXT,
    cantidad INTEGER NOT NULL,
    fecha_falta TEXT DEFAULT CURRENT_TIMESTAMP,
    fecha_llegada TEXT,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE
);

-- Envios de Repuestos RAYPAC a DML
CREATE TABLE envios_repuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_remito TEXT UNIQUE NOT NULL,
    fecha_envio TEXT NOT NULL,
    fecha_recepcion TEXT,
    estado TEXT DEFAULT 'PENDIENTE',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Detalles de Envios
CREATE TABLE envios_repuestos_detalles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    envio_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    FOREIGN KEY(envio_id) REFERENCES envios_repuestos(id) ON DELETE CASCADE
);

-- Auditoría
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Log de Correos
CREATE TABLE mail_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ficha_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'sent',
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id)
);

-- ======================== NUEVAS TABLAS PARA REQUERIMIENTOS ========================

-- Tickets de Seguimiento
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_ticket TEXT UNIQUE NOT NULL,
    ficha_id INTEGER NOT NULL,
    numero_serie TEXT NOT NULL,
    estado TEXT DEFAULT 'ACTIVO',
    fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE,
    UNIQUE(numero_ticket)
);

-- Historial de Seguimiento de Tickets
CREATE TABLE ticket_historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT NOT NULL,
    motivo TEXT,
    usuario_id INTEGER,
    fecha TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY(usuario_id) REFERENCES users(id)
);

-- Alertas de Stock
CREATE TABLE stock_alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad_actual INTEGER,
    nivel_alerta TEXT NOT NULL,
    email_enviado INTEGER DEFAULT 0,
    fecha_alerta TEXT DEFAULT CURRENT_TIMESTAMP,
    fecha_resuelto TEXT,
    FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
);

-- Estadísticas de Repuestos (salida/movimiento)
CREATE TABLE estadisticas_repuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad_utilizada INTEGER DEFAULT 0,
    fecha_ultimo_uso TEXT,
    total_usos INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
);

-- Freezing/Desfreeze de Registros
CREATE TABLE freezing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabla_nombre TEXT NOT NULL,
    registro_id INTEGER NOT NULL,
    estado_freezing INTEGER NOT NULL,
    usuario_freeze INTEGER,
    fecha_freeze TEXT,
    usuario_unfreeze INTEGER,
    fecha_unfreeze TEXT,
    motivo_unfreeze TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(usuario_freeze) REFERENCES users(id),
    FOREIGN KEY(usuario_unfreeze) REFERENCES users(id)
);

-- ======================== STOCK INICIAL ========================
-- Los repuestos se cargan automáticamente desde CSV en load_seed_data()
-- Comentado para evitar duplicados con el CSV completo

-- ======================== USUARIOS INICIALES ========================
-- Contraseñas: admin/admin, raypac/raypac, tecnico/tecnico, repuestos/repuestos

--INSERT INTO users (email, password_hash, nombre, role, is_active) VALUES
--('admin@dml.local', 'pbkdf2:sha256:600000$6A2RbBVTCNKXL7de$75969207ac15a7e7c63186bd53b919c17b722a89500a7fc6eb60cb3b20cdef7d', 'Administrador', 'ADMIN', 1),
--('raypac@dml.local', 'pbkdf2:sha256:600000$aSrOi7eCprUIyoPQ$86de1f158beaf6d954e51fc29a03f8e33749c4993ed3327256b821e5a4fab30d', 'RAYPAC', 'RAYPAC', 1),
--('tecnico@dml.local', 'pbkdf2:sha256:600000$bQ5PGbB2osS0xFi3$9cc5715d44a91e16db07e75d67842d981132af4d2d385164d2c5c0a906c3b8a7', 'Servicio Técnico', 'DML_ST', 1),
--('repuestos@dml.local', 'pbkdf2:sha256:600000$SyoM7kdkrIC3rxrS$e5e182cfd55f3482cbc5665339081ec5a90b3234a2d591634bd1ce89ea17cf47', 'Repuestos', 'DML_REPUESTOS', 1);

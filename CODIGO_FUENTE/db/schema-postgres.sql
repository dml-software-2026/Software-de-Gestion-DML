
DROP TABLE IF EXISTS mail_log CASCADE;
DROP TABLE IF EXISTS logs_auditoria CASCADE;
DROP TABLE IF EXISTS envios_repuestos_detalles CASCADE;
DROP TABLE IF EXISTS envios_repuestos CASCADE;
DROP TABLE IF EXISTS repuestos_faltantes CASCADE;
DROP TABLE IF EXISTS dml_repuestos CASCADE;
DROP TABLE IF EXISTS dml_partes CASCADE;
DROP TABLE IF EXISTS estado_general CASCADE;
DROP TABLE IF EXISTS ticket_historial CASCADE;
DROP TABLE IF EXISTS tickets CASCADE;
DROP TABLE IF EXISTS dml_fichas CASCADE;
DROP TABLE IF EXISTS stock_ubicaciones CASCADE;
DROP TABLE IF EXISTS stock_dml CASCADE;
DROP TABLE IF EXISTS matriz_repuestos CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;
DROP TABLE IF EXISTS usuarios_notificaciones CASCADE;
DROP TABLE IF EXISTS raypac_entries CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS stock_alertas CASCADE;
DROP TABLE IF EXISTS estadisticas_repuestos CASCADE;
DROP TABLE IF EXISTS freezing_log CASCADE;
DROP TYPE IF EXISTS estado_equipo_enum CASCADE;
DROP TYPE IF EXISTS estado_carcaza_enum CASCADE;
DROP TYPE IF EXISTS estado_cubre_feedwheel_enum CASCADE;
DROP TYPE IF EXISTS estado_mango_enum CASCADE;
DROP TYPE IF EXISTS estado_botones_enum CASCADE;
DROP TYPE IF EXISTS estado_motor_arrastre_enum CASCADE;
DROP TYPE IF EXISTS estado_motor_sellado_enum CASCADE;
DROP TYPE IF EXISTS estado_cuchilla_enum CASCADE;
DROP TYPE IF EXISTS estado_servo_enum CASCADE;
DROP TYPE IF EXISTS estado_rueda_arrastre_enum CASCADE;
DROP TYPE IF EXISTS estado_resorte_manija_enum CASCADE;

-- Tabla de Usuarios
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    nombre TEXT,
    role TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Tabla RAYPAC - Ingreso inicial
CREATE TABLE raypac_entries (
    id SERIAL PRIMARY KEY,
    numero_correlativo INTEGER,
    fecha_recepcion DATE NOT NULL,
    tipo_solicitud TEXT NOT NULL,
    cliente TEXT NOT NULL,
    numero_serie TEXT NOT NULL,
    modelo_maquina TEXT NOT NULL,
    tipo_maquina TEXT NOT NULL,
    numero_bateria TEXT,
    numero_cargador TEXT,
    diagnostico_ingreso TEXT,
    comercial TEXT NOT NULL,
    mail_comercial TEXT NOT NULL,
    contacto_cliente TEXT,
    email_cliente TEXT,
    numero_remito TEXT,
    is_frozen BOOLEAN DEFAULT FALSE,
    frozen_at DATE,
    unfrozen_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Catálogo de clientes RAYPAC (desplegable con autoaprendizaje, RF03)
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Destinatarios del mail automático de stock crítico (#59). Ver #161: esta
-- tabla nunca había estado en el schema versionado, aunque el código que la
-- usa (blueprints/notificaciones.py, services/stock.py) ya está mergeado.
CREATE TABLE usuarios_notificaciones (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    nombre TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Matriz de Repuestos (catálogo)
CREATE TABLE matriz_repuestos (
    id SERIAL PRIMARY KEY,
    numero INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL UNIQUE,
    item TEXT NOT NULL,
    cantidad_inicial INTEGER NOT NULL,
    cantidad_actual INTEGER NOT NULL,
    ubicacion TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Stock DML (inventario general)
CREATE TABLE stock_dml (
    id SERIAL PRIMARY KEY,
    codigo_repuesto TEXT NOT NULL UNIQUE,
    item TEXT,
    cantidad INTEGER NOT NULL DEFAULT 0,
    cantidad_minima INTEGER DEFAULT 2,
    estado_alerta TEXT DEFAULT 'OK',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
);

-- Stock por Ubicación (RAYPAC y DML)
CREATE TABLE stock_ubicaciones (
    id SERIAL PRIMARY KEY,
    codigo_repuesto TEXT NOT NULL,
    ubicacion TEXT NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(codigo_repuesto, ubicacion),
    FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
);

-- Tabla DML Fichas - Servicio Técnico
CREATE TABLE dml_fichas (
    id SERIAL PRIMARY KEY,
    numero_ficha INTEGER UNIQUE NOT NULL,
    raypac_id INTEGER NOT NULL,
    fecha_ingreso DATE,
    tecnico TEXT NOT NULL,
    numero_ticket TEXT UNIQUE,
    observaciones TEXT,
    diagnostico_inicial TEXT,
    diagnostico_reparacion TEXT,
    estado_reparacion TEXT DEFAULT 'A LA ESPERA DE REVISIÓN',
    n_ciclos INTEGER,
    mecanizado_adic TEXT,
    horas_adic REAL,
    tipo_trabajo TEXT NOT NULL DEFAULT 'REPARACIÓN',
    tecnico_resp TEXT NOT NULL,
    fecha_egreso DATE,
    numero_remito_salida TEXT,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    closed_at DATE,
    ticket_enviado INTEGER DEFAULT 0,
    ficha_generada INTEGER DEFAULT 0,
    pdf_ficha BYTEA,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(raypac_id) REFERENCES raypac_entries(id) ON DELETE CASCADE
);

CREATE TYPE estado_equipo_enum AS ENUM ('NO APLICA', 'BUENO', 'EXCELENTE', 'MALO', 'OK', 'REGULAR', 'HISTORICO');
CREATE TYPE estado_carcaza_enum AS ENUM ('NO APLICA', 'BUENO', 'CON TORNILLOS FALTANTES', 'EXCELENTE', 'MALO', 'OK', 'RAJADA', 'REGULAR', 'ROTA', 'HISTORICO');
CREATE TYPE estado_cubre_feedwheel_enum AS ENUM ('NO APLICA', 'CON TORNILLOS FALTANTES', 'FALTANTE', 'GOLPEADO', 'OK', 'RAJADO', 'ROTO', 'HISTORICO');
CREATE TYPE estado_mango_enum AS ENUM ('NO APLICA', 'CON TORNILLOS FALTANTES', 'GOLPEADO', 'OK', 'RAJADO', 'ROTO',  'HISTORICO');
CREATE TYPE estado_botones_enum AS ENUM ('NO APLICA', 'OK', 'ROTO', 'SIN FUNCIONAR', 'HISTORICO');
CREATE TYPE estado_motor_arrastre_enum AS ENUM ('NO APLICA', 'A PROBAR', 'FUNCIONAMIENTO OK', 'NO FUNCIONA', 'HISTORICO');
CREATE TYPE estado_motor_sellado_enum AS ENUM ('NO APLICA', 'A PROBAR', 'FUNCIONAMIENTO OK', 'NO FUNCIONA', 'HISTORICO');
CREATE TYPE estado_cuchilla_enum AS ENUM ('NO APLICA', 'CON DIENTES FALTANTES', 'DESGASTADA', 'FALTANTE', 'OK', 'ROTA', 'SIN FILO', 'HISTORICO');
CREATE TYPE estado_servo_enum AS ENUM ('NO APLICA', 'A PROBAR', 'FALTANTE', 'OK', 'ROTO', 'TRABADO', 'HISTORICO');
CREATE TYPE estado_rueda_arrastre_enum AS ENUM ('NO APLICA', 'DESGASTADO', 'FALTANTE', 'OK', 'HISTORICO');
CREATE TYPE estado_resorte_manija_enum AS ENUM ('NO APLICA', 'DESGASTADO', 'FALTANTE', 'OK', 'ROTO', 'HISTORICO');

--Tabla DML Campo de ingreso "Estado general"
CREATE TABLE estado_general (
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER NOT NULL UNIQUE,
    estado_equipo estado_equipo_enum,
    carcaza estado_carcaza_enum,
    cubre_feedwheel estado_cubre_feedwheel_enum,
    mango estado_mango_enum,
    botones estado_botones_enum,
    motor_arrastre estado_motor_arrastre_enum,
    motor_sellado estado_motor_sellado_enum,
    cuchilla estado_cuchilla_enum,
    servo estado_servo_enum,
    rueda_arrastre estado_rueda_arrastre_enum,
    resorte_manija estado_resorte_manija_enum,
    otros TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE
);

-- Partes del Equipo (12 partes estándar)
CREATE TABLE dml_partes (
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER NOT NULL,
    nombre_parte TEXT NOT NULL,
    estado TEXT NOT NULL,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE
);

-- Repuestos Utilizados en Reparación (hasta 15)
CREATE TABLE dml_repuestos (
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    descripcion TEXT,
    cantidad INTEGER NOT NULL DEFAULT 1,
    cantidad_utilizada INTEGER DEFAULT 1,
    estado_repuesto TEXT DEFAULT 'INSPECCIONADO',
    en_stock INTEGER DEFAULT 0,
    en_falta INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE
);

-- Repuestos Faltantes en Transición
CREATE TABLE repuestos_faltantes (
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    descripcion TEXT,
    cantidad INTEGER NOT NULL,
    fecha_falta TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_llegada DATE,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE
);

-- Envios de Repuestos RAYPAC a DML
CREATE TABLE envios_repuestos (
    id SERIAL PRIMARY KEY,
    numero_remito TEXT UNIQUE NOT NULL,
    fecha_envio DATE NOT NULL,
    fecha_recepcion DATE,
    estado TEXT DEFAULT 'PENDIENTE',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Detalles de Envios
CREATE TABLE envios_repuestos_detalles (
    id SERIAL PRIMARY KEY,
    envio_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    FOREIGN KEY(envio_id) REFERENCES envios_repuestos(id) ON DELETE CASCADE
);

-- Auditoría
CREATE TABLE logs_auditoria (
    id_log UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario INTEGER NOT NULL REFERENCES users(id),
    tipo_accion TEXT NOT NULL CHECK (tipo_accion IN ('INSERT', 'UPDATE', 'DELETE')),
    tabla_afectada TEXT NOT NULL,
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    FOREIGN KEY(id_usuario) REFERENCES users(id)
);

-- Log de Correos
CREATE TABLE mail_log (
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'sent',
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id)
);

-- ======================== NUEVAS TABLAS PARA REQUERIMIENTOS ========================

-- Tickets de Seguimiento
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    numero_ticket TEXT UNIQUE NOT NULL,
    ficha_id INTEGER NOT NULL,
    numero_serie TEXT NOT NULL,
    estado TEXT DEFAULT 'ACTIVO',
    fecha_creacion TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ficha_id) REFERENCES dml_fichas(id) ON DELETE CASCADE,
    UNIQUE(numero_ticket)
);

-- Historial de Seguimiento de Tickets
CREATE TABLE ticket_historial (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT NOT NULL,
    motivo TEXT,
    usuario_id INTEGER,
    fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    FOREIGN KEY(usuario_id) REFERENCES users(id)
);

-- Alertas de Stock
CREATE TABLE stock_alertas (
    id SERIAL PRIMARY KEY,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad_actual INTEGER,
    nivel_alerta TEXT NOT NULL,
    email_enviado BOOLEAN DEFAULT FALSE,
    fecha_alerta TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_resuelto DATE,
    FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
);

-- Estadísticas de Repuestos (salida/movimiento)
CREATE TABLE estadisticas_repuestos (
    id SERIAL PRIMARY KEY,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad_utilizada INTEGER DEFAULT 0,
    fecha_ultimo_uso DATE,
    total_usos INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(codigo_repuesto) REFERENCES matriz_repuestos(codigo_repuesto)
);

-- Freezing/Desfreeze de Registros
CREATE TABLE freezing_log (
    id SERIAL PRIMARY KEY,
    tabla_nombre TEXT NOT NULL,
    registro_id INTEGER NOT NULL,
    estado_freezing INTEGER NOT NULL,
    usuario_freeze INTEGER,
    fecha_freeze DATE,
    usuario_unfreeze INTEGER,
    fecha_unfreeze DATE,
    motivo_unfreeze TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(usuario_freeze) REFERENCES users(id),
    FOREIGN KEY(usuario_unfreeze) REFERENCES users(id)
);



-- ======================== STOCK INICIAL ========================
-- Los repuestos se cargan automáticamente desde CSV en load_seed_data()
-- Comentado para evitar duplicados con el CSV completo

-- ======================== USUARIOS INICIALES ========================
-- Contraseñas: admin/admin, raypac/raypac, tecnico/tecnico, repuestos/repuestos

INSERT INTO users (email, password_hash, nombre, role, is_active) VALUES
('admin@dml.local', 'pbkdf2:sha256:600000$6A2RbBVTCNKXL7de$75969207ac15a7e7c63186bd53b919c17b722a89500a7fc6eb60cb3b20cdef7d', 'Administrador', 'ADMIN', TRUE),
('raypac@dml.local', 'pbkdf2:sha256:600000$aSrOi7eCprUIyoPQ$86de1f158beaf6d954e51fc29a03f8e33749c4993ed3327256b821e5a4fab30d', 'RAYPAC', 'RAYPAC', TRUE),
('tecnico@dml.local', 'pbkdf2:sha256:600000$bQ5PGbB2osS0xFi3$9cc5715d44a91e16db07e75d67842d981132af4d2d385164d2c5c0a906c3b8a7', 'Servicio Técnico', 'DML_ST', TRUE),
('repuestos@dml.local', 'pbkdf2:sha256:600000$SyoM7kdkrIC3rxrS$e5e182cfd55f3482cbc5665339081ec5a90b3234a2d591634bd1ce89ea17cf47', 'Repuestos', 'DML_REPUESTOS', TRUE);

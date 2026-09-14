-- =====================================================
-- schema-postgres.sql
-- Refleja el estado real de las tablas del proyecto.
-- Edición manual. NO se genera con scripts/sync_schema.py
-- (ese script leía Supabase y sobreescribía este archivo —
-- deprecado, no usar más).
-- El flujo correcto es el inverso: este archivo es la fuente
-- de verdad y se aplica a la base con scripts/aplicar_schema.py.
-- =====================================================
 
-- NOTA: raypac_entries tiene dos columnas parecidas:
-- "numero_correlatico" (con typo, columna original) y
-- "numero_correlativo" (agregada después, bien escrita).
-- No se sabe con certeza si son la misma columna duplicada por
-- error o dos columnas distintas en uso. Verificar contra
-- Supabase (\d raypac_entries) antes de eliminar cualquiera.
 
-- Tipos ENUM
CREATE TYPE estado_botones_enum AS ENUM ('NO APLICA', 'OK', 'ROTO', 'SIN FUNCIONAR', 'HISTORICO');
CREATE TYPE estado_carcaza_enum AS ENUM ('NO APLICA', 'BUENO', 'CON TORNILLOS FALTANTES', 'EXCELENTE', 'MALO', 'OK', 'RAJADA', 'REGULAR', 'ROTA', 'HISTORICO');
CREATE TYPE estado_cubre_feedwheel_enum AS ENUM ('NO APLICA', 'CON TORNILLOS FALTANTES', 'FALTANTE', 'GOLPEADO', 'OK', 'RAJADO', 'ROTO', 'HISTORICO');
CREATE TYPE estado_cuchilla_enum AS ENUM ('NO APLICA', 'CON DIENTES FALTANTES', 'DESGASTADA', 'FALTANTE', 'OK', 'ROTA', 'SIN FILO', 'HISTORICO');
CREATE TYPE estado_equipo_enum AS ENUM ('NO APLICA', 'BUENO', 'EXCELENTE', 'MALO', 'OK', 'REGULAR', 'HISTORICO');
CREATE TYPE estado_mango_enum AS ENUM ('NO APLICA', 'CON TORNILLOS FALTANTES', 'GOLPEADO', 'OK', 'RAJADO', 'ROTO', 'HISTORICO');
CREATE TYPE estado_motor_arrastre_enum AS ENUM ('NO APLICA', 'A PROBAR', 'FUNCIONAMIENTO OK', 'NO FUNCIONA', 'HISTORICO');
CREATE TYPE estado_motor_sellado_enum AS ENUM ('NO APLICA', 'A PROBAR', 'FUNCIONAMIENTO OK', 'NO FUNCIONA', 'HISTORICO');
CREATE TYPE estado_resorte_manija_enum AS ENUM ('NO APLICA', 'DESGASTADO', 'FALTANTE', 'OK', 'ROTO', 'HISTORICO');
CREATE TYPE estado_rueda_arrastre_enum AS ENUM ('NO APLICA', 'DESGASTADO', 'FALTANTE', 'OK', 'HISTORICO');
CREATE TYPE estado_servo_enum AS ENUM ('NO APLICA', 'A PROBAR', 'FALTANTE', 'OK', 'ROTO', 'TRABADO', 'HISTORICO');
 
-- Tablas sin dependencias
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
 
CREATE TABLE clientes (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
 
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
 
CREATE TABLE raypac_entries (
    id SERIAL PRIMARY KEY,
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
    numero_remito TEXT,
    is_frozen BOOLEAN DEFAULT FALSE,
    frozen_at DATE,
    unfrozen_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    contacto_cliente TEXT,
    email_cliente TEXT,
    estado_envio_equipos TEXT DEFAULT 'PENDIENTE',
    fecha_envio_equipos TIMESTAMP,
    numero_correlativo INTEGER
);
 
CREATE TABLE usuarios_notificaciones (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    nombre VARCHAR(100),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT NOW()
);
 
-- Depende de matriz_repuestos
CREATE TABLE stock_dml (
    id SERIAL PRIMARY KEY,
    codigo_repuesto TEXT NOT NULL UNIQUE,
    item TEXT,
    cantidad INTEGER NOT NULL DEFAULT 0,
    cantidad_minima INTEGER DEFAULT 2,
    estado_alerta TEXT DEFAULT 'OK',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (codigo_repuesto) REFERENCES matriz_repuestos (codigo_repuesto)
);
 
CREATE TABLE stock_ubicaciones (
    id SERIAL PRIMARY KEY,
    codigo_repuesto TEXT NOT NULL,
    ubicacion TEXT NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    codigo_ubicacion_fisica TEXT DEFAULT 'SIN UBICACIÓN',
    UNIQUE (codigo_repuesto, ubicacion),
    FOREIGN KEY (codigo_repuesto) REFERENCES matriz_repuestos (codigo_repuesto)
);
 
CREATE TABLE stock_alertas (
    id SERIAL PRIMARY KEY,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad_actual INTEGER,
    nivel_alerta TEXT NOT NULL,
    email_enviado BOOLEAN DEFAULT FALSE,
    fecha_alerta TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_resuelto DATE,
    FOREIGN KEY (codigo_repuesto) REFERENCES matriz_repuestos (codigo_repuesto)
);
 
CREATE TABLE estadisticas_repuestos (
    id SERIAL PRIMARY KEY,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad_utilizada INTEGER DEFAULT 0,
    fecha_ultimo_uso DATE,
    total_usos INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (codigo_repuesto) REFERENCES matriz_repuestos (codigo_repuesto)
);
 
-- Depende de users
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
    FOREIGN KEY (usuario_freeze) REFERENCES users (id),
    FOREIGN KEY (usuario_unfreeze) REFERENCES users (id)
);
 
CREATE TABLE logs_auditoria (
    id_log UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    id_usuario INTEGER NOT NULL,
    tipo_accion TEXT NOT NULL CHECK (tipo_accion IN ('INSERT', 'UPDATE', 'DELETE')),
    tabla_afectada TEXT NOT NULL,
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    FOREIGN KEY (id_usuario) REFERENCES users (id)
);
 
CREATE TABLE envios_repuestos (
    id SERIAL PRIMARY KEY,
    numero_remito TEXT UNIQUE NOT NULL,
    fecha_envio DATE NOT NULL,
    fecha_recepcion DATE,
    estado TEXT DEFAULT 'PENDIENTE',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    estado_envio TEXT DEFAULT 'ENVIADO',
    is_frozen BOOLEAN DEFAULT TRUE,
    fecha_recepcion_dml TIMESTAMP,
    usuario_recepcion_id INTEGER,
    tipo_entrega TEXT DEFAULT 'REPUESTOS',
    FOREIGN KEY (usuario_recepcion_id) REFERENCES users (id)
);
 
CREATE TABLE envios_repuestos_detalles (
    id SERIAL PRIMARY KEY,
    envio_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    FOREIGN KEY (envio_id) REFERENCES envios_repuestos (id) ON DELETE CASCADE
);
 
-- dml_fichas: depende de raypac_entries.
-- La FK a tickets(id) (columna ticket_id) es circular con tickets,
-- que a su vez depende de dml_fichas(id) -> se agrega al final con ALTER TABLE.
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
    fecha_entrega_cliente TIMESTAMP,
    recibido_por TEXT,
    ticket_id INTEGER,
    FOREIGN KEY (raypac_id) REFERENCES raypac_entries (id) ON DELETE CASCADE
);
 
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
    FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE
);
 
CREATE TABLE dml_partes (
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER NOT NULL,
    nombre_parte TEXT NOT NULL,
    estado TEXT NOT NULL,
    FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE
);
 
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
    FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE
);
 
CREATE TABLE repuestos_faltantes (
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    descripcion TEXT,
    cantidad INTEGER NOT NULL,
    fecha_falta TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_llegada DATE,
    FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE
);
 
CREATE TABLE mail_log (
    id SERIAL PRIMARY KEY,
    ficha_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'sent',
    FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id)
);
 
-- tickets: depende de dml_fichas y raypac_entries
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    numero_ticket TEXT UNIQUE NOT NULL,
    ficha_id INTEGER,
    numero_serie TEXT NOT NULL,
    estado TEXT DEFAULT 'ACTIVO',
    fecha_creacion TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    raypac_id INTEGER,
    fecha_ingreso TEXT,
    tecnico_responsable TEXT,
    observaciones TEXT,
    estado_equipo TEXT DEFAULT 'BUENO',
    carcaza TEXT DEFAULT 'BUENO',
    cubre_feedwheel TEXT DEFAULT 'BUENO',
    mango TEXT DEFAULT 'BUENO',
    botones TEXT DEFAULT 'BUENO',
    motor_arrastre TEXT DEFAULT 'BUENO',
    motor_sellado TEXT DEFAULT 'BUENO',
    cuchilla TEXT DEFAULT 'BUENO',
    servo TEXT DEFAULT 'BUENO',
    rueda_arrastre TEXT DEFAULT 'BUENO',
    resorte_manija TEXT DEFAULT 'BUENO',
    otros TEXT DEFAULT 'BUENO',
    FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE,
    FOREIGN KEY (raypac_id) REFERENCES raypac_entries (id)
);
 
CREATE TABLE ticket_historial (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT NOT NULL,
    motivo TEXT,
    usuario_id INTEGER,
    fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets (id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES users (id)
);
 
-- FK circular: dml_fichas.ticket_id -> tickets(id)
-- (tickets no existía todavía cuando se creó dml_fichas)
ALTER TABLE dml_fichas ADD CONSTRAINT fk_dml_fichas_ticket_id
    FOREIGN KEY (ticket_id) REFERENCES tickets (id);
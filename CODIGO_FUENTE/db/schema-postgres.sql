-- =====================================================
-- schema-postgres.sql
-- GENERADO AUTOMÁTICAMENTE por scripts/sync_schema.py
-- NO EDITAR A MANO — los cambios se pierden en el próximo sync.
--
-- Refleja el estado real de la base al momento de correr el
-- script. Los cambios incrementales de schema se hacen vía
-- migrate_db() en CODIGO_FUENTE/extensions.py; este archivo es
-- solo documentación versionada en git, generada después del
-- hecho — no se corre manualmente contra Supabase.
-- =====================================================

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


CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL,
    nombre TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (nombre)
);

CREATE TABLE IF NOT EXISTS dml_fichas (
    id SERIAL,
    numero_ficha INTEGER NOT NULL,
    raypac_id INTEGER NOT NULL,
    fecha_ingreso DATE,
    tecnico TEXT NOT NULL,
    numero_ticket TEXT,
    observaciones TEXT,
    diagnostico_inicial TEXT,
    diagnostico_reparacion TEXT,
    estado_reparacion TEXT DEFAULT 'A LA ESPERA DE REVISIÓN'::text,
    n_ciclos INTEGER,
    mecanizado_adic TEXT,
    horas_adic REAL,
    tipo_trabajo TEXT NOT NULL DEFAULT 'REPARACIÓN'::text,
    tecnico_resp TEXT NOT NULL,
    fecha_egreso DATE,
    numero_remito_salida TEXT,
    is_closed BOOLEAN NOT NULL DEFAULT false,
    closed_at DATE,
    ticket_enviado INTEGER DEFAULT 0,
    ficha_generada INTEGER DEFAULT 0,
    pdf_ficha bytea,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_entrega_cliente TIMESTAMP,
    recibido_por TEXT,
    ticket_id INTEGER,
    PRIMARY KEY (id),
    UNIQUE (numero_ficha),
    UNIQUE (numero_ticket)
);

CREATE TABLE IF NOT EXISTS dml_partes (
    id SERIAL,
    ficha_id INTEGER NOT NULL,
    nombre_parte TEXT NOT NULL,
    estado TEXT NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS dml_repuestos (
    id SERIAL,
    ficha_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    descripcion TEXT,
    cantidad INTEGER NOT NULL DEFAULT 1,
    cantidad_utilizada INTEGER DEFAULT 1,
    estado_repuesto TEXT DEFAULT 'INSPECCIONADO'::text,
    en_stock INTEGER DEFAULT 0,
    en_falta INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS envios_repuestos (
    id SERIAL,
    numero_remito TEXT NOT NULL,
    fecha_envio DATE NOT NULL,
    fecha_recepcion DATE,
    estado TEXT DEFAULT 'PENDIENTE'::text,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    estado_envio TEXT DEFAULT 'ENVIADO'::text,
    is_frozen BOOLEAN DEFAULT true,
    fecha_recepcion_dml TIMESTAMP,
    usuario_recepcion_id INTEGER,
    tipo_entrega TEXT DEFAULT 'REPUESTOS'::text,
    PRIMARY KEY (id),
    UNIQUE (numero_remito)
);

CREATE TABLE IF NOT EXISTS envios_repuestos_detalles (
    id SERIAL,
    envio_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS estadisticas_repuestos (
    id SERIAL,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad_utilizada INTEGER DEFAULT 0,
    fecha_ultimo_uso DATE,
    total_usos INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS estado_general (
    id SERIAL,
    ficha_id INTEGER NOT NULL,
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
    PRIMARY KEY (id),
    UNIQUE (ficha_id)
);

CREATE TABLE IF NOT EXISTS freezing_log (
    id SERIAL,
    tabla_nombre TEXT NOT NULL,
    registro_id INTEGER NOT NULL,
    estado_freezing INTEGER NOT NULL,
    usuario_freeze INTEGER,
    fecha_freeze DATE,
    usuario_unfreeze INTEGER,
    fecha_unfreeze DATE,
    motivo_unfreeze TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS logs_auditoria (
    id_log UUID NOT NULL DEFAULT gen_random_uuid(),
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT now(),
    id_usuario INTEGER NOT NULL,
    tipo_accion TEXT NOT NULL,
    tabla_afectada TEXT NOT NULL,
    record_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    PRIMARY KEY (id_log)
);

CREATE TABLE IF NOT EXISTS mail_log (
    id SERIAL,
    ficha_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT,
    body TEXT,
    sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'sent'::text,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS matriz_repuestos (
    id SERIAL,
    numero INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    item TEXT NOT NULL,
    cantidad_inicial INTEGER NOT NULL,
    cantidad_actual INTEGER NOT NULL,
    ubicacion TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (codigo_repuesto)
);

CREATE TABLE IF NOT EXISTS raypac_entries (
    id SERIAL,
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
    is_frozen BOOLEAN DEFAULT false,
    frozen_at DATE,
    unfrozen_by TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    estado_envio_equipos TEXT DEFAULT 'PENDIENTE'::text,
    fecha_envio_equipos TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS repuestos_faltantes (
    id SERIAL,
    ficha_id INTEGER NOT NULL,
    codigo_repuesto TEXT NOT NULL,
    descripcion TEXT,
    cantidad INTEGER NOT NULL,
    fecha_falta TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_llegada DATE,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS stock_alertas (
    id SERIAL,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad_actual INTEGER,
    nivel_alerta TEXT NOT NULL,
    email_enviado BOOLEAN DEFAULT false,
    fecha_alerta TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_resuelto DATE,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS stock_dml (
    id SERIAL,
    codigo_repuesto TEXT NOT NULL,
    item TEXT,
    cantidad INTEGER NOT NULL DEFAULT 0,
    cantidad_minima INTEGER DEFAULT 2,
    estado_alerta TEXT DEFAULT 'OK'::text,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (codigo_repuesto)
);

CREATE TABLE IF NOT EXISTS stock_ubicaciones (
    id SERIAL,
    codigo_repuesto TEXT NOT NULL,
    ubicacion TEXT NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    codigo_ubicacion_fisica TEXT DEFAULT 'SIN UBICACIÓN'::text,
    PRIMARY KEY (id),
    UNIQUE (codigo_repuesto, ubicacion)
);

CREATE TABLE IF NOT EXISTS ticket_historial (
    id SERIAL,
    ticket_id INTEGER NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT NOT NULL,
    motivo TEXT,
    usuario_id INTEGER,
    fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL,
    numero_ticket TEXT NOT NULL,
    ficha_id INTEGER,
    numero_serie TEXT NOT NULL,
    estado TEXT DEFAULT 'ACTIVO'::text,
    fecha_creacion TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre DATE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    raypac_id INTEGER,
    fecha_ingreso TEXT,
    tecnico_responsable TEXT,
    observaciones TEXT,
    estado_equipo TEXT DEFAULT 'BUENO'::text,
    carcaza TEXT DEFAULT 'BUENO'::text,
    cubre_feedwheel TEXT DEFAULT 'BUENO'::text,
    mango TEXT DEFAULT 'BUENO'::text,
    botones TEXT DEFAULT 'BUENO'::text,
    motor_arrastre TEXT DEFAULT 'BUENO'::text,
    motor_sellado TEXT DEFAULT 'BUENO'::text,
    cuchilla TEXT DEFAULT 'BUENO'::text,
    servo TEXT DEFAULT 'BUENO'::text,
    rueda_arrastre TEXT DEFAULT 'BUENO'::text,
    resorte_manija TEXT DEFAULT 'BUENO'::text,
    otros TEXT DEFAULT 'BUENO'::text,
    PRIMARY KEY (id),
    UNIQUE (numero_ticket)
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    nombre TEXT,
    role TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS usuarios_notificaciones (
    id SERIAL,
    email VARCHAR(255) NOT NULL,
    nombre VARCHAR(100),
    activo BOOLEAN NOT NULL DEFAULT true,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (email)
);

-- Foreign keys
ALTER TABLE dml_fichas ADD CONSTRAINT IF NOT EXISTS fk_dml_fichas_raypac_id FOREIGN KEY (raypac_id) REFERENCES raypac_entries (id) ON DELETE CASCADE;
ALTER TABLE dml_fichas ADD CONSTRAINT IF NOT EXISTS fk_dml_fichas_ticket_id FOREIGN KEY (ticket_id) REFERENCES tickets (id);
ALTER TABLE dml_partes ADD CONSTRAINT IF NOT EXISTS fk_dml_partes_ficha_id FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE;
ALTER TABLE dml_repuestos ADD CONSTRAINT IF NOT EXISTS fk_dml_repuestos_ficha_id FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE;
ALTER TABLE envios_repuestos ADD CONSTRAINT IF NOT EXISTS fk_envios_repuestos_usuario_recepcion_id FOREIGN KEY (usuario_recepcion_id) REFERENCES users (id);
ALTER TABLE envios_repuestos_detalles ADD CONSTRAINT IF NOT EXISTS fk_envios_repuestos_detalles_envio_id FOREIGN KEY (envio_id) REFERENCES envios_repuestos (id) ON DELETE CASCADE;
ALTER TABLE estadisticas_repuestos ADD CONSTRAINT IF NOT EXISTS fk_estadisticas_repuestos_codigo_repuesto FOREIGN KEY (codigo_repuesto) REFERENCES matriz_repuestos (codigo_repuesto);
ALTER TABLE estado_general ADD CONSTRAINT IF NOT EXISTS fk_estado_general_ficha_id FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE;
ALTER TABLE freezing_log ADD CONSTRAINT IF NOT EXISTS fk_freezing_log_usuario_freeze FOREIGN KEY (usuario_freeze) REFERENCES users (id);
ALTER TABLE freezing_log ADD CONSTRAINT IF NOT EXISTS fk_freezing_log_usuario_unfreeze FOREIGN KEY (usuario_unfreeze) REFERENCES users (id);
ALTER TABLE logs_auditoria ADD CONSTRAINT IF NOT EXISTS fk_logs_auditoria_id_usuario FOREIGN KEY (id_usuario) REFERENCES users (id);
ALTER TABLE mail_log ADD CONSTRAINT IF NOT EXISTS fk_mail_log_ficha_id FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id);
ALTER TABLE repuestos_faltantes ADD CONSTRAINT IF NOT EXISTS fk_repuestos_faltantes_ficha_id FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE;
ALTER TABLE stock_alertas ADD CONSTRAINT IF NOT EXISTS fk_stock_alertas_codigo_repuesto FOREIGN KEY (codigo_repuesto) REFERENCES matriz_repuestos (codigo_repuesto);
ALTER TABLE stock_dml ADD CONSTRAINT IF NOT EXISTS fk_stock_dml_codigo_repuesto FOREIGN KEY (codigo_repuesto) REFERENCES matriz_repuestos (codigo_repuesto);
ALTER TABLE stock_ubicaciones ADD CONSTRAINT IF NOT EXISTS fk_stock_ubicaciones_codigo_repuesto FOREIGN KEY (codigo_repuesto) REFERENCES matriz_repuestos (codigo_repuesto);
ALTER TABLE ticket_historial ADD CONSTRAINT IF NOT EXISTS fk_ticket_historial_ticket_id FOREIGN KEY (ticket_id) REFERENCES tickets (id) ON DELETE CASCADE;
ALTER TABLE ticket_historial ADD CONSTRAINT IF NOT EXISTS fk_ticket_historial_usuario_id FOREIGN KEY (usuario_id) REFERENCES users (id);
ALTER TABLE tickets ADD CONSTRAINT IF NOT EXISTS fk_tickets_ficha_id FOREIGN KEY (ficha_id) REFERENCES dml_fichas (id) ON DELETE CASCADE;
ALTER TABLE tickets ADD CONSTRAINT IF NOT EXISTS fk_tickets_raypac_id FOREIGN KEY (raypac_id) REFERENCES raypac_entries (id);

# Arquitectura de DIO CRM

## Referencia técnica

`table_assistant` sirvió para ver cómo separar configuración, conexión, modelos, casos de uso y rutas en una API FastAPI. DIO CRM conserva esa separación y define su propio dominio.

## Módulos

- `app/core`: configuración, JWT, contraseñas y errores de dominio.
- `app/db`: modelos SQLAlchemy 2 y sesión.
- `app/services/crm.py`: reglas de empresa, pipeline, conversión de prospectos y totales de cotización.
- `app/api`: dependencias de autenticación y rutas `/api/v1`.
- `alembic/versions`: esquema. La revisión `0001_initial` queda vacía para no recrear ni borrar tablas de un prototipo anterior. `0002_crm` crea solo las tablas del CRM.

## Empresas

El registro crea la empresa, un usuario propietario y el pipeline Comercial con etapas Nuevo, Calificación, Propuesta, Negociación, Ganada y Perdida. El token incluye `tenant_id`. Las consultas filtran por esa empresa. Un identificador de otra empresa responde 404. Las claves foráneas compuestas impiden enlazar filas de empresas distintas.

Roles: `owner` y `admin` configuran usuarios, pipelines y campos; `sales` opera el ciclo comercial; `viewer` solo consulta.

## Cotizaciones

Si la línea apunta a un producto, el precio sale del catálogo. El servidor calcula subtotal, descuento y total. El cliente no envía el total.

Los usuarios del CRM viven en `crm_users`. Así la migración puede convivir con una tabla `users` anterior sin eliminarla.

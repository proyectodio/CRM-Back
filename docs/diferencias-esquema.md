# Esquema

Tablas del CRM: `tenants`, `crm_users`, `accounts`, `contacts`, `leads`, `pipelines`, `stages`, `opportunities`, `activities`, `products`, `quotes`, `quote_items`, `custom_fields`, `custom_field_values`.

Cada tabla de negocio lleva `tenant_id`. Los registros que se relacionan entre sí repiten la pareja `(id, tenant_id)` como clave foránea compuesta.

Si la base local ya tenía tablas de un prototipo previo, esas tablas permanecen. La aplicación del CRM no las consulta.

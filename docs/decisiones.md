# Decisiones de DIO CRM

- Una base PostgreSQL propia, publicada en el puerto 5433 del host.
- Alembic no borra tablas que ya existan de un prototipo anterior.
- Los usuarios del CRM se guardan en `crm_users`.
- El precio de una línea de cotización con producto se copia del catálogo en el momento de emitirla.
- El frontend no decide estados ni totales.

# DIO CRM — backend

API de un CRM empresarial multiempresa. Cada operación autenticada queda limitada a la empresa del token. PostgreSQL guarda los datos. FastAPI publica la API REST y su contrato OpenAPI.

La organización por capas —configuración, sesión de base de datos, modelos, servicios y rutas— toma como referencia la estructura técnica de `table_assistant`. El dominio comercial se diseñó para DIO CRM.

## Arranque local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload
```

- API: http://localhost:8000/api/v1
- Salud: http://localhost:8000/health
- Postgres del contenedor: `localhost:5433`
- Swagger: http://localhost:8000/docs

## Arranque con Docker

Desde la carpeta que contiene `CRM-Back` y `CRM-Front`:

```bash
docker compose up --build
```

Ese `compose.yaml` levanta PostgreSQL, la API y nginx. Nginx publica la interfaz y reenvía `/api`, `/health` y `/docs` a la API.

- Aplicación: http://localhost y http://localhost:4200
- API directa: http://localhost:8000
- Postgres publicado en el host: `localhost:5433`

## Pruebas

```bash
pytest
```

Las pruebas usan SQLite en memoria. Cubren el alta de empresa, el aislamiento entre empresas, el rol de consulta, el total de cotización calculado en el servidor, el rechazo de una etapa de otro pipeline y la unicidad de campos personalizados.

## Ramas

El trabajo nuevo va en `feature/<modulo>`, `fix/<tema>` o `docs/<tema>`. Los commits los hace quien mantiene el repositorio.

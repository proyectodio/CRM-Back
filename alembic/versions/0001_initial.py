"""La revisión 0001 ya fue aplicada en la base local anterior.

Esa revisión creó tablas de un prototipo que no pertenece al dominio del CRM.
No se vuelve a ejecutar su SQL y no se eliminan esas tablas: Alembic no debe
borrar datos ya existentes. El esquema de DIO CRM está en la revisión 0002.
"""

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

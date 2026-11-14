"""Adopt the existing prototype without replacing its data; initialize new installs."""
from alembic import op
import sqlalchemy as sa
from migrations.schema_v1 import Base

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    Base.metadata.create_all(connection)
    columns = {column["name"] for column in sa.inspect(connection).get_columns("analysis_run")}
    if "input_checksum" not in columns:
        op.add_column("analysis_run", sa.Column("input_checksum", sa.String(64), nullable=True))
    # Older local databases predate this constraint. A duplicate deliberately
    # fails migration rather than deleting or silently rewriting salary history.
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_salary_event ON salary_record (employee_id, effective_month, event_kind)")


def downgrade():
    raise RuntimeError("Baseline downgrade would destroy compensation history; restore a verified backup instead.")

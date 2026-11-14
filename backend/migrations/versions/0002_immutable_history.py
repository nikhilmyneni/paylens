"""Enforce append-only compensation and decision history at the database boundary."""
from alembic import op

revision = "0002_immutable_history"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None
TABLES = ("salary_record", "proposal_event", "audit_event")


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("""CREATE OR REPLACE FUNCTION reject_history_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'History is append-only: %', TG_TABLE_NAME;
        END; $$""")
        for table in TABLES:
            op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()")
    elif dialect == "sqlite":
        for table in TABLES:
            for operation in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'History is append-only'); END")
    else:
        raise RuntimeError(f"Unsupported database dialect: {dialect}")


def downgrade():
    dialect = op.get_bind().dialect.name
    for table in TABLES:
        if dialect == "postgresql":
            op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
        else:
            for operation in ("update", "delete"):
                op.execute(f"DROP TRIGGER IF EXISTS {table}_no_{operation}")
    if dialect == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS reject_history_mutation()")

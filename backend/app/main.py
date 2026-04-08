from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.router import api_router
from .core.database import engine, Base
from .models.report import Report
from .models.annotation import Annotation
from .models.import_task import ImportTask
from .models.collaboration import ReportCollaborationSession, ReportEditLock
from sqlalchemy.orm import Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建数据库表
    Base.metadata.create_all(bind=engine)

    # 数据库迁移：检查并添加缺失的列（保持 bool 语义）
    db = Session(engine)
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(engine)
        dialect_name = engine.dialect.name

        def create_index_if_missing(table_name: str, index_name: str, column_sql: str) -> None:
            existing_indexes = {item["name"] for item in inspector.get_indexes(table_name)}
            if index_name in existing_indexes:
                return
            with engine.connect() as conn:
                conn.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({column_sql})"))
                conn.commit()
            print(f"Added {index_name} index to {table_name} table")

        def add_json_list_column(table_name: str, column_name: str) -> None:
            with engine.connect() as conn:
                if dialect_name == "postgresql":
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} JSONB DEFAULT '[]'::jsonb"))
                    conn.execute(text(f"UPDATE {table_name} SET {column_name} = '[]'::jsonb WHERE {column_name} IS NULL"))
                    conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {column_name} SET NOT NULL"))
                else:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} JSON DEFAULT '[]'"))
                    conn.execute(text(f"UPDATE {table_name} SET {column_name} = '[]' WHERE {column_name} IS NULL"))
                conn.commit()

        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'employee_id' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN employee_id VARCHAR(32)"))
                conn.commit()
            print("Added employee_id column to users table")

        if 'can_view_all' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN can_view_all BOOLEAN DEFAULT FALSE"))
                conn.commit()
            print("Added can_view_all column to users table")

        if 'view_all_requested' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN view_all_requested BOOLEAN DEFAULT FALSE"))
                conn.commit()
            print("Added view_all_requested column to users table")

        if 'is_cancel' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_cancel BOOLEAN DEFAULT FALSE"))
                conn.commit()
            print("Added is_cancel column to users table")

        report_columns = [col['name'] for col in inspector.get_columns('reports')]
        if 'pre_annotations' not in report_columns:
            with engine.connect() as conn:
                if dialect_name == "postgresql":
                    conn.execute(text("ALTER TABLE reports ADD COLUMN pre_annotations JSONB"))
                else:
                    conn.execute(text("ALTER TABLE reports ADD COLUMN pre_annotations JSON"))
                conn.commit()
            print("Added pre_annotations column to reports table")

        if 'is_cancel' not in report_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN is_cancel BOOLEAN DEFAULT FALSE"))
                conn.commit()
            print("Added is_cancel column to reports table")

        if 'annotator_doctor_id' not in report_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN annotator_doctor_id INTEGER"))
                conn.commit()
            print("Added annotator_doctor_id column to reports table")

        if 'reviewer_doctor_id' not in report_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN reviewer_doctor_id INTEGER"))
                conn.commit()
            print("Added reviewer_doctor_id column to reports table")

        if 'review_assigned_at' not in report_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN review_assigned_at TIMESTAMPTZ"))
                conn.commit()
            print("Added review_assigned_at column to reports table")

        if 'reviewed_at' not in report_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN reviewed_at TIMESTAMP"))
                conn.commit()
            print("Added reviewed_at column to reports table")

        if 'review_completed_user_ids' not in report_columns:
            add_json_list_column('reports', 'review_completed_user_ids')
            print("Added review_completed_user_ids column to reports table")

        if 'review_completed_at' not in report_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN review_completed_at TIMESTAMP"))
                conn.commit()
            print("Added review_completed_at column to reports table")

        create_index_if_missing('reports', 'ix_reports_assigned_doctor_id', 'assigned_doctor_id')
        create_index_if_missing('reports', 'ix_reports_reviewer_doctor_id', 'reviewer_doctor_id')
        create_index_if_missing('reports', 'ix_reports_assigned_cancel_id', 'assigned_doctor_id, is_cancel, id')
        create_index_if_missing('reports', 'ix_reports_status_cancel_id', 'status, is_cancel, id')

        if inspector.has_table('annotations'):
            annotation_columns = [col['name'] for col in inspector.get_columns('annotations')]

            if 'annotation_user_ids' not in annotation_columns:
                add_json_list_column('annotations', 'annotation_user_ids')
                print("Added annotation_user_ids column to annotations table")

        if inspector.has_table('report_collaboration_sessions'):
            collaboration_columns = [col['name'] for col in inspector.get_columns('report_collaboration_sessions')]

            if 'active_status' not in collaboration_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE report_collaboration_sessions ADD COLUMN active_status VARCHAR(32)"))
                    conn.commit()
                print("Added active_status column to report_collaboration_sessions table")

            if 'active_label' not in collaboration_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE report_collaboration_sessions ADD COLUMN active_label VARCHAR(255)"))
                    conn.commit()
                print("Added active_label column to report_collaboration_sessions table")

            if 'active_content_type' not in collaboration_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE report_collaboration_sessions ADD COLUMN active_content_type VARCHAR(32)"))
                    conn.commit()
                print("Added active_content_type column to report_collaboration_sessions table")

            if 'active_selection_start' not in collaboration_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE report_collaboration_sessions ADD COLUMN active_selection_start INTEGER"))
                    conn.commit()
                print("Added active_selection_start column to report_collaboration_sessions table")

            if 'active_selection_end' not in collaboration_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE report_collaboration_sessions ADD COLUMN active_selection_end INTEGER"))
                    conn.commit()
                print("Added active_selection_end column to report_collaboration_sessions table")

            if 'active_selection_text' not in collaboration_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE report_collaboration_sessions ADD COLUMN active_selection_text TEXT"))
                    conn.commit()
                print("Added active_selection_text column to report_collaboration_sessions table")
    except Exception as e:
        print(f"Database migration warning: {e}")
    finally:
        db.close()

    yield


app = FastAPI(title="Medical Report Annotation", lifespan=lifespan)
app.include_router(api_router, prefix="/api")

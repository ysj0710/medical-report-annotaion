from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.router import api_router
from .core.database import engine, Base
from .models.report import Report
from .models.annotation import Annotation
from .models.import_task import ImportTask
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
                conn.execute(text("ALTER TABLE reports ADD COLUMN pre_annotations JSONB"))
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
                conn.execute(text("ALTER TABLE reports ADD COLUMN reviewed_at TIMESTAMPTZ"))
                conn.commit()
            print("Added reviewed_at column to reports table")
    except Exception as e:
        print(f"Database migration warning: {e}")
    finally:
        db.close()

    yield


app = FastAPI(title="Medical Report Annotation", lifespan=lifespan)
app.include_router(api_router, prefix="/api")

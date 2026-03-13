from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.router import api_router
from .core.database import engine, Base
from .core.security import get_password_hash
from .models.user import User
from .models.report import Report
from .models.annotation import Annotation
from .models.import_task import ImportTask
from sqlalchemy.orm import Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建数据库表
    Base.metadata.create_all(bind=engine)

    # 数据库迁移：检查并添加缺失的列
    db = Session(engine)
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(engine)

        # 检查users表是否有employee_id列
        columns = [col['name'] for col in inspector.get_columns('users')]
        if 'employee_id' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN employee_id VARCHAR(32)"))
                conn.commit()
            print("Added employee_id column to users table")

        # 检查users表是否有can_view_all列
        if 'can_view_all' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN can_view_all BOOLEAN DEFAULT FALSE"))
                conn.commit()
            print("Added can_view_all column to users table")

        # 检查users表是否有view_all_requested列
        if 'view_all_requested' not in columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN view_all_requested BOOLEAN DEFAULT FALSE"))
                conn.commit()
            print("Added view_all_requested column to users table")

        # 检查reports表是否有pre_annotations列
        report_columns = [col['name'] for col in inspector.get_columns('reports')]
        if 'pre_annotations' not in report_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN pre_annotations JSONB"))
                conn.commit()
            print("Added pre_annotations column to reports table")
    except Exception as e:
        print(f"Database migration warning: {e}")
    finally:
        db.close()

    # 创建默认管理员账号
    db = Session(engine)
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                role="admin",
                enabled=True
            )
            db.add(admin)
            db.commit()
            print("Default admin user created: admin / admin123")
    finally:
        db.close()

    yield


app = FastAPI(title="Medical Report Annotation", lifespan=lifespan)
app.include_router(api_router, prefix="/api")

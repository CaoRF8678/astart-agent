from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

#给你所有数据表模型定一个统一 “父模板”，ORM 靠它自动识别、映射 Python 类 ↔ PostgreSQL 表。
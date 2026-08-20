# -*- coding: utf-8 -*-
import datetime
import json

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class DBEngine(object):
    def __init__(self, db_uri):
        """
        db_uri = f'mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4'

        """
        # SQLAlchemy 2.0 已移除 sessionmaker 的 autocommit=True 参数，
        # 改用普通 session 并在写操作后显式 commit()。
        engine = create_engine(db_uri)
        self.session = sessionmaker(bind=engine)()

    @staticmethod
    def value_decode(row: dict):
        """
        Try to decode value of table
        datetime.datetime-->string
        datetime.date-->string
        json str-->dict
        :param row:
        :return:
        """
        for k, v in row.items():
            if isinstance(v, datetime.datetime):
                row[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(v, datetime.date):
                row[k] = v.strftime("%Y-%m-%d")
            elif isinstance(v, str):
                try:
                    row[k] = json.loads(v)
                except ValueError:
                    pass

    @staticmethod
    def _row_to_dict(row):
        """Convert a SQLAlchemy Row to a dict.

        SQLAlchemy 2.0 的 Row 不再支持 dict(row)，需通过 _mapping 转换；
        这里兼容新旧两种版本。
        """
        if row is None:
            return None
        if hasattr(row, "_mapping"):
            return dict(row._mapping)
        return dict(row)

    def _fetch(self, query, size=-1, commit=True):
        query = query.strip()
        # SQLAlchemy 2.0 要求纯文本 SQL 必须用 text() 包装
        result = self.session.execute(text(query))
        if query.upper()[:6] == "SELECT":
            if size < 0:
                al = result.fetchall()
                al = [self._row_to_dict(el) for el in al]
                for el in al:
                    self.value_decode(el)
                return al or None
            elif size == 1:
                row = result.fetchone()
                if row is None:
                    return None
                on = self._row_to_dict(row)
                self.value_decode(on)
                return on or None
            else:
                mny = result.fetchmany(size)
                mny = [self._row_to_dict(el) for el in mny]
                for el in mny:
                    self.value_decode(el)
                return mny or None
        elif query.upper()[:6] in ("UPDATE", "DELETE", "INSERT"):
            # SQLAlchemy 2.0 不再自动提交写操作，需显式 commit
            if commit:
                self.session.commit()
            return {"rowcount": result.rowcount}

    def fetchone(self, query, commit=True):
        return self._fetch(query, size=1, commit=commit)

    def fetchmany(self, query, size, commit=True):
        return self._fetch(query=query, size=size, commit=commit)

    def fetchall(self, query, commit=True):
        return self._fetch(query=query, size=-1, commit=commit)

    def insert(self, query, commit=True):
        return self._fetch(query=query, commit=commit)

    def delete(self, query, commit=True):
        return self._fetch(query=query, commit=commit)

    def update(self, query, commit=True):
        return self._fetch(query=query, commit=commit)


if __name__ == "__main__":
    # db = DBEngine("mysql+pymysql://xxxxx:xxxxx@10.0.0.1:3306/dbname?charset=utf8mb4")
    db = DBEngine("sqlite:////Users/xxx/HttpRunner/examples/data/sqlite.db")
    print(db.fetchmany("""
    select* from student""", 5))
    print(db.fetchmany("select* from student", 5))

import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


class Db:

    def __init__(self):
        self.cnx = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "123456789"),
            database=os.getenv("DB_NAME", "wildeye_new"),
            port=int(os.getenv("DB_PORT", 3306))
        )
        self.cur = self.cnx.cursor(dictionary=True)



    def select(self, q, params=None):
        if params is not None:
            self.cur.execute(q, params)
        else:
            self.cur.execute(q)
        return self.cur.fetchall()

    def selectOne(self, q, params=None):
        if params is not None:
            self.cur.execute(q, params)
        else:
            self.cur.execute(q)
        return self.cur.fetchone()

    def insert(self, q, params=None):
        if params is not None:
            self.cur.execute(q, params)
        else:
            self.cur.execute(q)
        self.cnx.commit()
        return self.cur.lastrowid

    def update(self, q, params=None):
        if params is not None:
            self.cur.execute(q, params)
        else:
            self.cur.execute(q)
        self.cnx.commit()
        return self.cur.rowcount

    def delete(self, q, params=None):
        if params is not None:
            self.cur.execute(q, params)
        else:
            self.cur.execute(q)
        self.cnx.commit()
        return self.cur.rowcount



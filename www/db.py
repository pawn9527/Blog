# encoding: utf-8

import logging
import aiomysql

logging.basicConfig(level=logging.INFO)


# 创建线程池
async def create_pool(loop, **kwargs):
    logging.info("create databases connection pool ...")
    global __pool

    __pool = await  aiomysql.create_pool(
        host=kwargs.get("host", "localhost"),
        port=kwargs.get("port", 3306),
        user=kwargs["user"],
        password=kwargs["password"],
        db=kwargs["db"],
        charset=kwargs.get("charset", "utf8"),
        autocommit=kwargs.get("autocommit", True),
        maxsize=kwargs.get("maxsize", 10),
        minsize=kwargs.get("minsize", 1),
        loop=loop
    )


#  sql select 语句转化
async def select(sql, args, size=None):
    with await __pool as conn:
        cur = await conn.cursor(aiomysql.DictCursor)
        await cur.execute(sql.replace("?", '%s'), args or ())
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        await cur.close()
        logging.warning('rows returned: %s' % len(rs))
        return rs


# sql execute 执行语句
async def execute(sql, args, autocommit=True):
    logging.info(sql)
    with await __pool as conn:
        if not autocommit:
            await conn.begin()
        try:
            cur = await conn.cursor()
            await cur.execute(sql.replace("?", "%s"), args)
            affected = cur.rowcount
            await cur.close()
        except BaseException as e:
            if not autocommit:
                await conn.rolback()
            raise
        return affected

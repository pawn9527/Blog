#!/usr/bin/env python
# encoding: utf-8
from db import select, execute
import logging;

logging.basicConfig(level=logging.INFO)


def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    return ', '.join(L)


class Field:
    def __init__(self, name, colum_tpye, primary_key, default):
        self.name = name
        self.colum_tpye = colum_tpye
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s: %s>' % (self.__class__.__name__, self.colum_tpye, self.name)


class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)


class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, primary_key=False, default=False):
        super().__init__(name, 'boolean', primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)


class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


# 定义所有的 ModelMetaclass 的基类
class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        if name == "Model":
            return type.__new__(cls, name, bases, attrs)

        # 获取表明称
        table_name = attrs.get('__table__', None) or None
        logging.info(f"find Model: {name} ( {table_name}) ")
        mappings = dict()
        fields = []
        primaryKey = None
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info(f"find mapping: {k} ===> {v}")
                mappings[k] = v
                if v.primary_key:
                    # 找到主键
                    if primaryKey:
                        raise RuntimeError(f"Duplicate primary key for field: {k}")
                    primaryKey = k
                else:
                    fields.append(k)

        if not primaryKey:
            raise RuntimeError("primaryKey not find")

        for k in mappings.keys():
            attrs.pop(k)

        escaped_fields = list(map(lambda f: "%s" % f, fields))

        attrs["__mappings__"] = mappings  # 保存属性和列的关系
        attrs["__table__"] = table_name
        attrs['__primary_key__'] = primaryKey  # 主键名称
        attrs["__fields__"] = fields  # 除主键外的属性名
        # 构建默认的 SELECT UPDATE DELETE 语句
        attrs['__select__'] = "select `%s`, %s from `%s`" % (primaryKey, ','.join(escaped_fields), table_name)
        attrs['__insert__'] = "insert into `%s` (%s, `%s` ) value (%s)" % (
            table_name, ','.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = "update `%s` set `%s` where `%s` = ? " % (
            table_name, ','.join(map(lambda x: '`%s` = ?' % (mappings.get(x).name or x), fields)), primaryKey)
        attrs['__delete__'] = "delete from `%s` where '%s' = ?" % (table_name, primaryKey)
        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kwargs):
        super(Model, self).__init__(**kwargs)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"Model object not has attribute {key}")

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefult(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug(f"user default vlaues {key}:{value}")
                setattr(self, key, value)
        return value

    # find All
    @classmethod
    async def findAll(cls, where=None, args=None, **kwargs):
        # find objects by where
        sql = [cls.__select__]
        if where:
            sql.append("where")
            sql.append(where)
        if args is None:
            args = []

        orderBy = kwargs.get("order_by", None)
        if orderBy:
            sql.append("order by")
            sql.append(orderBy)
        limit = kwargs.get("limit", None)
        if limit:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append("?, ?")
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))

        rs = await select(' '.join(sql), args)

        return [cls(**r) for r in rs]

    # find
    @classmethod
    async def find(cls, key):
        # find object by primary_key
        rs = await select("%s where %s = ?" % (cls.__select__, cls.__primary_key__), [key], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    async def save(self):
        args = list(map(self.getValueOrDefult, self.__fields__))
        args.append(self.getValueOrDefult(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    # findNumber
    @classmethod
    async def findNumber(cls, selectFied, where=None, args=None):
        sql = ['select %s _num_ from `%s`' % (selectFied, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rw = await select(''.join(sql), args)
        if len(rw) == 0:
            return None
        return rw[0]['_num_']

    async def updata(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)

#!/usr/bin/env python
# encoding: utf8
import orm
import db
# from model import User, Blog, Comment
import asyncio
# loop = asyncio.get_event_loop()
#
# async def test():
#     await db.create_pool(loop=loop, user="root", password="root", db="awesome")
#
#     u = User(name='pawn', email="pawn9527@gmail.com", password="123456", image="about:blank")
#
#     await u.save()
#
# loop.run_until_complete(test())
import inspect

def sum(x, y = None):
    return x + y

for name, parameter in inspect.signature(sum).parameters.items():
    print(parameter.kind)
    print(parameter.default)
    print(f"name={name}")
    print(f"parameter={parameter}")

print("*"*30)

print(inspect.signature(sum))
print(inspect.Parameter.empty)

# encoding: utf-8


from datetime import datetime

from web import add_routes, add_static

from aiohttp import web

from db import create_pool
from model import User
from handlers import _COOKIE_NAME, cookie2user
# from jinja2 import environment, FileSystemLoader
import jinja2
import asyncio
import time
import json
import os
import logging

logging.basicConfig(level=logging.INFO)


def index(request):
    return web.Response(body=f"<h1>users</h1>")


def init_jinja2(app, **kwargs):
    logging.info("Init jinja2")
    options = dict(
        autoescape=kwargs.get("autoescape", True),
        block_start_string=kwargs.get("block_start_string", "{%"),
        block_end_string=kwargs.get("block_end_string", "%}"),
        variable_start_string=kwargs.get("variable_start_string", "{{"),
        variable_end_string=kwargs.get("variable_end_string", "}}"),
        auto_reload=kwargs.get("auto_reload", True)
    )
    path = kwargs.get("path", None)
    if not path:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info("set templates path : %s" % path)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(path), **options)
    filters = kwargs.get("filters", None)
    if filters:
        for name, f in filters.items():
            env.filters[name] = f
    app["__templating__"] = env


"""
middleware 是一种拦截器， 一个url 经过某个函数处理之前， 要经过 middleware 处理
一个middleware可以改变URL的输入、输出，甚至可以决定不继续处理而直接返回。middleware的用处就在于把通用的功能从每个URL处理函数中拿出来，集中放到一个地方
"""


# 把cookie解析出来，并将登录用户绑定到request对象上，这样，后续的URL处理函数就可以直接拿到登录用户
async def auth_factory(app, handler):
    async def auth(request):
        logging.info("check user: %s %s" % (request.method, request.path))
        request.__user__ = None
        logging.error("**" * 30)
        logging.error(request.cookies)
        cookie_str = request.cookies.get(_COOKIE_NAME)
        logging.error(f"cookie_str={cookie_str}")
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        if request.path.startswith('/message/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')

        return await handler(request)

    return auth


async def logger_factory(app, handler):
    async def logger(request):
        logging.info("Requet: %s  %s" % (request.method, request.path))
        return await handler(request)

    return logger


async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == "POST":
            if request.content_type.startwith("application/json"):
                request.__data__ = await request.json()
                logging.info('request json: %s ' % str(request.__data__))
            elif request.content_type.startwith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request from: %s' % (request.__data__))
        return await handler(request)
    return parse_data


async def response_factory(app, handler):
    async def response(request):
        logging.info("Response handler .... ")
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode("utf-8"))
            resp.content_type = "text/html; charset=utf-8"
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if not template:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False,
                                                    default=lambda a: a.__dict__).encode("utf-8"))
                resp.content_type = "application/json;charset=utf-8"
                return resp
            else:
                r['__user__'] = request.__user__
                resp = web.Response(body=app['__templating__'].get_template(
                    template).render(**r).encode('utf-8'))
                resp.content_type = "text/html; charset=utf-8"
                return resp

        if isinstance(r, int) and 600 > r >= 100:
            return web.Response(r)

        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and 600 > t >= 100:
                return web.Response(status=t, reason=str(m))

        # default
        resp = web.Response(body=str(r).encode("utf-8"))
        resp.content_type = 'text/plain; charset=utf-8'
        return resp

    return response


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u"一分钟前"
    if delta < 3600:
        return u"%s 分钟前" % (delta // 60)
    if delta < 86400:
        return u"%s 小时前" % (delta // 3600)
    if delta < 604800:
        return u"%s 天之前" % (delta // 86400)

    dt = datetime.fromtimestamp(t)

    return u"%s年%s月%s日" % (dt.year, dt.month, dt.day)


async def init(loop):
    # 创建 mysql 链接池
    database_cofig = {
        'host': "localhost",
        'prot': 3306,
        'user': 'root',
        'password': 'root',
        'db': 'awesome'
    }
    await create_pool(loop, **database_cofig)

    # 创建 web app
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory, auth_factory
    ])
    # 初始化 jinja2
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    # 添加路由 自动扫描  handlers 模块的自动注册
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info("server started at http://127.0.0.1:9000 ...")
    return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

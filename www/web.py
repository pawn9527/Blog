#!/usr/bin/env python
# -*- coding: utf-8 -*-
import functools
import asyncio
import inspect
from urllib import parse
import os
from aiohttp import web
from apis import APIError
import logging

logging.basicConfig(level=logging.INFO)


def get(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__method__ = "GET"
        wrapper.__route__ = path
        return wrapper

    return decorator


def post(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.__method__ = "POST"
        wrapper.__route__ = path
        return wrapper

    return decorator


def get_required_kwargs(func):
    args = []
    params = inspect.signature(func).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)


def get_named_kwargs(func):
    args = []
    params = inspect.signature(func).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)


def has_named_kwargs(func):
    params = inspect.signature(func).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True


def has_var_kwargs(func):
    params = inspect.signature(func).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True


def has_request_arg(func):
    sig = inspect.signature(func)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == "request":
            found = True
            continue
        if found and (
                param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.empty and param.kind != inspect.Parameter.VAR_KEYWORD and param):
            raise ValueError(
                "request params must  be the last named parameter in function: %s %s" % (func.__name__, str(sig)))
    return found


def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info("add static %s ==> %s" % ('/static/', path))


# 添加 注册
def add_route(app, func):
    method = getattr(func, "__method__", None)
    path = getattr(func, "__route__", None)
    if not method or not path:
        raise ValueError('@get or @post not method in {str(func)}')
    if not asyncio.iscoroutinefunction(func) and not inspect.isgeneratorfunction(func):
        func = asyncio.coroutine(func)
    logging.info("add route %s %s ==>%s(%s)" % (
    method, path, func.__name__, ",".join(inspect.signature(func).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, func))


# 自动扫描注册
def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n + 1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, "__method__", None)
            path = getattr(fn, "__route__", None)
            if method and path:
                add_route(app, fn)


class RequestHandler:
    def __init__(self, app, func):
        self._app = app
        self._func = func
        self._has_var_kwargs = has_var_kwargs(func)
        self._has_request_arg = has_request_arg(func)
        self._has_named_kwargs = has_named_kwargs(func)
        self._named_kwargs = get_named_kwargs(func)
        self._required_kwargs = get_required_kwargs(func)

    async def __call__(self, request):
        kwargs = None
        if self._has_var_kwargs or self._has_request_arg or self._has_named_kwargs:
            if request.method == "POST":
                if not request.content_type:
                    # return web.HTTPBadRequest(text="Missing Content Type")
                    return web.HTTPBadRequest(text="Missing Content Type")
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text="JSON body must be Object")
                    kwargs = params
                elif ct.startswith("application/x-www-form-urlencoded") or ct.startswith('multipart/from-data'):
                    params = await request.post()
                    kwargs = dict(**params)
                else:
                    return web.HTTPBadRequest(text="Unspported Content Type %s" % request.content_type)
            if request.method == "GET":
                qs = request.query_string
                if qs:
                    kwargs = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kwargs[k] = v[0]
        if not kwargs:
            kwargs = dict(**request.match_info)
        else:
            if not self._has_var_kwargs and self._named_kwargs:
                copy = dict()
                for name in self._named_kwargs:
                    if name in kwargs:
                        copy[name] = kwargs[name]
                kwargs = copy
            # check name args
            for k, v in request.match_info.items():
                if k in kwargs:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kwargs[k] = v
        if self._has_request_arg:
            kwargs['request'] = request
        if self._required_kwargs:
            for name in self._required_kwargs:
                if name not in kwargs:
                    return web.HTTPBadRequest(text=f"Missing argument: {name}")
        logging.info('call with args: %s' % str(kwargs))
        try:
            r = await self._func(**kwargs)
            return r
        except APIError as e:
            return {
                "error": e.error,
                "data": e.data,
                "message": e.message
            }

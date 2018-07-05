#!/usr/bin/env python
# -*- coding: utf-8 -*-

from web import get, post
from model import User, Blog, next_id, Comment
import time
from apis import APIValueError, APIError, APIPermissionError, Page, APIResourceNotFoundError
from aiohttp import web
from config import configs
import markdown2
import logging

logging.basicConfig(level=logging.INFO)
import re
import hashlib
import json

_COOKIE_KEY = configs.session.secret
_COOKIE_NAME = 'awesession'


def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


def user2cookie(user, max_age):
    """
    Generate cookie str by user
    """
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
    l = [user.id, expires, hashlib.sha1(s.encode("utf-8")).hexdigest()]
    return '_'.join(l)


# 解密 cookie
async def cookie2user(cookie_str):
    logging.info(f"解密cookie_str: {cookie_str}")
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('_')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        user = await  User.find(uid)
        if int(expires) < time.time():
            return None
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.password = "******"
        return user

    except Exception as e:
        logging.exception(e)
        return None


_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


@get('/')
async def index(*, page="1"):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    page = Page(num, page_index)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))

    return {
        '__template__': 'blogs.html',
        'page': page,
        'blogs': blogs
    }



@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }


@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }


@get('/api/users')
def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    num = yield from User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = yield from User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.password = '******'
    return dict(page=p, users=users)


@post('/api/register')
async def api_register_user(*, email, name, password):
    """"
    用户注册
    """
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError("email")
    if not password or not _RE_SHA1.match(password):
        raise APIValueError("password")
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIValueError("register:failed', 'email', 'Email is already in use.")
    uid = next_id()
    sha1_password = '%s:%s' % (uid, password)
    user = User(id=uid, name=name.strip(), email=email,
                password=hashlib.sha1(sha1_password.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    r = web.Response()
    r.set_cookie(_COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '******'
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r


@get("/signout")
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(_COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out')
    return r


@get("/blog/{id}")
async def get_blog(id):
    blog = await Blog.find(id)
    comments = await Comment.findAll("blog_id=?", [id], order_by="create_time desc")
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }


@post('/api/authenticate')
async def authenticate(*, email, password):
    if not email:
        raise APIValueError('email', 'Invalid email')
    if not password:
        raise APIValueError('password', 'Invalid password')
    users = await User.findAll("email=?", [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist')
    user = users[0]
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(password.encode('utf-8'))
    if user.password != sha1.hexdigest():
        raise APIValueError('password', 'Invalid password')
    # authenticate ok , set cookie
    r = web.Response()
    r.set_cookie(_COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = "******"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r


def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError("Permission Error")


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


@get('/api/blogs')
async def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(item_count=num, page_index=page_index)
    if num == 0:
        return dict(page=p, blogs=())

    blogs = await Blog.findAll(order_by="create_time desc", limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)


@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    # check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name not empty')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary not empty')
    if not content or not content.strip():
        raise APIValueError('content', 'contant cannot be empty.')
    blog = Blog(
        user_id=request.__user__.id,
        user_name=request.__user__.name,
        user_image=request.__user__.image,
        name=name.strip(),
        summary=summary.strip(),
        content=content.strip()
    )
    await blog.save()
    return blog


@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog


@post('/api/blog/{id}')
async def api_update_blog(id, request, *, name, summary, content):
    check_admin(request)
    blog = await Blog.find(id)
    if not name or not name.strip():
        raise APIValueError('name', 'name not be empty. ')
    if not summary or not summary:
        raise APIValueError('summary', 'summary cannot be empty .')
    if not content or not content:
        raise APIValueError('content', 'content cannot be empty .')
    blog.name = name
    blog.summary = summary
    blog.content = content
    await blog.updata()
    return blog


@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):
    check_admin(request)
    blog = Blog.find(id)
    if not blog:
        raise APIResourceNotFoundError("Blog")
    await blog.remove()
    return dict(id=id)


@get('/api/comments')
async def api_commnets(*, page="1"):
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = await  Comment.findAll(order_by="create_time desc", limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)


@post('/api/blogs/{id}/comments')
async def api_create_comment(id, *, request, content):
    user = request.__user__
    if not user:
        raise APIPermissionError('Please signin first . ')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = await Blog.find(id)
    if not blog:
        raise APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image,
                      content=content.strip())
    await comment.save()
    return comment


@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
    check_admin(request)
    c = await Comment.find(id)
    if not c:
        raise APIResourceNotFoundError('Commnet')
    await c.remove()
    return dict(id=id)


@get('/manage/blogs')
def manage_blogs(*, page="1"):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }


@get('/manage/')
def manage():
    return 'redirect:/manage/comments'


@get('/manage/comments')
def manage_comments(*, page="1"):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }


@get('/manage/blogs')
def manage_blogs(*, page="1"):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }


@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }


@get('/manage/blog/edit')
def mange_edit_blog(*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/%s' % id
    }


@get('/manage/users')
def manage_users(*, page="1"):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page)
    }

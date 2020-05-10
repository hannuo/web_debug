#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio

import markdown2

from aiohttp import web
from coroweb import get, post
from apis import Page, APIValueError, APIResourceNotFoundError
from models import User, Comment, Blog, Video, next_id
from config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def check_user(request):
    if request.__user__ is None:
        return False
    else:
        return True

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p		


def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)		

def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        ##0015471912220111be18497722f41c990471a69d4267503000-1548400507-98b97b8c031fccc33cb283c0f58d40e7c354984e
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

#01 主页
@get('/')
async def index(*, page='1',request):
    logging.info('@@ get /')
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    page = Page(num)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
    #qing04-1.2  返回一个dict，让response_factory处理.
    return {
        '__template__': 'blogs.html',
        'page': page,
        'blogs': blogs,
        '__user__': request.__user__
    }

#01 主页
@get('/videos')
async def play_videos(*, page='1',request):
    logging.info('@@ get /videos')
    page_index = get_page_index(page)
    #video = Video(poster='show.JPG',src='test.mp4')
    #await video.save()
    num = await Video.findNumber('count(id)')
    page = Page(num)
    if(check_user(request)):
        if num == 0:
            videos = []
        else:
            videos = await Video.findAll(limit=(page.offset, page.limit))
        #qing04-1.2  返回一个dict，让response_factory处理.
        return {
            '__template__': 'videos.html',
            'page': page,
            'videos': videos,
            '__user__': request.__user__
    }
    else:
        videos = await Video.findAll(limit=(page.offset, page.limit))
    #qing04-1.2  返回一个dict，让response_factory处理.
        check_admin(request)
        return {
            '__template__': 'videos.html',
            'page': page,
            'videos': videos,
            '__user__': request.__user__
    }

@get('/video')
async def PlayVideo(request):
    if(check_user(request)):
        return {
			'__template__': 'Play.html'
		}
    else:
        return {
        '__template__': 'signin.html'
    }
#02 REST 具象状态传输，返回所有用户信息
@get('/api/users')
async def api_get_users(*, page='1'):
    logging.info('@@ get /api/users')
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)

#03 注册用户界面
@get('/register')
def register():
    return {
        '__template__':'register.html' #submit 导向方法，$form.postJSON('/api/users',..) 这里用了vue，MVVC技术
    }

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

#03 注册用户信息创建
@post('/api/users')
async def api_register_user(*, email, name, passwd):
    logging.info('@@ post /api/users')
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r	
	
#04 用户登陆
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

#qqing02-1.2 kw:{'email': 'test', 'passwd': '576f2afcdca7238248dd1939e21d2bf0ee6432e8'}
@post('/api/authenticate')
async def authenticate(*, email, passwd):
    logging.info('@@ post /api/authenticate')
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    #qqing03-1 response deal。
    return r

#04 用户登出
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

#05 创建blog
@get('/manage/blogs/create')
def manage_create_blog(request):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs',
        '__user__': request.__user__
    }
#06 编辑blog	
@get('/manage/blogs/edit')
def manage_edit_blog(*, id,request):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/%s' % id,
        '__user__': request.__user__
    }

@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    logging.info('@@ post /api/blogs by /manage/blogs/create')
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    if(check_user(request)):
        blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
        await blog.save()
        return blog
    else:
        return {
            '__template__': 'signin.html'
        }
    
    

@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, name, summary, content):
    logging.info('@@ post /api/blogs/%s by /manage/blogs/edit' % id)
    check_admin(request)
    blog = await Blog.find(id)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog

#07 管理comments
@get('/manage/')
def manage(request):
    check_admin(request)
    return 'redirect:/manage/comments'

@get('/manage/comments')
def manage_comments(*, page='1',request):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page),
        '__user__': request.__user__
    }	

@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
    logging.info('@@ post /api/comments/%s/delete by /manage/comments'% id)
    check_admin(request)
    c = await Comment.find(id)
    if c is None:
        raise APIResourceNotFoundError('Comment')
    await c.remove()
    return dict(id=id)

#hqing-001 vue Ref. ,管理所有博客，可以编辑，删除博客
#08 管理blog
@get('/manage/blogs')
def manage_blogs(*, page='1',request):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page),
        '__user__': request.__user__
    }

#location.assign('/manage/blogs/edit?id='

#hqing-011
#@@ post /api/blogs/0015471995382294708336351a0485b98fcad85b65ec52f000/delete by /manage/blogs
@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):
    logging.info('@@ post /api/blogs/%s/delete by /manage/blogs'% id)
    check_admin(request)
    blog = await Blog.find(id)
    await blog.remove()
    return dict(id=id)
	
#09 获取某个id comments
#href: '/blog/'+blog.id"
@get('/blog/{id}')
async def get_blog(id,request):
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments,
        '__user__': request.__user__
    }
#hqing-006 -01 _httpJSON: url:/api/blogs?page=1	
@get('/api/blogs')
async def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

@get('/manage/users')
def manage_users(*, page='1',request):
    return {
        '__template__': 'manage_users.html',
        'page_index': get_page_index(page),
        '__user__': request.__user__
    }

@get('/api/comments')
async def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)	

@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog

#qqing01:id positional_or_keyword request positional_or_keyword
#content keyword_only
# * 前面的为positional_or_keyword 后面的为keyword_only
@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first.')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = await Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    await comment.save()
    return comment	
	
@get('/blogs/user/have')
async def get_twe(*, page='1',request):
    logging.info('@@ get /blogs/user/have')
    if(not check_user(request)):
        return {
		    '__template__': 'signin.html'
		}
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    page = Page(num)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll('user_name=?',[request.__user__.name])
    #qing04-1.2  返回一个dict，让response_factory处理.
    return {
        '__template__': 'blogs.html',
        'blogs': blogs,
        '__user__': request.__user__
    }

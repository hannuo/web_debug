#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
async web application.
'''

import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static
from handlers import cookie2user, COOKIE_NAME

#qing04 - 1.1 预先准备一个HTML文档，这个HTML文档不是普通的HTML，而是嵌入了一些变量和指令，
#然后，根据我们传入的数据，替换后，得到最终的HTML，发送给用户
#
def init_jinja2(app, **kw):
	#log3
    logging.info('init jinja2...')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
	#log4
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
            logging.info('****fileters not none:%s' % filters.items())
    app['__templating__'] = env


async def logger_factory(app, handler):
    async def logger(request):
		#log10
		##1.request 包含哪些信息
        logging.info('***logger_facotry,Request: %s %s \n %s' % (request.method, request.path,request))
        # await asyncio.sleep(0.3)
        return (await handler(request))
    return logger


async def auth_factory(app, handler):
    async def auth(request):
        logging.info('**auth_factory,check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
		##2. url处理函数的__user__是这里来的，request  method path cookies
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        if request.path.startswith('/manage/') and (request.__user__ is None): #or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return (await handler(request))
    return auth

async def data_factory(app, handler):
    async def parse_data(request):
        logging.info('###data_factory,data handler...')
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                #qingqing02 request json:{'email': 'test', 'passwd': '576f2afcdca7238248dd1939e21d2bf0ee6432e8'}
                #$form.postJSON('/api/authenticate', data, function(err, result)
                request.__data__ = await request.json()
                logging.info('###request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('###request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data

async def response_factory(app, handler):
    async def response(request):
		#log11
        logging.info('##response_factory,Response handler...')
        #qingqing03 handler(request) just is async def authenticate(*, email, passwd):
        #wait handel
        #handler(request) 什么意思，三个地方都有。先后顺序呢？？这个是最后一步，过滤response
        r = await handler(request)
        logging.info('##handler(request):%s'% r)
		#qingqing 03 @post('/api/authenticate') 返回一个web.streamResponse
        if isinstance(r, web.StreamResponse):
            #qingqing03 ##handler(request):<Response OK not prepared>
            logging.info('##web.streamResponse.')
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            logging.info('##bytes.')
            return resp
        if isinstance(r, str):
            #Add01
            logging.info(str);
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            logging.info('##str')
            return resp
		#qingqing03 @get('/') 返回一个web.streamResponse
		#qing-04 - 1.3  处理r 
        if isinstance(r, dict):
            template = r.get('__template__')
			#qingqing03 @get('/api/comments') 返回一个json
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                logging.info('##__template__ application/json')
                return resp
            else:
				#qing-04 - 1.4  app['__templating__'] = env '__template__': 'blogs.html'
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                ##handler(request):{'__template__': 'blogs.html', ...
                logging.info('##__template__ text/html')
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            logging.info('##int')
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                logging.info('##tuple')
                return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        logging.info('##defautl:text/plain')
        return resp
    return response

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
	#qing02-1 创建一个全局的数据库连接池
    await orm.create_pool(loop=loop, user='www-data', password='www-data', db='awesome')
	#qing03-1 aiohttp web 
	#Application is a synonym for web-server.
	#Application contains a router instance and a list of callbacks that will be called during application finishing.
    #qing03-2 logger_factory, data_factory, auth_factory, response_factory
	app = web.Application(loop=loop, middlewares=[
        logger_factory, data_factory, auth_factory, response_factory
    ])
	#qing04-1 使用jinja2
    init_jinja2(app, filters=dict(datetime=datetime_filter))
	#qing03-1.1 add_routes 
    add_routes(app, 'handlers')
    add_static(app)
	#qing01-1.4 loop ref 
	#Create a TCP server (socket type SOCK_STREAM) listening on port of the host address.
	#protocol_factory must be a callable returning a protocol implementation.
	#app.make_handler() Creates HTTP protocol factory for handling requests.
    srv = await loop.create_server(app.make_handler(), '', 9000)
	#log9
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

#qing01-1 asyncio ref
#qing01-1.1 Get the current event loop. If there is no current event loop set in the current OS thread and 
# set_event_loop() has not yet been called, asyncio will create a new event loop and set it as 
# the current one.
loop = asyncio.get_event_loop()
#qing01-1.2 If the argument is a coroutine object it is implicitly scheduled to run as a asyncio.Task.
loop.run_until_complete(init(loop))
#qing01-1.3 Run the event loop until stop() is called.
loop.run_forever()


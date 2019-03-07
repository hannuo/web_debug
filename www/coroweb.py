#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

import asyncio, os, inspect, logging, functools

from urllib import parse

from aiohttp import web

from apis import APIError


#1.
# 要把一个函数映射为一个URL处理函数，我们先定义@get()
# 这样，一个函数通过@get()的装饰就附带了URL信息。
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

def get_required_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        logging.info('sig.parameters name:%s param:%s kind:%s'%(name,param,param.kind))
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

#2.
# RequestHandler是一个类，由于定义了__call__()方法，因此可以将其实例视为函数。
# RequestHandler 目的就是从URL函数中分析其需要接收的参数，从request中获取必要的参数，调用URL函数，
# 然后把结果转换为web.Response对象，这样，就完全符合aiohttp框架的要求
#qing03-1.3 
class RequestHandler(object):

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)
        logging.info('__init__ %s _named_kw_args:%s _required_kw_args:%s'%(fn,self._named_kw_args,self._required_kw_args))

    async def __call__(self, request):
        kw = None
        logging.info('********')
        logging.info('%s' % request)
        logging.info('********')
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
			##qing03-1.3 参数过滤转换
            if request.method == 'POST':
                logging.info('RequestHandler fn:%s   POST  content_type:%s'% (self._func,request.content_type))
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                    #qingqing02 kw:{'email': 'test', 'passwd': '576f2afcdca7238248dd1939e21d2bf0ee6432e8'}
                    logging.info('RequestHandler application/json kw:%s'% kw)
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                    logging.info('RequestHandler application/x-www-form-urlencoded kw:%s'% kw)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                logging.info('RequestHandler fn:%s   GET  content_type:%s'% (self._func,request.content_type))
                qs = request.query_string
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
                    logging.info('RequestHandler quert_string %s'% kw)
        if kw is None:
            kw = dict(**request.match_info)
            logging.info('RequestHandler kw is None match_info %s'% kw)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        #qingqing02 kw:{'email': 'test', 'passwd': '576f2afcdca7238248dd1939e21d2bf0ee6432e8'}
                        #这里过滤掉了 传过来的json和自身参数不匹配的参数值
                        copy[name] = kw[name]
                        logging.info('not has_var_kw_arg _name_kw_args has name:%s kw[name]:%s'%(name,kw[name]))
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                logging.info('match_info.items k:%s v:%s'%(k,v))
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:
            kw['request'] = request
        # check required kw:
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
		#log12
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
	#log8
    logging.info('add static %s => %s' % ('/static/', path))

#qing03-1.2 aiohttp add_route implemented by app.router.add_route('GET', '/', index) 
#3.
# 注册一个URL处理函数
def add_route(app, fn):
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)
	#log7
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))

#4.
# 把很多次add_route()注册的调用，变成自动扫描，自动把某个模块module_name的所有符合条件的函数注册了
def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
        #logging.info('*** add_routes:mod -- %s' % mod)
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            #logging.info('*** __method__ __route__ %s - %s' %(method,path)) 
            if method and path:
                add_route(app, fn)

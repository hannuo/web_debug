#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Default configurations.
'''

__author__ = 'Michael Liao'


#1.
# 由于Python本身语法简单，完全可以直接用Python源代码来实现配置，
# 而不需要再解析一个单独的.properties或者.yaml等配置文件。
# 默认的配置文件应该完全符合本地开发环境，这样，无需任何设置，就可以立刻启动服务器。


configs = {
    'debug': True,
    'db': {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'www',
        'password': 'www',
        'db': 'awesome'
    },
    'session': {
        'secret': 'Awesome'
    }
}

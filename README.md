# Release note: #

**2019-03-05 22:18**

1. 搞懂函数对象，参数过滤那块 

2. 搞懂一个处理request的大概顺序

	logger_factory

	data_factory

	auth_factory

上两个函数，已经传过来的请求，赋值request

	response_factory

  	await handler(调用真正的具有较好参数校正的route 函数)
	处理response数据，返回response

通过添加log，考虑各种参数类型（keyword_only等）搞懂问题1

通过 /signin 
输入用户名，密码 登陆
搞懂问题2 （设计post json数据 response等）

##2019-03-18##

注释标志

"#qing01" asyncio part

"#qing02" database pool

"#qing03" aiohttp web

"#qing04" template-jinja2

"#qqing01 route-param type filter "

"#qqing02 signin post json,authenticate-route-api,requesthanderl-func-object,data_factory

"#qqing03 response deal ,web-streamresponse or application json

"#hqing# manage all bolgs - you will list all and delete someone

add

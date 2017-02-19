# zigmo - Python web framework

README: 中文 | [English](https://github.com/leohowell/zigmo/blob/master/README-en.md)

zigmo框架实现参考Tornado框架，学习tornado并实现一个类似框架。


## 更新日志
 - 2017-02-19 添加coroutine实现(tornado_style模块)，使用`@coroutine`可以写出tornado以tornado中同步风格来写异步代码
 - 2017-02-17 添加ioloop实现(ioloop模块)
 - 2017-02-12 添加WSGI server实现(wsgi_server模块) 和 主框架实现(zigmo模块)
 
## 目标

1. 理解yield
2. 理解coroutine
3. 理解ioloop
4. 理解为什么要异步
5. 实现ioloop
6. 实现coroutine
7. 实现一个基于epoll的异步框架

## 模块
- `ioloop` - 基于`epoll`的ioloop简化实现
- `zigmo` - 主框架
- `wsgi_server` - WSGI协议web server的demo实现
- `tornado_style` - tornado中同步风格写异步代码的简化实现

## 环境
zigmo 需要 **Python 2.7** 以及支持 `epoll` 的Linux

## 感谢

- Tornado

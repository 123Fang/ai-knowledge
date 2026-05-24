"""
__init__.py 是 Python 的"包标记文件" —— 类比前端的 package.json / index.ts

当 Python 看到某个目录下有 __init__.py，它就知道这个目录是一个"包（package）"，
可以用 `from pipeline import xxx` 来导入里面的模块。

知识点：
- Python 的"模块" ≈ JS 的一个 .ts 文件（通过文件级作用域导出变量/函数）
- Python 的"包"   ≈ JS 的一个目录，用 __init__.py 代替 index.ts 的"入口"角色
"""
# ↑ 上面是三引号包裹的"文档字符串"，相当于 JSDoc 中的 /** ... */ 多行注释

# 这一行是单行注释，Python 用 # 开头，相当于 JS 的 //
# pipeline 模块

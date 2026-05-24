"""
scripts/ — pipeline/ 的别名入口

历史原因：早期教学材料里把代码目录叫 scripts/，后来规范化改名为 pipeline/。
本目录提供别名，让按 scripts/xxx.py 路径查找的代码也能工作。

所有真实实现在 pipeline/ 下，本目录下的文件都是薄包装（re-export）。
"""

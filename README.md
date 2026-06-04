# kaa-scheduler

`kaa-scheduler` 是一个 Windows 下的自动编排器，用来串起 UU 加速器和 `kaa`：

1. 启动并附着 UU
2. 自动进入 `学园偶像大师` 对应页面并开启加速
3. 启动 `kaa`
4. 等待 `kaa` 执行结束后关闭 UU 加速

## 最基本用法

运行环境：Windows + Python 3.9 及以上

先在仓库根目录安装：

```powershell
python -m pip install -e .
```

查看命令帮助：

```powershell
python -m kaa_scheduler --help
```

执行完整流程：

```powershell
python -m kaa_scheduler run
```

更完整的调试命令、环境前提、配置项、计划任务脚本、日志说明和常见问题见 [AGENTS.md](AGENTS.md)。

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

## kaa 路径说明

scheduler 默认启动的 kaa 路径如下：

- **可执行文件**：`D:\Programs\kaa-bootstrap-0.5.1\kaa.exe`
- **工作目录**：`D:\Programs\kaa-bootstrap-0.5.1`
- **进程名**：`kaa.exe`

这个路径在 `app/kaa_scheduler/config.py` 中写死为默认值。启动时 scheduler 会执行：

```powershell
kaa.exe --start-immidiately
```

如果你系统里有多个 kaa，可以通过环境变量覆盖默认值，而不需要改代码：

```powershell
$env:KAA_SCHEDULER_KAA_EXE = "D:\Programs\另一个kaa目录\kaa.exe"
$env:KAA_SCHEDULER_KAA_WORKDIR = "D:\Programs\另一个kaa目录"
python -m kaa_scheduler run
```

可用的覆盖环境变量：

| 环境变量 | 说明 |
| --- | --- |
| `KAA_SCHEDULER_KAA_EXE` | kaa 可执行文件完整路径 |
| `KAA_SCHEDULER_KAA_WORKDIR` | kaa 启动时的工作目录 |
| `KAA_SCHEDULER_KAA_PROCESS` | kaa 进程名（默认 `kaa.exe`） |

## 计划任务快速试跑

如果你想先测试一次“5 分钟后是否会自动执行”，可以先用一个临时时间创建任务。

先在 PowerShell 里算出 5 分钟后的时间：

```powershell
$testTime = (Get-Date).AddMinutes(5).ToString("HH:mm")
```

然后创建计划任务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_task_scheduler.ps1 -TaskName "kaa-scheduler-test" -StartTime $testTime
```

测试完成后删除这个临时任务：

```powershell
schtasks /Delete /TN "kaa-scheduler-test" /F
```

确认没问题后，再创建正式的每天 `06:00` 任务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_task_scheduler.ps1 -TaskName "kaa-scheduler-daily" -StartTime "06:00"
```

## 计划任务深夜失败（屏保导致）

如果在计划任务设置的时间点（例如凌晨）执行失败，日志显示 UU 窗口已恢复但 OCR 读不到任何内容，大概率是因为 **Windows 屏幕保护程序** 在长时间空闲后激活，导致 DWM 合成状态异常，窗口截图被遮挡或变为空白。

### 检查

- 如果执行日志出现类似 `OCR current UU page title region: <none>` 或随机数字（如 `10`），而 UU 进程本身在运行，说明窗口已恢复但内容无法被截图识别。
- 手动测试时（刚关闭显示器立即运行）正常，但放置一晚后失败，更说明是时间触发的状态变化。

### 修复（关闭屏幕保护程序）

在 PowerShell 中执行以下命令：

```powershell
# 关闭屏幕保护程序
reg add "HKEY_CURRENT_USER\Control Panel\Desktop" /v ScreenSaveActive /t REG_SZ /d 0 /f

# 刷新设置使其立即生效
rundll32.exe user32.dll,UpdatePerUserSystemParameters
```

关闭后，Windows 在长时间空闲时不会进入屏保状态，凌晨任务可以正常截图和 OCR 识别。

### 注意

- 手动按显示器物理按钮关闭显示器**不会**触发这个问题（测试已验证）。
- 问题仅在 Windows 屏保程序自动启动后出现。
- 如果关闭屏保后仍有失败，请检查 `AGENTS.md` 中的其他常见问题。

更完整的调试命令、环境前提、配置项、计划任务脚本、日志说明和常见问题见 [AGENTS.md](AGENTS.md)。

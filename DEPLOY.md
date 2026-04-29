# 发布到 lldd-linux 说明

> 本文档记录如何从本机（Mac）通过 Git 一键发布代码到远程 Linux 服务器（lldd-linux）。

---

## 一、发布链路

```
本机 Mac 修改代码
    ↓ git push lldd-linux main
远程 Linux 裸仓库 (/home/lldd/xiaozhi-server.git)
    ↓ post-receive Hook 自动触发
检出代码 → rsync 同步到 /home/lldd/xiaozhi-server/
    ↓ 自动重启服务
停止 Docker → 启动 Python 源码服务 (python app.py)
```

---

## 二、已完成的配置

### 远程 Linux (lldd-linux)
- 已创建 Git 裸仓库：`/home/lldd/xiaozhi-server.git`
- 已配置 `post-receive` Hook：推送后自动部署并重启服务
- 已安装 Python 3.10、ffmpeg、libopus0 等系统依赖
- 运行目录：`/home/lldd/xiaozhi-server/`

### 本机 Mac
- 已在本地仓库添加 remote：
  ```bash
  git remote add lldd-linux lldd-linux:/home/lldd/xiaozhi-server.git
  ```

---

## 三、发布步骤（日常操作）

```bash
# 1. 改代码
vim main/xiaozhi-server/core/connection.py

# 2. 提交
# 注意：commit 到本地，不要 push 到 origin（除非你想同步到 GitHub）
git add .
git commit -m "fix: 修改了 xxx"

# 3. 一键发布到 lldd-linux
git push lldd-linux main
```

推送后，远程会自动：
1. 检出最新代码
2. 用 `rsync` 把 `main/xiaozhi-server/` 同步到运行目录
3. **保留** `data/`、`models/`、`venv/`、`tmp/` 不被覆盖
4. 停止旧的 Docker 容器 / Python 进程
5. 启动新的 Python 服务

---

## 四、查看远程状态

### 看服务是否启动
```bash
ssh lldd-linux "ps aux | grep 'python app.py' | grep -v grep"
```

### 看运行日志
```bash
ssh lldd-linux "tail -f /tmp/xiaozhi-server.log"
```

### 看 pip 安装进度（首次部署时）
```bash
ssh lldd-linux "tail -f /tmp/pip-install.log"
```

---

## 五、注意事项

1. **Python 依赖首次安装较慢**  
   远程正在后台安装 `requirements.txt`（torch 约 755MB）。安装完成前服务无法启动。

2. **`.config.yaml` 不会被覆盖**  
   Hook 中 `data/` 被排除在同步范围外，远程配置安全。

3. **如需回滚**  
   在 Mac 上 `git revert` 或 `git reset` 后，重新 `git push lldd-linux main --force` 即可。

4. **Hook 文件位置（如需修改）**  
   `lldd-linux:/home/lldd/xiaozhi-server.git/hooks/post-receive`

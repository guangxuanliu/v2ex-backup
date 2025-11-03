# V2EX 备份工具

一个用于备份 V2EX 个人数据的 Python 工具，支持备份收藏、发帖和回复内容，并导出为多种格式。

## 功能特性

- 备份我的收藏
- 备份我的发帖
- 备份我的回复

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Cookie

1. 在浏览器中登录 V2EX
2. 按 `F12` 打开开发者工具
3. 进入 **应用** → **存储** → **Cookies** → `https://v2ex.com`
4. 复制所有 Cookie 内容并保存到 `cookie.txt` 文件

### 3. 运行程序

```bash
python main.py
```

## 输出文件

所有备份文件保存在 `backups/` 目录下，每次备份会生成三种格式的文件：

### 文件命名规则

- **收藏备份**：`favorites_{timestamp}.{format}`
- **发帖备份**：`my_topics_{username}_{timestamp}.{format}`
- **回复备份**：`my_replies_{username}_{timestamp}.{format}`

### 输出格式

1. JSON 格式（`.json`）
2. TXT 格式（`.txt`）
3. Markdown 格式（`.md`）



## 使用示例

### 完整备份流程

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 准备 Cookie（将 Cookie 保存到 cookie.txt）

# 3. 运行备份
python main.py
```

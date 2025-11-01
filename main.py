#!/usr/bin/env python3
"""
V2EX 收藏备份工具 - 增强版
新增功能：
- 从文件读取 Cookie
- 提取更多信息（点赞数、精确时间）
- 去重功能
- 导出 Markdown 格式
- 备份对比
- 统计分析
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import time
import re

# 配置
BASE_URL = "https://v2ex.com"
COOKIE_FILE = "cookie.txt"
BACKUP_DIR = "backups"

def load_cookie(cookie_file=COOKIE_FILE):
    """从文件加载 Cookie，支持多种格式"""
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print(f"✗ {cookie_file} 文件为空")
                return None
            
            # 检测 Cookie 格式
            # 格式1: Chrome 导出的表格格式 (制表符分隔)
            if '\t' in content and ('v2ex.com' in content or 'www.v2ex.com' in content):
                print("检测到 Chrome 导出格式，正在转换...")
                cookies = {}
                lines = content.split('\n')
                
                for line in lines:
                    if not line.strip():
                        continue
                    
                    # 分割每行 (格式: name \t value \t domain \t ...)
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        value = parts[1].strip()
                        
                        # 移除值两边的引号（如果有）
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        
                        # 保存 cookie
                        if name and value:
                            cookies[name] = value
                
                if not cookies:
                    print(f"✗ 未能从 Chrome 格式中提取有效的 Cookie")
                    return None
                
                # 转换为 HTTP Cookie 格式
                cookie_string = '; '.join([f"{k}={v}" for k, v in cookies.items()])
                print(f"✓ 成功转换 {len(cookies)} 个 Cookie 条目")
                return cookie_string
            
            # 格式2: 标准 HTTP Cookie 格式 (key=value; key=value)
            elif '=' in content:
                print("检测到标准 Cookie 格式")
                return content
            
            else:
                print(f"✗ 无法识别的 Cookie 格式")
                print(f"提示: 支持的格式:")
                print(f"  1. Chrome 导出的表格格式 (复制 Cookie 表格)")
                print(f"  2. 标准 HTTP Cookie 格式 (key=value; key=value)")
                return None
                
    except FileNotFoundError:
        print(f"✗ 未找到 {cookie_file} 文件")
        print(f"提示: 请创建 {cookie_file} 文件并将你的 Cookie 粘贴进去")
        return None
    except Exception as e:
        print(f"✗ 读取 Cookie 文件时出错: {e}")
        return None

def get_favorites_page(cookie, page=1):
    """获取收藏页面的 HTML"""
    url = f"{BASE_URL}/my/topics"
    if page > 1:
        url += f"?p={page}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookie,
        "Referer": BASE_URL,
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"✗ 获取第 {page} 页失败, 状态码: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求出错: {e}")
        return None

def parse_topic_from_item(item):
    """从收藏项中解析主题信息"""
    try:
        topic = {}
        
        # 获取主题链接和标题
        title_element = item.find('span', class_='item_title')
        if title_element:
            link = title_element.find('a')
            if link:
                topic['title'] = link.text.strip()
                topic['url'] = BASE_URL + link.get('href', '')
                # 从 URL 中提取 topic_id
                match = re.search(r'/t/(\d+)', topic['url'])
                if match:
                    topic['id'] = match.group(1)
        
        # 获取节点信息
        node_element = item.find('a', class_='node')
        if node_element:
            topic['node'] = node_element.text.strip()
            topic['node_url'] = BASE_URL + node_element.get('href', '')
        
        # 获取作者信息
        author_element = item.find('strong')
        if author_element:
            author_link = author_element.find('a')
            if author_link:
                topic['author'] = author_link.text.strip()
                topic['author_url'] = BASE_URL + author_link.get('href', '')
        
        # 获取用户头像
        avatar_element = item.find('img', class_='avatar')
        if avatar_element:
            topic['author_avatar'] = avatar_element.get('src', '')
        
        # 获取回复数
        count_element = item.find('a', class_='count_livid')
        if not count_element:
            count_element = item.find('a', class_='count_orange')
        if count_element:
            topic['replies'] = int(count_element.text.strip())
        else:
            topic['replies'] = 0
        
        # 获取点赞数
        votes_element = item.find('div', class_='votes')
        if votes_element:
            votes_text = votes_element.get_text(strip=True)
            # 提取数字
            votes_match = re.search(r'(\d+)', votes_text)
            if votes_match:
                topic['votes'] = int(votes_match.group(1))
            else:
                topic['votes'] = 0
        else:
            topic['votes'] = 0
        
        # 获取精确发布时间
        topic_info = item.find('span', class_='topic_info')
        if topic_info:
            # 查找带 title 属性的 span（包含精确时间）
            time_span = topic_info.find('span', title=True)
            if time_span:
                topic['created_time'] = time_span.get('title', '')
                topic['created_time_relative'] = time_span.get_text(strip=True)
            
            # 获取最后回复者
            last_reply_text = topic_info.get_text()
            if '最后回复来自' in last_reply_text:
                last_reply_match = re.search(r'最后回复来自.*?<strong><a[^>]*>([^<]+)</a>', str(topic_info))
                if last_reply_match:
                    topic['last_reply_user'] = last_reply_match.group(1)
        
        # 记录收藏时间（当前时间）
        topic['favorited_at'] = datetime.now().isoformat()
        
        return topic
        
    except Exception as e:
        print(f"✗ 解析主题时出错: {e}")
        return None

def parse_favorites_page(html, current_page_num):
    """解析收藏页面,提取所有主题信息"""
    soup = BeautifulSoup(html, 'html.parser')
    
    # 查找所有收藏的主题
    items = soup.find_all('div', class_='cell item')
    
    topics = []
    for item in items:
        topic = parse_topic_from_item(item)
        if topic:
            topics.append(topic)
    
    # 检查是否有下一页
    has_next = False
    all_links = soup.find_all('a')
    page_numbers = set()
    
    for link in all_links:
        href = link.get('href', '')
        if '/my/topics?p=' in href:
            try:
                page_num = int(href.split('p=')[1].split('&')[0].split('#')[0])
                if 1 <= page_num <= 1000:
                    page_numbers.add(page_num)
            except:
                pass
    
    if page_numbers and max(page_numbers) > current_page_num:
        has_next = True
    
    return topics, has_next

def remove_duplicates(topics):
    """根据 topic ID 去重"""
    seen = set()
    unique_topics = []
    
    for topic in topics:
        topic_id = topic.get('id')
        if topic_id and topic_id not in seen:
            seen.add(topic_id)
            unique_topics.append(topic)
    
    return unique_topics

def export_to_markdown(topics, filename):
    """导出为 Markdown 格式"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# V2EX 收藏备份\n\n")
        f.write(f"**备份时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**总计**: {len(topics)} 个主题\n\n")
        
        # 写入所有主题
        f.write("## 📚 所有收藏\n\n")
        
        # 按节点分组
        topics_by_node = {}
        for topic in topics:
            node = topic.get('node', '未分类')
            if node not in topics_by_node:
                topics_by_node[node] = []
            topics_by_node[node].append(topic)
        
        for node, node_topics in sorted(topics_by_node.items()):
            f.write(f"### {node} ({len(node_topics)})\n\n")
            for topic in node_topics:
                f.write(f"- **[{topic['title']}]({topic['url']})**\n")
                f.write(f"  - 作者: [{topic.get('author', 'N/A')}]({topic.get('author_url', '#')})\n")
                f.write(f"  - 回复: {topic.get('replies', 0)} | 点赞: {topic.get('votes', 0)}\n")
                if topic.get('created_time'):
                    f.write(f"  - 发布时间: {topic['created_time']}\n")
                f.write("\n")

def backup_all_favorites(output_dir=BACKUP_DIR):
    """备份所有收藏的主题 - 增强版"""
    print("\n" + "=" * 60)
    print("V2EX 收藏备份工具 - 增强版")
    print("=" * 60)
    
    # 加载 Cookie
    cookie = load_cookie()
    if not cookie:
        return None
    
    # 创建备份目录
    os.makedirs(output_dir, exist_ok=True)
    
    all_topics = []
    page = 1
    max_pages = 1000
    
    while page <= max_pages:
        print(f"\n正在获取第 {page} 页...")
        
        html = get_favorites_page(cookie, page)
        if not html:
            print(f"✗ 无法获取第 {page} 页内容")
            break
        
        # 检查是否登录
        if '登录' in html and 'Google 账号登录' in html:
            print("\n✗ Cookie 可能已失效,请重新获取 Cookie!")
            return None
        
        topics, has_next = parse_favorites_page(html, page)
        
        if not topics:
            print(f"第 {page} 页没有找到收藏内容,停止获取")
            break
        
        all_topics.extend(topics)
        print(f"✓ 第 {page} 页: 获取到 {len(topics)} 个收藏 (累计: {len(all_topics)})")
        
        # 显示前几个主题
        for i, topic in enumerate(topics[:3], 1):
            votes_info = f"👍 {topic.get('votes', 0)}" if topic.get('votes', 0) > 0 else ""
            print(f"  {i}. {topic.get('title', 'N/A')} [{topic.get('replies', 0)} 回复] {votes_info}")
        
        if not has_next:
            print(f"\n✓ 已到达最后一页 (第 {page} 页)")
            break
        
        print(f"  → 检测到有下一页,继续...")
        page += 1
        time.sleep(1)
    
    if all_topics:
        # 去重
        original_count = len(all_topics)
        all_topics = remove_duplicates(all_topics)
        if original_count > len(all_topics):
            print(f"\n✓ 去重: 移除了 {original_count - len(all_topics)} 个重复项")
        
        # 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON 格式
        json_filename = f"{output_dir}/favorites_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(all_topics, f, indent=2, ensure_ascii=False)
        
        # TXT 格式（简化版）
        txt_filename = f"{output_dir}/favorites_{timestamp}.txt"
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write(f"V2EX 收藏备份\n")
            f.write(f"备份时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总计: {len(all_topics)} 个主题\n")
            f.write("=" * 60 + "\n\n")
            
            for i, topic in enumerate(all_topics, 1):
                f.write(f"{i}. {topic.get('title', 'N/A')}\n")
                f.write(f"   节点: {topic.get('node', 'N/A')} | 作者: {topic.get('author', 'N/A')}\n")
                f.write(f"   回复: {topic.get('replies', 0)} | 点赞: {topic.get('votes', 0)}\n")
                f.write(f"   链接: {topic.get('url', 'N/A')}\n")
                if topic.get('created_time'):
                    f.write(f"   发布: {topic['created_time']}\n")
                f.write("\n")
        
        # Markdown 格式
        md_filename = f"{output_dir}/favorites_{timestamp}.md"
        export_to_markdown(all_topics, md_filename)
        
        print("\n" + "=" * 60)
        print("✓ 备份完成!")
        print(f"  总共收藏: {len(all_topics)} 个主题")
        print(f"\n文件已保存:")
        print(f"  📄 JSON: {json_filename}")
        print(f"  📄 TXT:  {txt_filename}")
        print(f"  📄 MD:   {md_filename}")
        print("=" * 60)
        
        return all_topics
    
    return None

def test_cookie(cookie):
    """测试 Cookie 是否有效"""
    print("正在测试 Cookie...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie,
    }
    
    try:
        response = requests.get(f"{BASE_URL}/my/topics", headers=headers, timeout=10)
        
        if response.status_code == 200:
            if '登录' in response.text and 'Google 账号登录' in response.text:
                print("✗ Cookie 无效或已过期")
                return False
            else:
                print("✓ Cookie 验证成功!")
                return True
        else:
            print(f"✗ 请求失败, 状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ 测试出错: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("V2EX 收藏备份工具")
    print("=" * 60)
    
    # 加载 Cookie
    cookie = load_cookie()
    if not cookie:
        print("\n获取 Cookie 的步骤:")
        print("1. 在浏览器中登录 V2EX (https://v2ex.com)")
        print("2. 按 F12 打开开发者工具")
        print("3. 进入 Network(网络) 标签")
        print("4. 刷新页面,点击任意请求")
        print("5. 在 Headers 中找到 'Cookie' 字段并复制完整值")
        print(f"6. 将 Cookie 值保存到 {COOKIE_FILE} 文件中")
        exit(1)
    
    # 测试 Cookie
    if not test_cookie(cookie):
        print("\n请检查你的 Cookie 是否正确")
        exit(1)
    
    # 开始备份
    favorites = backup_all_favorites()
    
    if favorites:
        print(f"\n收藏主题示例 (前 5 个):\n")
        for i, topic in enumerate(favorites[:5], 1):
            print(f"{i}. {topic.get('title', 'N/A')}")
            print(f"   回复: {topic.get('replies', 0)} | 点赞: {topic.get('votes', 0)}")
            print(f"   {topic.get('url', 'N/A')}\n")

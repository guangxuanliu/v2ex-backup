#!/usr/bin/env python3
"""
V2EX 备份工具
功能：
1. 备份我的收藏 (/my/topics)
2. 备份我的发帖 (/member/{username}/topics)
3. 备份我的回复 (/member/{username}/replies)
4. 从首页自动获取用户名
5. 从文件读取 Cookie (支持Chrome导出格式)
6. 提取详细信息（点赞数、精确时间等）
7. 去重功能
8. 导出多种格式（JSON、TXT、Markdown）
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
            
            # 格式2: 标准 HTTP Cookie 格式
            elif '=' in content:
                print("检测到标准 Cookie 格式")
                return content
            
            else:
                print(f"✗ 无法识别的 Cookie 格式")
                return None
                
    except FileNotFoundError:
        print(f"✗ 未找到 {cookie_file} 文件")
        return None
    except Exception as e:
        print(f"✗ 读取 Cookie 文件时出错: {e}")
        return None

def get_username_from_homepage(cookie):
    """从首页获取当前登录的用户名"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie,
    }
    
    try:
        response = requests.get(BASE_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找用户名链接 (格式: <a href="/member/username" class="top">)
            user_link = soup.find('a', class_='top', href=re.compile(r'/member/'))
            if user_link:
                username = user_link.get('href').replace('/member/', '')
                print(f"✓ 检测到用户名: {username}")
                return username
            else:
                print("✗ 无法从首页获取用户名")
                return None
        else:
            print(f"✗ 获取首页失败，状态码: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"✗ 获取用户名时出错: {e}")
        return None

def get_page(cookie, url):
    """获取页面 HTML"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie,
        "Referer": BASE_URL,
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            print(f"✗ 获取页面失败, 状态码: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求出错: {e}")
        return None

def parse_topic_from_item(item):
    """从主题条目中解析信息"""
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
            time_span = topic_info.find('span', title=True)
            if time_span:
                topic['created_time'] = time_span.get('title', '')
                topic['created_time_relative'] = time_span.get_text(strip=True)
            
            # 获取最后回复者
            if '最后回复来自' in topic_info.get_text():
                last_reply_match = re.search(r'最后回复来自.*?<strong><a[^>]*>([^<]+)</a>', str(topic_info))
                if last_reply_match:
                    topic['last_reply_user'] = last_reply_match.group(1)
        
        return topic
        
    except Exception as e:
        print(f"✗ 解析主题时出错: {e}")
        return None

def parse_page(html, page_type, current_page_num):
    """
    解析页面，提取所有主题信息
    page_type: 'favorites' 或 'topics'
    """
    soup = BeautifulSoup(html, 'html.parser')
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
    
    # 匹配分页链接：可能是完整路径或相对路径
    # 完整: /my/topics?p=2 或 /member/user/topics?p=2
    # 相对: ?p=2
    for link in all_links:
        href = link.get('href', '')
        if '?p=' in href or 'topics?p=' in href:
            try:
                # 提取页码
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

def save_topics(topics, filename_prefix, output_dir=BACKUP_DIR):
    """保存主题到文件"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON 格式
    json_filename = f"{output_dir}/{filename_prefix}_{timestamp}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(topics, f, indent=2, ensure_ascii=False)
    
    # TXT 格式
    txt_filename = f"{output_dir}/{filename_prefix}_{timestamp}.txt"
    with open(txt_filename, 'w', encoding='utf-8') as f:
        f.write(f"V2EX 备份\n")
        f.write(f"备份时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总计: {len(topics)} 个主题\n")
        f.write("=" * 60 + "\n\n")
        
        for i, topic in enumerate(topics, 1):
            f.write(f"{i}. {topic.get('title', 'N/A')}\n")
            f.write(f"   节点: {topic.get('node', 'N/A')} | 作者: {topic.get('author', 'N/A')}\n")
            f.write(f"   回复: {topic.get('replies', 0)} | 点赞: {topic.get('votes', 0)}\n")
            f.write(f"   链接: {topic.get('url', 'N/A')}\n")
            if topic.get('created_time'):
                f.write(f"   发布: {topic['created_time']}\n")
            f.write("\n")
    
    # Markdown 格式
    md_filename = f"{output_dir}/{filename_prefix}_{timestamp}.md"
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write(f"# V2EX 备份\n\n")
        f.write(f"**备份时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**总计**: {len(topics)} 个主题\n\n")
        f.write("## 📚 所有主题\n\n")
        
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
    
    return json_filename, txt_filename, md_filename

def backup_favorites(cookie, output_dir=BACKUP_DIR):
    """备份我的收藏"""
    print("\n" + "=" * 60)
    print("开始备份: 我的收藏")
    print("=" * 60)
    
    all_topics = []
    page = 1
    max_pages = 1000
    
    while page <= max_pages:
        print(f"\n正在获取第 {page} 页...")
        
        url = f"{BASE_URL}/my/topics"
        if page > 1:
            url += f"?p={page}"
        
        html = get_page(cookie, url)
        if not html:
            break
        
        # 检查是否登录
        if '登录' in html and 'Google 账号登录' in html:
            print("\n✗ Cookie 可能已失效!")
            return None
        
        topics, has_next = parse_page(html, 'favorites', page)
        
        if not topics:
            print(f"第 {page} 页没有找到内容")
            break
        
        all_topics.extend(topics)
        print(f"✓ 第 {page} 页: 获取到 {len(topics)} 个主题 (累计: {len(all_topics)})")
        
        # 显示前3个
        for i, topic in enumerate(topics[:3], 1):
            votes_info = f"👍 {topic.get('votes', 0)}" if topic.get('votes', 0) > 0 else ""
            print(f"  {i}. {topic.get('title', 'N/A')} [{topic.get('replies', 0)} 回复] {votes_info}")
        
        if not has_next:
            print(f"\n✓ 已到达最后一页 (第 {page} 页)")
            break
        
        page += 1
        time.sleep(1)
    
    if all_topics:
        # 去重
        original_count = len(all_topics)
        all_topics = remove_duplicates(all_topics)
        if original_count > len(all_topics):
            print(f"\n✓ 去重: 移除了 {original_count - len(all_topics)} 个重复项")
        
        # 保存
        json_file, txt_file, md_file = save_topics(all_topics, 'favorites', output_dir)
        
        print("\n" + "=" * 60)
        print("✓ 收藏备份完成!")
        print(f"  总共收藏: {len(all_topics)} 个主题")
        print(f"\n文件已保存:")
        print(f"  📄 JSON: {json_file}")
        print(f"  📄 TXT:  {txt_file}")
        print(f"  📄 MD:   {md_file}")
        print("=" * 60)
        
        return all_topics
    
    return None

def backup_user_topics(cookie, username, output_dir=BACKUP_DIR):
    """备份我的发帖"""
    print("\n" + "=" * 60)
    print(f"开始备份: 我的发帖 (用户: {username})")
    print("=" * 60)
    
    all_topics = []
    page = 1
    max_pages = 1000
    
    while page <= max_pages:
        print(f"\n正在获取第 {page} 页...")
        
        url = f"{BASE_URL}/member/{username}/topics"
        if page > 1:
            url += f"?p={page}"
        
        html = get_page(cookie, url)
        if not html:
            break
        
        topics, has_next = parse_page(html, 'topics', page)
        
        if not topics:
            print(f"第 {page} 页没有找到内容")
            break
        
        all_topics.extend(topics)
        print(f"✓ 第 {page} 页: 获取到 {len(topics)} 个主题 (累计: {len(all_topics)})")
        
        # 显示前3个
        for i, topic in enumerate(topics[:3], 1):
            votes_info = f"👍 {topic.get('votes', 0)}" if topic.get('votes', 0) > 0 else ""
            print(f"  {i}. {topic.get('title', 'N/A')} [{topic.get('replies', 0)} 回复] {votes_info}")
        
        if not has_next:
            print(f"\n✓ 已到达最后一页 (第 {page} 页)")
            break
        
        page += 1
        time.sleep(1)
    
    if all_topics:
        # 去重
        original_count = len(all_topics)
        all_topics = remove_duplicates(all_topics)
        if original_count > len(all_topics):
            print(f"\n✓ 去重: 移除了 {original_count - len(all_topics)} 个重复项")
        
        # 保存
        json_file, txt_file, md_file = save_topics(all_topics, f'my_topics_{username}', output_dir)
        
        print("\n" + "=" * 60)
        print("✓ 发帖备份完成!")
        print(f"  总共发帖: {len(all_topics)} 个主题")
        print(f"\n文件已保存:")
        print(f"  📄 JSON: {json_file}")
        print(f"  📄 TXT:  {txt_file}")
        print(f"  📄 MD:   {md_file}")
        print("=" * 60)
        
        return all_topics
    
    return None

def parse_reply_item(dock_area, inner):
    """解析单个回复条目"""
    try:
        reply = {}
        
        # 从 dock_area 提取信息
        dock_text = dock_area.get_text()
        
        # 提取时间
        time_span = dock_area.find('span', class_='fade')
        if time_span:
            reply['time'] = time_span.get_text(strip=True)
        
        # 提取主题信息 (回复了 XXX 创建的主题 › 节点 › 主题标题)
        links = dock_area.find_all('a')
        for i, link in enumerate(links):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # 主题作者
            if '/member/' in href and i == 0:
                reply['topic_author'] = text
            # 节点
            elif '/go/' in href:
                reply['node'] = text
            # 主题标题和链接
            elif '/t/' in href:
                reply['topic_title'] = text
                reply['topic_url'] = BASE_URL + href if href.startswith('/') else href
                # 提取 topic_id
                match = re.search(r'/t/(\d+)', href)
                if match:
                    reply['topic_id'] = match.group(1)
        
        # 从 inner 提取回复内容
        reply_content_div = inner.find('div', class_='reply_content')
        if reply_content_div:
            reply['content'] = reply_content_div.get_text(strip=True)
            # 保留 HTML 格式的内容（用于导出）
            reply['content_html'] = str(reply_content_div)
        
        return reply
        
    except Exception as e:
        print(f"✗ 解析回复时出错: {e}")
        return None

def backup_user_replies(cookie, username, output_dir=BACKUP_DIR):
    """备份我的回复"""
    print("\n" + "=" * 60)
    print(f"开始备份: 我的回复 (用户: {username})")
    print("=" * 60)
    
    all_replies = []
    page = 1
    max_pages = 1000
    
    while page <= max_pages:
        print(f"\n正在获取第 {page} 页...")
        
        url = f"{BASE_URL}/member/{username}/replies"
        if page > 1:
            url += f"?p={page}"
        
        html = get_page(cookie, url)
        if not html:
            break
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 查找所有回复（dock_area + inner 配对）
        dock_areas = soup.find_all('div', class_='dock_area')
        
        if not dock_areas:
            print(f"第 {page} 页没有找到回复")
            break
        
        page_replies = []
        for dock_area in dock_areas:
            # 找到对应的 inner 或 cell (最后一条可能是 cell)
            inner = dock_area.find_next_sibling('div', class_='inner')
            if not inner:
                # 尝试查找 cell (某些回复使用 cell 而不是 inner)
                inner = dock_area.find_next_sibling('div', class_='cell')
            
            if inner:
                reply = parse_reply_item(dock_area, inner)
                if reply:
                    page_replies.append(reply)
        
        if not page_replies:
            print(f"第 {page} 页解析失败")
            break
        
        all_replies.extend(page_replies)
        print(f"✓ 第 {page} 页: 获取到 {len(page_replies)} 条回复 (累计: {len(all_replies)})")
        
        # 显示前几条
        for i, reply in enumerate(page_replies[:3], 1):
            topic_title = reply.get('topic_title', 'N/A')[:50]
            content_preview = reply.get('content', '')[:30]
            print(f"  {i}. {topic_title} - {content_preview}...")
        
        # 检查是否有下一页
        has_next = False
        all_links = soup.find_all('a')
        page_numbers = set()
        
        for link in all_links:
            href = link.get('href', '')
            if '?p=' in href or 'replies?p=' in href:
                try:
                    page_num = int(href.split('p=')[1].split('&')[0].split('#')[0])
                    if 1 <= page_num <= 1000:
                        page_numbers.add(page_num)
                except:
                    pass
        
        if page_numbers and max(page_numbers) > page:
            has_next = True
        
        if not has_next:
            print(f"\n✓ 已到达最后一页 (第 {page} 页)")
            break
        
        page += 1
        time.sleep(1)
    
    if all_replies:
        # 保存回复
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(output_dir, exist_ok=True)
        
        # JSON 格式
        json_file = os.path.join(output_dir, f'my_replies_{username}_{timestamp}.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_replies, f, ensure_ascii=False, indent=2)
        
        # TXT 格式
        txt_file = os.path.join(output_dir, f'my_replies_{username}_{timestamp}.txt')
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"V2EX 回复备份 - {username}\n")
            f.write(f"备份时间: {datetime.now()}\n")
            f.write(f"总回复数: {len(all_replies)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, reply in enumerate(all_replies, 1):
                f.write(f"{i}. {reply.get('time', 'N/A')}\n")
                f.write(f"   主题: {reply.get('topic_title', 'N/A')}\n")
                f.write(f"   作者: {reply.get('topic_author', 'N/A')}\n")
                f.write(f"   节点: {reply.get('node', 'N/A')}\n")
                f.write(f"   链接: {reply.get('topic_url', 'N/A')}\n")
                f.write(f"   回复内容:\n")
                f.write(f"   {reply.get('content', 'N/A')}\n")
                f.write("\n" + "-" * 80 + "\n\n")
        
        # Markdown 格式
        md_file = os.path.join(output_dir, f'my_replies_{username}_{timestamp}.md')
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(f"# V2EX 回复备份 - {username}\n\n")
            f.write(f"**备份时间**: {datetime.now()}\n\n")
            f.write(f"**总回复数**: {len(all_replies)}\n\n")
            f.write("---\n\n")
            
            for i, reply in enumerate(all_replies, 1):
                f.write(f"## {i}. {reply.get('topic_title', 'N/A')}\n\n")
                f.write(f"- **时间**: {reply.get('time', 'N/A')}\n")
                f.write(f"- **主题作者**: {reply.get('topic_author', 'N/A')}\n")
                f.write(f"- **节点**: {reply.get('node', 'N/A')}\n")
                f.write(f"- **链接**: [{reply.get('topic_url', 'N/A')}]({reply.get('topic_url', 'N/A')})\n\n")
                f.write(f"**回复内容**:\n\n")
                f.write(f"{reply.get('content', 'N/A')}\n\n")
                f.write("---\n\n")
        
        print("\n" + "=" * 60)
        print("✓ 回复备份完成!")
        print(f"  总回复数: {len(all_replies)} 条")
        print(f"\n文件已保存:")
        print(f"  📄 JSON: {json_file}")
        print(f"  📄 TXT:  {txt_file}")
        print(f"  📄 MD:   {md_file}")
        print("=" * 60)
        
        return all_replies
    
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
    print("V2EX 备份工具")
    print("功能: 1) 备份我的收藏  2) 备份我的发帖  3) 备份我的回复")
    print("=" * 60)
    
    # 加载 Cookie
    cookie = load_cookie()
    if not cookie:
        print("\n获取 Cookie 的步骤:")
        print("1. 在浏览器中登录 V2EX")
        print("2. 按 F12 打开开发者工具")
        print("3. 进入 应用 -> 存储 -> Cookies")
        print("4. 复制所有 Cookie 并保存到 cookie.txt")
        exit(1)
    
    # 测试 Cookie
    if not test_cookie(cookie):
        print("\n请检查你的 Cookie 是否正确")
        exit(1)
    
    # 获取用户名
    username = get_username_from_homepage(cookie)
    if not username:
        print("\n✗ 无法获取用户名，将只备份收藏")
    
    # 1. 备份收藏
    favorites = backup_favorites(cookie)
    
    # 2. 备份发帖
    if username:
        my_topics = backup_user_topics(cookie, username)
    
    # 3. 备份回复
    if username:
        my_replies = backup_user_replies(cookie, username)
    
    print("\n" + "=" * 60)
    print("✅ 所有备份任务完成!")
    print("=" * 60)

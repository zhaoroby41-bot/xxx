import openpyxl
from collections import Counter, defaultdict
import json

wb = openpyxl.load_workbook(
    r'C:\Users\Administrator\Desktop\Project\笔记报告\笔记报告\小红书笔记报告\小红书 - on line渠道笔记数据\2025年至今的全部笔记.xlsx',
    read_only=True, data_only=True
)
ws = wb['全部笔记明细']
rows = list(ws.iter_rows(values_only=True))

monthly = defaultdict(lambda: {'notes':0,'reads':0,'likes':0,'collects':0,'comments':0,'shares':0,'viral':0,'fans':0,'img':0,'video':0})
author_stats = defaultdict(lambda: {'notes':0,'reads':0,'likes':0,'collects':0,'comments':0,'shares':0,'viral':0,'fans':0})
top_notes = []

for row in rows[1:]:
    pub_date = str(row[7])[:7] if row[7] else 'unknown'
    author = row[5] or 'unknown'
    title = row[1] or ''
    note_type = row[4] or ''
    reads = row[8] or 0
    likes = row[9] or 0
    collects = row[10] or 0
    comments = row[11] or 0
    shares = row[12] or 0
    avg_read_time = row[13] or 0
    fans = row[15] or 0
    viral = 1 if row[16] == '是' else 0
    pub_full = str(row[7]) if row[7] else ''

    monthly[pub_date]['notes'] += 1
    monthly[pub_date]['reads'] += reads
    monthly[pub_date]['likes'] += likes
    monthly[pub_date]['collects'] += collects
    monthly[pub_date]['comments'] += comments
    monthly[pub_date]['shares'] += shares
    monthly[pub_date]['viral'] += viral
    monthly[pub_date]['fans'] += fans
    if note_type == '图片':
        monthly[pub_date]['img'] += 1
    else:
        monthly[pub_date]['video'] += 1

    author_stats[author]['notes'] += 1
    author_stats[author]['reads'] += reads
    author_stats[author]['likes'] += likes
    author_stats[author]['collects'] += collects
    author_stats[author]['comments'] += comments
    author_stats[author]['shares'] += shares
    author_stats[author]['viral'] += viral
    author_stats[author]['fans'] += fans

    top_notes.append({
        'title': title,
        'author': author,
        'type': note_type,
        'pub_date': pub_full[:10],
        'reads': reads,
        'likes': likes,
        'collects': collects,
        'comments': comments,
        'shares': shares,
        'fans': fans,
        'viral': viral,
        'interaction': likes + collects + comments + shares
    })

print("=== Monthly Stats ===")
for month in sorted(monthly.keys()):
    d = monthly[month]
    interaction = d['likes'] + d['collects'] + d['comments'] + d['shares']
    viral_rate = d['viral'] / d['notes'] * 100 if d['notes'] else 0
    print(f"{month}: notes={d['notes']}, reads={d['reads']}, interaction={interaction}, viral={d['viral']}({viral_rate:.0f}%), fans={d['fans']}, img={d['img']}, video={d['video']}")

print("\n=== Author Stats (sorted by reads) ===")
author_list = []
for author, d in sorted(author_stats.items(), key=lambda x: x[1]['reads'], reverse=True):
    avg_reads = d['reads'] // d['notes'] if d['notes'] else 0
    viral_rate = d['viral'] / d['notes'] * 100 if d['notes'] else 0
    total_interaction = d['likes'] + d['collects'] + d['comments'] + d['shares']
    author_list.append({
        'author': author,
        'notes': d['notes'],
        'reads': d['reads'],
        'avg_reads': avg_reads,
        'viral': d['viral'],
        'viral_rate': round(viral_rate, 1),
        'interaction': total_interaction,
        'fans': d['fans']
    })
    print(f"{author}: notes={d['notes']}, reads={d['reads']}, avg_reads={avg_reads}, viral={d['viral']}({viral_rate:.0f}%), interaction={total_interaction}, fans={d['fans']}")

print("\n=== Top 20 Notes by Reads ===")
top20 = sorted(top_notes, key=lambda x: x['reads'], reverse=True)[:20]
for i, n in enumerate(top20, 1):
    print(f"{i}. [{n['pub_date']}] {n['title'][:40]} | {n['author']} | 阅读:{n['reads']} 点赞:{n['likes']} 收藏:{n['collects']} 评论:{n['comments']}")

print("\n=== Top 20 by Interaction ===")
top20i = sorted(top_notes, key=lambda x: x['interaction'], reverse=True)[:20]
for i, n in enumerate(top20i, 1):
    print(f"{i}. [{n['pub_date']}] {n['title'][:40]} | {n['author']} | 互动:{n['interaction']} 阅读:{n['reads']}")

# 分析爆款内容特征
print("\n=== Viral Notes Title Keywords ===")
viral_notes = [n for n in top_notes if n['viral'] == 1]
all_titles = ' '.join([n['title'] for n in viral_notes])
print(f"Total viral notes: {len(viral_notes)}")
# 简单分析标题中的数字和关键词
import re
numbers_in_titles = re.findall(r'\d+', all_titles)
print(f"Notes with numbers in title: {sum(1 for n in viral_notes if re.search(r'\\d', n['title']))}")
print(f"Image viral: {sum(1 for n in viral_notes if n['type']=='图片')}")
print(f"Video viral: {sum(1 for n in viral_notes if n['type']=='视频')}")

# 按季度统计
print("\n=== Quarterly Stats ===")
quarterly = defaultdict(lambda: {'notes':0,'reads':0,'interaction':0,'viral':0,'fans':0})
for row in rows[1:]:
    pub_date = str(row[7]) if row[7] else ''
    if len(pub_date) >= 7:
        year = pub_date[:4]
        month_num = int(pub_date[5:7])
        quarter = (month_num - 1) // 3 + 1
        qkey = f"{year}-Q{quarter}"
        reads = row[8] or 0
        likes = row[9] or 0
        collects = row[10] or 0
        comments = row[11] or 0
        shares = row[12] or 0
        fans = row[15] or 0
        viral = 1 if row[16] == '是' else 0
        quarterly[qkey]['notes'] += 1
        quarterly[qkey]['reads'] += reads
        quarterly[qkey]['interaction'] += likes + collects + comments + shares
        quarterly[qkey]['viral'] += viral
        quarterly[qkey]['fans'] += fans

for q in sorted(quarterly.keys()):
    d = quarterly[q]
    vr = d['viral'] / d['notes'] * 100 if d['notes'] else 0
    print(f"{q}: notes={d['notes']}, reads={d['reads']}, interaction={d['interaction']}, viral={d['viral']}({vr:.0f}%), fans={d['fans']}")

# 保存数据到JSON供后续使用
output = {
    'monthly': {k: dict(v) for k, v in monthly.items()},
    'author_list': author_list,
    'top20_reads': top20,
    'top20_interaction': top20i,
    'quarterly': {k: dict(v) for k, v in quarterly.items()},
    'summary': {
        'total_notes': len(rows) - 1,
        'unique_authors': len(author_stats),
        'total_reads': sum(n['reads'] for n in top_notes),
        'total_likes': sum(n['likes'] for n in top_notes),
        'total_collects': sum(n['collects'] for n in top_notes),
        'total_comments': sum(n['comments'] for n in top_notes),
        'total_shares': sum(n['shares'] for n in top_notes),
        'total_fans': sum(n['fans'] for n in top_notes),
        'total_viral': sum(n['viral'] for n in top_notes),
        'viral_rate': round(sum(n['viral'] for n in top_notes) / (len(rows)-1) * 100, 1),
        'avg_reads': round(sum(n['reads'] for n in top_notes) / (len(rows)-1), 0)
    }
}
with open('analysis_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\nData saved to analysis_data.json")

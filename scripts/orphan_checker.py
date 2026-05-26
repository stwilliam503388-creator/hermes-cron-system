#!/usr/bin/env python3
"""
Daily orphan detector + auto-linker for Obsidian vault.
Run as cron job. Checks TODAY's new files only.
"""
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

VAULT = "/Users/liuwei/Documents/个人学习笔记"
WIKILINK_RE = re.compile(r'\[\[([^\]|#]+?)(?:[|#][^\]]+?)?\]\]')
COURSE_NUM_RE = re.compile(r'^(0[1-9]|1[0-9])[-_]')
APPENDIX_RE = re.compile(r'^附录[A-D]')

def find_all_md(vault):
    files = []
    for root, dirs, filenames in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in ('.obsidian', '.git', '.trash') and 'VaultBackups' not in root]
        for f in filenames:
            if f.endswith('.md'):
                files.append(os.path.join(root, f))
    return files

def get_outgoing_links(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return set(t.strip() for t in WIKILINK_RE.findall(f.read()))
    except:
        return set()

def get_incoming_map(vault, files):
    imap = defaultdict(set)
    for fp in files:
        rel = os.path.relpath(fp, vault)
        for link in get_outgoing_links(fp):
            imap[link].add(rel)
    return imap

def resolve_incoming(rel, incoming_map):
    basename = os.path.splitext(os.path.basename(rel))[0]
    full_no_ext = rel[:-3] if rel.endswith('.md') else rel
    result = set()
    for lookup in (full_no_ext, basename):
        result.update(incoming_map.get(lookup, set()))
    result.discard(rel)
    return result

def is_orphan(rel, incoming_map):
    fpath = os.path.join(VAULT, rel)
    outgoing = get_outgoing_links(fpath)
    incoming = resolve_incoming(rel, incoming_map)
    return len(outgoing) == 0 and len(incoming) == 0

def find_related_entities(rel, vault):
    fpath = os.path.join(vault, rel)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return []
    if not content:
        return []
    
    fname = os.path.basename(rel)[:-3]
    terms = set(re.findall(r'[\w\u4e00-\u9fff]{2,}', fname))
    sample = content[:500]
    terms.update(re.findall(r'[\w\u4e00-\u9fff]{2,}', sample))
    
    stopwords = {'the','is','of','and','or','in','to','for','a','an','的','是','了','在','和','与',
                 'md','2026','2025','2024','日报','简报','2026-05','url','tags','created','date','category'}
    terms -= stopwords
    
    candidates = []
    entity_dirs = ['wiki/entities', 'raw/notes/obsidian-概念']
    for edir in entity_dirs:
        edir_path = os.path.join(vault, edir)
        if not os.path.isdir(edir_path):
            continue
        for root, dirs, files in os.walk(edir_path):
            for f in files:
                if not f.endswith('.md'):
                    continue
                frel = os.path.relpath(os.path.join(root, f), vault)
                if frel == rel:
                    continue
                fname_terms = set(re.findall(r'[\w\u4e00-\u9fff]{2,}', f[:-3]))
                overlap = terms & fname_terms
                if overlap:
                    candidates.append((frel, len(overlap)))
    
    candidates.sort(key=lambda x: -x[1])
    return [c[0][:-3] for c in candidates[:3]]

def make_link(target, alias=None):
    if alias:
        return f"[[{target}|{alias}]]"
    return f"[[{target}]]"

def append_links(filepath, links):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return False
    
    if '相关链接' in content or '关联笔记' in content:
        return False  # Already has links
    
    link_lines = "\n".join(f"- {link}" for link in links)
    content = content.rstrip() + f"\n\n## 相关链接\n\n{link_lines}\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return True

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Find files created/modified today
    all_files = find_all_md(VAULT)
    
    new_today = []
    for fp in all_files:
        try:
            mtime = os.path.getmtime(fp)
            mdate = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')
            if mdate == today:
                new_today.append(fp)
        except:
            continue
    
    if not new_today:
        print(f"[{datetime.now().isoformat()}] No new .md files today ({today}).")
        return
    
    # Check which new files are orphans
    incoming_map = get_incoming_map(VAULT, all_files)
    
    new_orphans = []
    for fp in new_today:
        rel = os.path.relpath(fp, VAULT)
        if is_orphan(rel, incoming_map):
            new_orphans.append((rel, fp))
    
    if not new_orphans:
        print(f"[{datetime.now().isoformat()}] {len(new_today)} new files today, none are orphans.")
        return
    
    print(f"[{datetime.now().isoformat()}] Found {len(new_orphans)} new orphan files:")
    for rel, _ in new_orphans:
        print(f"  ORPHAN: {rel}")
    
    # Try to auto-link
    fixed = 0
    for rel, fpath in new_orphans:
        # Default: link to index
        links = [make_link("index", "知识库索引")]
        
        # Try to find related entities
        related = find_related_entities(rel, VAULT)
        for r in related:
            links.append(make_link(r))
        
        if append_links(fpath, links):
            fixed += 1
            print(f"  FIXED: {rel} -> {len(links)} links")
    
    print(f"\n[{datetime.now().isoformat()}] Fixed {fixed}/{len(new_orphans)} new orphans.")
    
    # Summary stats
    total_all = len(all_files)
    total_orphans = 0
    for fp in all_files:
        rel = os.path.relpath(fp, VAULT)
        if is_orphan(rel, incoming_map):
            total_orphans += 1
    
    print(f"Vault health: {total_all} files, {total_orphans} orphans ({total_orphans*100//total_all}%)")

if __name__ == '__main__':
    main()

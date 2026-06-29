#!/usr/bin/env python3
"""自动化采购Agent测试优化循环 — 多场景验证"""
import json, time, urllib.request, sys

BASE = 'http://127.0.0.1:8000'
PASS, FAIL, WARN = '✓', '✗', '⚠'

def api(path, payload=None, token=None, method='POST', timeout=120):
    data = json.dumps(payload or {}).encode() if payload else None
    headers = {'Content-Type': 'application/json'} if payload else {}
    if token: headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f'{BASE}{path}', data=data, headers=headers, method=method)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def login():
    return api('/api/auth/login', {'email':'user@fuyao.com','password':'password123'})['token']

def run_comparison(token, query, max_wait=180):
    job = api('/api/comparison/search-jobs', {
        'query': query,
        'deliveryTime': 'unlimited',
        'weights': {'price': 40, 'delivery': 35, 'rating': 25}
    }, token)
    jid = job['jobId']
    for _ in range(max_wait):
        job = api(f'/api/comparison/search-jobs/{jid}', token=token, method='GET')
        if job['status'] in ('completed', 'failed'): break
        time.sleep(0.5)
    return job

# ---- Test scenarios ----
SCENARIOS = [
    {
        'name': '碎纸机',
        'query': '碎纸机 Aktenvernichter 德国',
        'keywords_must': ['aktenvernichter', 'shredder', 'schredder'],
        'keywords_must_not': ['papier', 'kopierpapier', 'paper', 'a4', 'ordner', 'schere'],
        'min_results': 3,
    },
    {
        'name': 'A4复印纸',
        'query': 'A4 copy paper 500 sheets Germany',
        'keywords_must': ['papier', 'paper', 'a4'],
        'keywords_must_not': ['aktenvernichter', 'shredder', 'maus', 'tastatur'],
        'min_results': 3,
    },
    {
        'name': '鼠标',
        'query': '鼠标 computer mouse 德国',
        'keywords_must': ['maus', 'mouse'],
        'keywords_must_not': ['tastatur', 'keyboard', 'papier', 'aktenvernichter'],
        'min_results': 1,
    },
    {
        'name': '键盘',
        'query': '键盘 Tastatur 德国',
        'keywords_must': ['tastatur', 'keyboard'],
        'keywords_must_not': ['maus', 'mouse', 'papier'],
        'min_results': 1,
    },
    {
        'name': '打印机',
        'query': '打印机 Drucker 德国',
        'keywords_must': ['drucker', 'printer'],
        'keywords_must_not': ['papier', 'paper', 'tastatur'],
        'min_results': 1,
    },
    {
        'name': '投影仪',
        'query': '投影仪 Beamer Projektor 德国',
        'keywords_must': ['beamer', 'projektor'],
        'keywords_must_not': ['papier', 'paper', 'aktenvernichter'],
        'min_results': 1,
    },
    {
        'name': '计算器',
        'query': '计算器 Taschenrechner 德国',
        'keywords_must': ['taschenrechner', 'calculator'],
        'keywords_must_not': ['papier', 'maus', 'aktenvernichter'],
        'min_results': 1,
    },
    {
        'name': '文件夹',
        'query': '文件夹 Ordner 德国',
        'keywords_must': ['ordner', 'folder'],
        'keywords_must_not': ['papier', 'aktenvernichter', 'maus'],
        'min_results': 1,
    },
]

def evaluate_results(scenario, results):
    issues = []
    name = scenario['name']
    products = ' '.join([str(r.get('product','')) for r in results]).lower()
    
    # Check min results
    if len(results) < scenario['min_results']:
        issues.append(f'结果太少: {len(results)} < {scenario["min_results"]}')
    
    # Check must-have keywords
    for kw in scenario['keywords_must']:
        if kw.lower() not in products:
            issues.append(f'缺少关键词: {kw}')
    
    # Check must-not keywords
    for kw in scenario['keywords_must_not']:
        if kw.lower() in products:
            # Count how many results contain this bad keyword
            bad = sum(1 for r in results if kw.lower() in str(r.get('product','')).lower())
            if bad > 0:
                issues.append(f'混入无关产品含 \"{kw}\": {bad}/{len(results)}条')
    
    # Check prices
    prices = [r.get('unitPriceEur') for r in results if r.get('unitPriceEur')]
    if prices:
        min_p, max_p = min(prices), max(prices)
        if max_p > 0 and min_p / max_p < 0.01:
            issues.append(f'价格异常: min={min_p:.2f} max={max_p:.2f}')
    
    # Check search phrase
    phrase_events = [e for e in [] if '短语' in e.get('message','')]  # populated below
    return issues

def main():
    print('=' * 60)
    print('ProcureAI 多场景自动化测试')
    print('=' * 60)
    
    token = login()
    results_summary = []
    
    for i, s in enumerate(SCENARIOS):
        name = s['name']
        print(f'\n[{i+1}/{len(SCENARIOS)}] {name}: {s["query"][:60]}')
        
        start = time.time()
        job = run_comparison(token, s['query'])
        elapsed = time.time() - start
        results = job.get('results', [])
        events = job.get('events', [])
        
        # Find search phrase
        phrase = ''
        for e in events:
            if '短语' in e.get('message', ''):
                phrase = e['message']
                break
        
        # Evaluate
        products = ' '.join([str(r.get('product','')) for r in results]).lower()
        issues = []
        
        if len(results) < s['min_results']:
            issues.append(f'结果太少: {len(results)}/{s["min_results"]}')
        
        for kw in s['keywords_must']:
            if kw.lower() not in products:
                issues.append(f'缺关键词: {kw}')
        
        for kw in s['keywords_must_not']:
            bad = sum(1 for r in results if kw.lower() in str(r.get('product','')).lower())
            if bad > 0:
                issues.append(f'混入 \"{kw}\": {bad}/{len(results)}条')
        
        status = PASS if not issues else (WARN if len(results) >= s['min_results'] else FAIL)
        
        print(f'  {status} {elapsed:.0f}s | {len(results)}条结果 | 短语={phrase[phrase.find("「")+1:phrase.find("」")] if "「" in phrase else "?"}')
        for issue in issues:
            print(f'    {FAIL if "太少" in issue or "缺" in issue else WARN} {issue}')
        
        results_summary.append({
            'name': name,
            'status': 'PASS' if not issues else ('WARN' if len(results) >= s['min_results'] else 'FAIL'),
            'results': len(results),
            'time': elapsed,
            'issues': issues,
            'phrase': phrase,
        })
    
    # Summary
    print('\n' + '=' * 60)
    passed = sum(1 for r in results_summary if r['status'] == 'PASS')
    warned = sum(1 for r in results_summary if r['status'] == 'WARN')
    failed = sum(1 for r in results_summary if r['status'] == 'FAIL')
    print(f'Summary: {passed} PASS, {warned} WARN, {failed} FAIL / {len(SCENARIOS)}')
    
    for r in results_summary:
        icon = PASS if r['status']=='PASS' else (WARN if r['status']=='WARN' else FAIL)
        print(f'  {icon} {r["name"]}: {r["results"]}条 {r["time"]:.0f}s {r["issues"]}')
    
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())

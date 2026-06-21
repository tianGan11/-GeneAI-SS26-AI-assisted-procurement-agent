# AI Agent 动态爬虫操作指南 (Autonomous Scraper SOP)

## 第一阶段：合规性与规则检查 (Bot & Rule Inspection)
1. 检查 robots.txt：访问 domain.com/robots.txt，识别允许和禁止爬取的路径
2. 识别反爬机制：判断是否部署了 Cloudflare、CAPTCHA 或强制登录
3. 制定策略：设置合理的 User-Agent、请求频率、是否需 Selenium

## 第二阶段：网站结构解析 (Site Analysis)
1. 识别页面类型：搜索列表页 vs 供应商详情页
2. 定位核心容器：
   - 供应商名称 → h1 或 company-name 类名
   - 指标数据区 → 包含"成立年份"、"员工数"、"地址"的邻近 DOM 节点
   - 产品列表区 → 大量重复结构的容器

## 第三阶段：信息分类与字段提取
1. 直接提取：名称、城市、网站链接
2. 模式匹配：年份(19|20\d{2})、规模(Mitarbeiter/Staff/数字区间)
3. 语义清理：剔除导航栏、页脚、广告

## 第四阶段：动态设置爬虫
1. 定义 RULES 字典：针对该网站的 CSS 选择器或 XPath
2. 设置交互动作：如"点击查看更多"模拟点击
3. 配置过滤器：排除 /ads/、/recommendations/

## 第五阶段：执行抓取与数据返回
1. 执行抓取并监控成功率
2. 校验 JSON 是否符合 Schema
3. 异常处理：字段缺失记录原因、遭遇封锁立即停止

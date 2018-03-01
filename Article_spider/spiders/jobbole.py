import datetime

import re

import scrapy
from pydispatch import dispatcher
from scrapy.http import Request

# python3中当url不完整时的解决
from urllib import parse
# Python2中url不完整的解决
# import urlparse

from Article_spider.items import JobboleItem, JobboleItemLoader
from Article_spider.utils.common import get_md5
from scrapy.loader import ItemLoader
from scrapy import signals


class JobboleSpider(scrapy.Spider):
    name = "jobbole"
    allowed_domains = ["blog.jobbole.com"]
    start_urls = ['http://blog.jobbole.com/all-posts']

    # 收集伯乐在线所有404的url以及404页面数
    handle_httpstatus_list = [404]

    def __init__(self,**kwargs):
        self.fail_urls = []
        dispatcher.connect(self.handle_spider_cosed, signals.spider_closed)

    def handle_spider_cosed(self, spider, reason):
        self.crawler.stats.set_value("failed_urls", ",".join(self.fail_urls))
        pass

    def parse(self, response):
        """
        1. 获取文章列表页中的文章url交给scrapy下载并进行解析
        2. 获取下一页的url并交给scrapy进行下载,  下载完成后交给parse
        """
        # 如果状态值为404
        if response.status == 404:
            self.fail_urls.append(response.url)
            self.crawler.stats.inc_value("failed_url")

        # 解析列表页中的所有文章url并交给scrapy下载后并进行解析
        # 不使用extra成值的list可以进行二次筛选
        # post_urls = response.css("#archive .floated-thumb .post-thumb a::attr(href)").extract()
        post_nodes = response.css("#archive .floated-thumb .post-thumb a")
        for post_node in post_nodes:
            # 获取封面图的url
            image_url = post_node.css("img::attr(src)").extract_first("")
            post_url = post_node.css("::attr(href)").extract_first("")
            # post_url 是我们每一页的具体的文章url。
            # 下面这个request是文章详情页面. 使用回调函数每下载完一篇就callback进行这一篇的具体解析。
            # 我们现在获取到的是完整的地址可以直接进行调用。如果不是完整地址: 根据response.url + post_url
            # def urljoin(base, url)完成url的拼接
            # 初始化好的Request如何交给scrapy进行下载: yield关键字
            # yield  Request(url=parse.urljoin(response.url, post_url),callback=self.parse_detail)
            yield Request(url=parse.urljoin(response.url, post_url), meta={"front_image_url": image_url},
                          callback=self.parse_detail)
            # Requ est(url=post_url, callback=self.parse_detail)

        # 提取下一页并交给scrapy进行下载
        next_url = response.css(".next.page-numbers::attr(href)").extract_first("")
        # 如果.next .pagenumber 是指两个class为层级关系。而不加空格为同一个标签
        if next_url:
            # 如果还有next url 就调用下载下一页，回调parse函数找出下一页的url。
            yield Request(url=parse.urljoin(response.url, next_url), callback=self.parse)
            # pass

    def parse_detail(self, response):

        # 通过item loader加载item
        front_image_url = response.meta.get("front_image_url", "")  # 文章封面图

        item_loader = JobboleItemLoader(item=JobboleItem(), response=response)

        # 通过css选择器将后面的指定规则进行解析。
        item_loader.add_css("title", ".entry-header h1::text")
        item_loader.add_value("url", response.url)
        item_loader.add_value("url_object_id", get_md5(response.url))
        item_loader.add_css("create_date", "p.entry-meta-hide-on-mobile::text")
        item_loader.add_value("front_image_url", [front_image_url])
        item_loader.add_css("praise_nums", ".vote-post-up h10::text")
        item_loader.add_css("comment_nums", "a[href='#article-comment'] span::text")
        item_loader.add_css("fav_nums", ".bookmark-btn::text")
        item_loader.add_css("tags", "p.entry-meta-hide-on-mobile a::text")
        item_loader.add_css("content", "div.entry")

        # 调用这个方法来对规则进行解析生成item对象
        article_item = item_loader.load_item()

        # 已经填充好了值调用yield传输至pipeline
        yield article_item

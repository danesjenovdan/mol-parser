import scrapy
import re


class PeopleSpider(scrapy.Spider):
    name = 'people'
    custom_settings = {
        'ITEM_PIPELINES': {
            'parlaparser.pipelines.ParlaparserPipeline': 1
        },
        'CONCURRENT_REQUESTS': '1'
    }
    allowed_domains = ['ljubljana.si']
    base_url = 'https://www.ljubljana.si'
    start_urls = ['https://www.ljubljana.si/sl/mestni-svet/mestni-svet-mol/']

    def parse(self, response):
        for party_link in response.css(".sub-navigation-list a::attr(href)").extract():
            yield scrapy.Request(url=self.base_url + party_link, callback=self.parse_orgs)

    def parse_orgs(self, response):
        org_name = response.css(".header-holder h1::text").extract_first()
        org_name = re.sub(r'\([^)]*\)', '', org_name)

        for member_link in response.css(".block_area.block_area_main .blockcontent a::attr(href)").extract():
            yield scrapy.Request(
                url=self.base_url + member_link,
                callback=self.parse_member,
                meta={'org_name': org_name})

    def parse_member(self, response):
        full_name = response.css(".header-holder h1::text").extract_first()
        extended_name = response.css(".title-holder h2::text").extract_first()
        if extended_name:
            role = extended_name.split(full_name)[0].strip()
        else:
            role = 'member'
        yield {
            'type': 'person',
            'name': full_name,
            'org_name': response.meta["org_name"],
            'role': role
        }

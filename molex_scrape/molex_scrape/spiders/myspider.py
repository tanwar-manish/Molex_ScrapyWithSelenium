
import scrapy
import re
import os
from scrapy.http import Request
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class MyspiderSpider(scrapy.Spider):
    name = "myspider"
    allowed_domains = ['molex.com']
    start_urls = [
        'https://www.molex.com/en-us/products/connectors/solderless-terminals?materialMaster_promotable=true&category_uid=solderless-terminals&page=1'
    ]

    custom_settings = {
        'FEEDS': {
            'molex_output.csv': {
                'format': 'csv',
                'fields': ['Product URL', 'Product Count', 'Category Name', 'Category URL'],
            },
        },
        'RETRY_TIMES': 3,  
    }

    def __init__(self, *args, **kwargs):
        super(MyspiderSpider, self).__init__(*args, **kwargs)
        options = Options()
        options.add_argument('--disable-gpu')
        options.add_argument("start-maximized")
        options.add_argument("--lang=en")
        options.add_argument('--disable-gpu')
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def parse(self, response):
        current_page = int(response.url.split('=')[-1])
        try:
            # Create cache directory
            if not os.path.exists('cache_dir'):
                os.makedirs('cache_dir')

            
            fpath = re.sub(r'\W+', '_', response.url)
            cache_path = os.path.join('cache_dir', f'{fpath}.html')

            with open(cache_path, 'w', encoding='utf-8') as cache_page:
                cache_page.write(response.text)

            product_links = response.xpath('//*[@id="productlist-697e85dbef"]/div[2]/div[2]//h3/a/@href').extract()

            # Check if the product links are found
            if not product_links:
                self.logger.warning(f"No product links found on page {current_page}, using Selenium to retry...")
                # Retry the same page using Selenium
                self.driver.get(response.url)
                self.driver.implicitly_wait(10)
                product_elements = self.driver.find_elements(By.XPATH, '//*[@id="productlist-697e85dbef"]/div[2]/div[2]//h3/a')
                product_links = [element.get_attribute('href') for element in product_elements]
                
                if not product_links:
                    self.logger.error(f"No product links found on page {current_page} even after using Selenium")
                    return

            # Extracting product count
            product_count_text = response.xpath('//*[@id="productlist-697e85dbef"]/div[1]/h4/text()').extract_first()
            product_count = int(re.search(r'\d+', product_count_text).group()) if product_count_text else 0

            # Category Name and URL
            category_name = 'Solderless Terminals'
            category_url = 'https://www.molex.com/en-us/products/connectors/solderless-terminals?materialMaster_promotable=true'

            for link in product_links:
                yield {
                    'Product URL': response.urljoin(link),
                    'Product Count': product_count,
                    'Category Name': category_name,
                    'Category URL': category_url
                }

            # Check for next page
            if current_page < 285:
                next_page = current_page + 1
                next_page_url = f"https://www.molex.com/en-us/products/connectors/solderless-terminals?materialMaster_promotable=true&category_uid=solderless-terminals&page={next_page}"
                yield scrapy.Request(next_page_url, callback=self.parse, dont_filter=True)

        except Exception as e:
            self.logger.error(f"An error occurred on page {current_page}: {str(e)}")
            # Retry the same page if an error occurs
            retry_times = response.meta.get('retry_times', 0) + 1
            if retry_times <= self.custom_settings['RETRY_TIMES']:
                retry_req = response.request.copy()
                retry_req.meta['retry_times'] = retry_times
                yield retry_req
            else:
                self.logger.error(f"Failed to retrieve page {current_page} after {self.custom_settings['RETRY_TIMES']} retries")

    def closed(self, reason):
        self.driver.quit()

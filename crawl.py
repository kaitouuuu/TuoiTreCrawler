import json
import os
import time
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.service import Service
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.utils.exceptions import IllegalCharacterError

# CONSTANTS
URL = "https://tuoitre.vn/"

class NewsItem:
    def __init__(self):
        self.postId = None
        self.title = None
        self.content = None
        self.author = None
        self.date = None
        self.category = None
        self.audio_podcast = None
        self.vote_reactions = None
        self.comments = None
        self.url = None

    def set_postId(self, postId):
        self.postId = postId

    def get_postId(self):
        return self.postId

    def set_url(self, url):
        self.url = url

    def get_url(self):
        return self.url

    def set_title(self, title):
        self.title = title

    def get_title(self):
        return self.title

    def set_content(self, content):
        self.content = content

    def get_content(self):
        return self.content

    def set_author(self, author):
        self.author = author

    def get_author(self):
        return self.author

    def set_date(self, date):
        self.date = date

    def get_date(self):
        return self.date

    def set_category(self, category):
        self.category = category

    def get_category(self):
        return self.category

    def set_audio_podcast(self, audio_podcast):
        self.audio_podcast = audio_podcast

    def get_audio_podcast(self):
        return self.audio_podcast

    def set_vote_reactions(self, vote_reactions):
        self.vote_reactions = vote_reactions

    def get_vote_reactions(self):
        return self.vote_reactions

    def set_comments(self, comments):
        self.comments = comments

    def get_comments(self):
        return self.comments

    def to_dict(self):
        return {
            "postId": self.postId,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "date": self.date,
            "category": self.category,
            "url": self.url,
            "audio_podcast": self.audio_podcast,
            "vote_reactions": self.vote_reactions,
            "comments": self.comments
        }

class MainScreenTransition:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 1)
        self.workbook = Workbook()
        self.worksheet = self.workbook.active
        self.categories = []
        self.category_links = []

    def extract_categories(self):
        self.driver.get(URL)
        try:
            category_items = self.driver.find_elements(By.CSS_SELECTOR, "div.header__nav-flex ul.menu-nav > li")
            
            for item in category_items:
                link = item.find_element(By.TAG_NAME, "a")
                category = link.get_attribute("title")
                href = link.get_attribute("href")
                
                if category and href and category != "Trang chủ" and category != "Video":
                    self.categories.append(category)
                    full_link = URL + href if not href.startswith('http') else href
                    self.category_links.append(full_link)
        
        except TimeoutException:
            print("Timed out waiting for menu-nav to load")
        except NoSuchElementException:
            print("Could not find the required elements")

class CategoryScreenTransition:
    def __init__(self, url, category, driver):
        self.url = url
        self.category = category
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 1)
        self.workbook = Workbook()
        self.worksheet = self.workbook.active
        self.news_titles = []
        self.news_links = []

    def extract_news(self):
        self.driver.get(self.url)
        try:
            while len(self.news_titles) < 100:
                self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "box-category-item")))
                news_items = self.driver.find_elements(By.CLASS_NAME, "box-category-item")
                
                for item in news_items:
                    try:
                        title_element = item.find_element(By.CLASS_NAME, "box-category-link-title")
                        title = title_element.get_attribute("title")
                        link = title_element.get_attribute("href")
                        
                        if title and link and title not in self.news_titles:
                            self.news_titles.append(title)
                            full_link = URL + link if not link.startswith('http') else link
                            self.news_links.append(full_link)
                    except NoSuchElementException:
                        continue
                
                if len(self.news_titles) >= 100:
                    break
                
                try:
                    view_more_button = self.driver.find_element(By.CLASS_NAME, "view-more-seciton")
                    view_more_button.click()
                    time.sleep(2)
                except TimeoutException:
                    print("No more 'Xem thêm' button found or it's not clickable")
                    break
        
        except TimeoutException:
            print("Timed out waiting for page to load")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
        
        finally:
            print(f"Total news items collected: {len(self.news_titles)}")
            print("\n")

class PageTextCrawl:
    def __init__(self, url, category, driver):
        self.url = url
        self.category = category
        self.file_name = None
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 5)
        self.workbook = Workbook()
        self.worksheet = self.workbook.active

    def crawl_page(self):
        self.driver.get(self.url)
        try:
            news_item = NewsItem()

            # Extract post ID from the URL
            id = re.search(r"(\d+)(?=\D*$)", self.url)
            if id:
                postID = id.group(1)
            else:
                print("Post ID not found in the URL.")
                postID = None
            news_item.set_postId(postID)

            # Set title, with None fallback
            try:
                title = self.driver.find_element(By.CLASS_NAME, "detail-title.article-title").text
            except NoSuchElementException:
                title = None
            news_item.set_title(title)

            # Set content, with None fallback
            try:
                sapo_text = self.driver.find_element(By.CLASS_NAME, "detail-sapo").text
                content_paragraphs = self.driver.find_elements(By.CSS_SELECTOR, "div.detail-content.afcbc-body > p")
                content_text = '\n'.join([p.text for p in content_paragraphs])
                content = sapo_text + '\n' + content_text
            except NoSuchElementException:
                content = None
            news_item.set_content(content)

            # Set author, with None fallback
            try:
                author = self.driver.find_element(By.CLASS_NAME, "detail-author-bot").text
            except NoSuchElementException:
                author = None
            news_item.set_author(author)

            # Set date, with None fallback
            try:
                date = self.driver.find_element(By.CLASS_NAME, "detail-time").text
            except NoSuchElementException:
                date = None
            news_item.set_date(date)

            # Set audio_podcast, with None fallback
            try:
                audio_podcast = self.driver.find_element(By.CSS_SELECTOR, "div.audioplayer").get_attribute("data-file")
            except NoSuchElementException:
                audio_podcast = None
            news_item.set_audio_podcast(audio_podcast)

            # Set comment, vote_reactions, with None fallback
            try:
                vote_reactions = self.driver.find_element(By.CLASS_NAME, "ico.comment")
                vote_reactions.click()
                time.sleep(1)
                comments = self.driver.find_elements(By.CSS_SELECTOR, "div.lst-comment > li.item-comment")
                comments_data = []
                for comment in comments:
                    comment_data = {
                        "commentId": comment.get_attribute("data-cmid"),
                        "author": comment.get_attribute("data-replyname"),
                        "text": comment.find_element(By.CSS_SELECTOR, "span.contentcomment").text,
                        "date": comment.find_element(By.CSS_SELECTOR, "span.timeago").get_attribute("title")
                    }
                    comments_data.append(comment_data)
            except NoSuchElementException:
                comments_data = None
            news_item.set_comments(comments_data)

            # Set category and URL, which are expected to exist already
            news_item.set_category(self.category)
            news_item.set_url(self.url)
            self.file_name = postID

            return news_item  
        except Exception as e:
            print(f"An error occurred while crawling the page: {e}")
            return None
        
    def save_to_json(self, news_item):
        if news_item is not None:
            with open(f"{self.file_name}.json", "w", encoding="utf-8") as file:
                json.dump(news_item.to_dict(), file, indent=4, ensure_ascii=False)
        else:
            print(f"Skipping JSON save for {self.url} due to crawl failure")

if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument('--ssl_client_socket_impl=yes')
    chrome_options.add_argument('--ignore-certificate-errors')

    driver = webdriver.Chrome(options=chrome_options)
    
    web = MainScreenTransition(driver)
    web.extract_categories()
    print(web.category_links)
    print(web.categories)
    print("Done extracting categories!")
    
    news_items = []

    for category_link, category in zip(web.category_links, web.categories):
        print(f"Extracting news from {category}")
        web_category = CategoryScreenTransition(category_link, category, driver)
        if web_category:
            web_category.extract_news()
            for link in web_category.news_links:
                print(f"Extracting news from {link}")
                page = PageTextCrawl(link, category, driver)
                news_item = page.crawl_page()
                if news_item:
                    page.save_to_json(news_item)
                else:
                    print(f"Skipping {link} due to crawl failure")
        else:
            print(f"Failed to extract_news() from {category}")
        
            
    print(f"Total items collected: {len(news_items)}")
    
    print("Done extracting news!")
    driver.quit()

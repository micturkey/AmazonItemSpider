from bs4 import BeautifulSoup
from multiprocessing import Pool
import requests

# 获取列表页，iPod为关键词，自行修改
my_headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/603.2.4 (KHTML, like Gecko) Version/10.1.1 Safari/603.2.4'}
response = requests.get("https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords=ipod",
                        headers=my_headers)
soup = BeautifulSoup(response.text, 'lxml')
item = soup.select("[class=s-item-container]")
items = []

# 获取某一项目细节
def get_detail(i):
    response_detail = requests.get(items[i]['url'], headers=my_headers)
    soup_detail = BeautifulSoup(response_detail.text, 'lxml')
    detail = soup_detail.find(id="feature-bullets")
    print("get detail " + detail.get_text())
    # 多线程情况下的返回参数，因为python多线程不支持修改全局变量，所以绕了一绕
    x = {
        i: detail.get_text()
    }
    return x


for i in item:
    x = i.find("a", "a-link-normal s-access-detail-page s-color-twister-title-link a-text-normal")
    # print(x)
    url = x.get("href")
    if url[0:4] == "/gp/":
        url = "https://www.amazon.com" + url
    rank = i.find("a", "a-popover-trigger a-declarative").get_text().split()[0]
    img = i.find("img", "s-access-image cfMarker").get("src")
    # print(rank)
    price = i.find("span", "a-color-base sx-zero-spacing")
    if price == None:
        price = i.find("span", "a-size-base a-color-base")
        price = price.get_text()
        # print(price.get_text()+ " x")
    else:
        price = price.get("aria-label")
        # print(price.get('aria-label'))
    # href = x.get("href")
    # print(x.get('"ref")+" "+x.get("title"))
    # print(img)
    data = {
        'title': x.get("title"),
        'price': price,
        'rank': rank,
        'img': img,
        'url': url,
        'detail': ""
    }
    items.append(data)

# 多线程处理
pool = Pool()
# pool.map(get_detail, range(1))
process = []
detail = []
print(items)
for i in range(len(items)):
    process.append(pool.apply_async(get_detail, (i,)))
    # detail.append(get_detail(i))
pool.close()
pool.join()
for res in process:
    detail.append(res.get())
for i in range(len(items)):
    items[i]['detail'] = detail[i]
# 经过测试，采用多线程比直接通过循环快了100%还多
# time.sleep(2)
print(items)

from bs4 import BeautifulSoup
from multiprocessing import Pool
import requests
import pymysql

db = pymysql.connect("localhost", "root", "123456", "amazon", charset="utf8")
cursor = db.cursor()

my_headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/603.2.4 (KHTML, like Gecko)'
                  ' Version/10.1.1 Safari/603.2.4'}


# 获取某一项目细节
def get_detail(i):
    print(i)
    print(items[i]['url'])
    # 超时重连
    response_detail = get_response(items[i]['url'], 0)
    while response_detail is None:
        print(str(i) + "failed, retry")
        response_detail = get_response(items[i]['url'], 0)
    soup_detail = BeautifulSoup(response_detail.text, 'lxml')
    tags_to_remove = ['script', 'style']
    for tag in soup_detail.find_all(tags_to_remove):
        tag.extract()

    # 顶部细节
    feature = soup_detail.find(id="feature-bullets")
    string_throw = "This fits your\xa0.\n" \
                   "     Enter your model number\nto make sure this fits.\n" \
                   "    P.when(\"ReplacementPartsBulletLoader\").execute(function(module){ module.initializeDPX(); })"
    string_throw2 = "This fits your\xa0.\n     Enter your model number\nto make sure this fits.\n \n"
    feature_text = feature.get_text().replace("\t", "").replace("\n\n\n", "").replace("'", "\'"). \
        replace(string_throw, "").replace(string_throw2, "").lstrip()

    # From the manufacturer
    manufacturer = soup_detail.find(text="From the manufacturer")
    if manufacturer is not None:
        manufacturer_text = manufacturer.parent.parent.get_text().replace("\t", "").replace("\n\n\n", "").replace("'",
                                                                                                                  "\'")
    else:
        manufacturer_text = ""

    # 中部Production Description
    description = soup_detail.find(id="productDescription")
    if description is not None:
        description_txt = description.get_text().replace("'", "\'")
    else:
        description_txt = ""

    # 中部Product information
    information = soup_detail.find(id="prodDetails")
    if information is not None:
        information_txt = information.get_text().replace("'", "\'")
    else:
        information_txt = ""

    # 中部Important information
    important = soup_detail.find(id="important-information_feature_div")
    if important is not None:
        important_text = important.get_text().replace("'", "\'")
    else:
        important_text = ""

    detail_txt = feature_text + manufacturer_text + description_txt + information_txt + important_text

    # 多线程情况下的返回参数，因为python多线程不支持修改全局变量，所以绕了一绕
    x = {
        'id': i,
        'detail': detail_txt
    }
    print(str(i) + " finish")
    return x


# 获取内容，单独作为函数是为了超时重连
def get_response(i, option):
    try:
        if option == 1:
            response = requests.get(i, headers=my_headers, timeout=10)
        else:
            response = requests.get(i, headers=my_headers, timeout=3)
    except:
        return None
    else:
        return response


# 对特定url进行修改，同时剪裁url至最简
def check_url(url):
    if url[0:4] == "/gp/":
        url = url.split("=")[4].replace("%3A", ":").replace("%2F", "/")
    return url.split("/ref")[0]


# 获取列表页，keyword为关键词，自行修改

items = []


def spider(page):
    url_str = "https://www.amazon.com/s/ref=nb_sb_noss?url=search-alias%3Daps&field-keywords="
    key = "cellphone"
    # 超时重连
    print(url_str + key + "&page=" + str(page))
    response = get_response(url_str + key + "&page=" + str(page), 1)
    while response is None:
        print("page" + str(page) + "failed, retry")
        response = get_response(url_str + key + "&page=" + str(page), 1)

    soup = BeautifulSoup(response.text, 'lxml')
    item = soup.select("[class=s-item-container]")
    # 主要爬虫部分
    for i in item:
        x = i.find("a", "a-link-normal s-access-detail-page s-color-twister-title-link a-text-normal")
        if x is None:
            continue
        # print(x.get("title"))
        url = check_url(x.get("href"))
        rank_tag = i.find("a", "a-popover-trigger a-declarative")

        if rank_tag is not None:
            rank = rank_tag.get_text().split()[0]
        else:
            rank = 0

        img = i.find("img", "s-access-image cfMarker").get("src")

        price_tag = i.find("span", "a-color-base sx-zero-spacing")
        if price_tag is None:
            price_tag = i.find(text=re.compile(r"\$(\s\w+)?"))
            if price_tag is None:
                continue
            price = price_tag.parent.get_text()
        else:
            price = price_tag.get("aria-label")
            price_split = price.split()
            price = price_split[0]
        price = price.replace(",", "")

        data = {
            'id': url.split("/")[5],
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
    process = []
    detail = {}
    print(items)
    for i in range(len(items)):
        process.append(pool.apply_async(get_detail, (i,)))
        # detail.append(get_detail(i))
    pool.close()
    pool.join()

    # 接受多线程运行传回的细节内容
    for res in process:
        temp = res.get()
        detail[temp['id']] = temp['detail']

    # 将细节存入items的detail中，同时编写sql语句
    for i in range(len(items)):
        items[i]['detail'] = detail[i]
        print(items[i]['detail'])
        # print()
        placeholder = ", ".join(["%s"] * len(items[i]))

        stmt = "replace into {table} ({columns}) values ({values});".format(table="item",
                                                                            columns=",".join(items[i].keys()),
                                                                            values=placeholder)
        print(stmt, list(items[i].values()))
        cursor.execute(stmt, list(items[i].values()))
    # 经过测试，采用多线程比直接通过循环快了100%还多
    # time.sleep(2)
    print(items)
    db.commit()


# 多页面采集，python不支持多线程下嵌套的多线程（或许是我太垃圾 逃
# 所以只能用循环一页一页搞了 被亚马逊查到也没辙了，可以改一下timeout看看
for page in range(1, 10):
    spider(page)
    items = []

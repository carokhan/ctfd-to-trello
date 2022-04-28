from trello import TrelloClient
import yaml
import os
import requests
import re
from requests import Session
from requests.compat import urljoin
import random
from tqdm import tqdm

def login(config, session):
    nonceres = session.get(urljoin(config["domain"], '/login'))
    nonce = re.search('name="nonce"(?:[^<>]+)?value="([0-9a-f]{64})"', nonceres.text).group(1)
    res = session.post(urljoin(config["domain"], '/login'), data={"name": config["username"], "password": config["password"], "nonce": nonce}) 
    if "success" in session.get(config["domain"] + '/api/v1/users/me').text:
        print("Successful login!")
    elif 'incorrect' in res.text:
        print("Could not login - check credentials")
        os._exit(0)

def fetch(url, session):
	res = session.get(url)
	return res.json()['data']

with open('.secret.yaml') as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    
client = TrelloClient(api_key=data["TRELLO_API_KEY"], token=data["TRELLO_TOKEN"])
boards = client.list_boards()
for x in range(len(boards)):
    print(str(x) + " | " + boards[x].name)
board = int(input("Which board would you like to choose? "))
recentBoard = boards[board]

for card in recentBoard.all_cards():
    if card.name == "scraper_config":
        configCard = card
    
try:
    print("Found config! " + configCard.name)
except:
    print("No config found, quitting...")
    os._exit(0)

todict = [x.split(": ") for x in configCard.desc.split("\n")]
todict = [e for l in todict for e in l]
config = {todict[i]: todict[i+1] for i in range(0, len(todict), 2)}

session = Session()

login(config, session)
chals = fetch(urljoin(config["domain"], '/api/v1/challenges'), session)

result = []

for chal in tqdm(chals, desc="Scraping challenges"):
    res = fetch(urljoin(config["domain"], f'/api/v1/challenges/{chal["id"]}'), session)
    files = []
    if 'files' in res:
        files = res["files"]
    category = res["category"]
    name = res['name']
    points = str(res['value'])
    description = str(res['description']).replace('\r', '').replace('\n', '')
    result.append({"category": category, "name": name, "desc": description, "points": points, "id": chal["id"], "files": files})

for tag in tqdm(recentBoard.get_labels(), desc="Deleting existing labels"):
    recentBoard.delete_label(tag.id)

tags = [info["category"] for info in result]
tags = list(set(tags))
tagIds = {}
for tag in tqdm(tags, desc="Making new labels"):
    tagIds[tag] = recentBoard.add_label(tag, random.choice(("yellow", "purple", "blue", "red", "green", "orange", "black", "sky", "pink", "lime")))

unsolved = recentBoard.add_list("Not started", pos=1)
for chal in tqdm(result, "Uploading to Trello"):
    newchal = unsolved.add_card(chal["name"] + " - " + str(chal["points"]), desc=chal["desc"])
    for filen in chal["files"]:
        url = str(config["domain"]) + filen
        try:
            size = int(requests.head(url).headers["content-length"])
        except KeyError:
            resp = requests.get(url)
            size = len(resp.content)
        if int(size) // (1024*1024) <= 10:
            fileresp = requests.get(url, allow_redirects=True)
            filename = os.path.basename(fileresp.url).split("?")[0]
            currentdir = os.path.dirname(os.path.abspath(__file__))
            path_file = '%s/%s'%(currentdir,filename)
            with open(path_file, 'wb+') as f:
                f.write(fileresp.content)
            newchal.attach(file=open(path_file, 'rb'))
            os.remove(path_file)
            
        else:
            newchal.attach(url=urljoin(config["domain"], str(f)))
    newchal.add_label(tagIds[chal["category"]])

recentBoard.add_list("Solving", pos=2)
recentBoard.add_list("Solved!", pos=3)





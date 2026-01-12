import os
import time

CONFIG_PATH="/config"
SHOW_PATH="/tvshows"

with open(os.path.join(CONFIG_PATH, "test.txt"), "w") as file:
    file.write("Your text goes here")
    print("file made")

username = os.environ['USERNAME']
password = os.environ['PASSWORD']
url = os.environ['URL']

print("-{}-{}-{}-".format(username, password, url))
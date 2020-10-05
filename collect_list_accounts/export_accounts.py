#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from __future__ import print_function
from builtins import str
import json, sys
from datetime import datetime
from pymongo import MongoClient
from config import MONGO_DATABASE

db = MongoClient("localhost", 27017)[MONGO_DATABASE]['users']

headers = ["Nom", "Prénom", "Type", "Compte twitter", "id", "name", "screen_name", "created_at", "time_zone", "utc_offset", "protected", "verified", "url", "lang",  "description", "statuses_count", "favourites_count", "followers_count", "following", "friends_count", "listed_count", "geo_enabled", "has_extended_profile", "is_translation_enabled", "is_translator", "contributors_enabled", "default_profile", "default_profile_image", "profile_background_color", "profile_background_image_url", "profile_background_image_url_https", "profile_background_tile", "profile_image_url", "profile_image_url_https", "profile_link_color", "profile_location", "profile_sidebar_border_color", "profile_sidebar_fill_color", "profile_text_color", "profile_use_background_image"]

format_txt = lambda x: '"' + x.replace('"', '""').replace("\n", " ").replace("\r", "") + '"'
format_spe = lambda x: str(x).lower() if x else ""
format_field = lambda x: format_txt(x) if type(x) == str else format_spe(x)

print((",".join(headers)))
for t in db.find(sort=[("_id", 1)]):
    t["created_at"] = datetime.strptime(t['created_at'], '%a %b %d %H:%M:%S +0000 %Y').isoformat()
    print(",".join([format_field(t.get(str(a), "")) for a in headers]))


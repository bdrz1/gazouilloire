import os
import sys
import json
import calendar
from elasticsearch import Elasticsearch, helpers, exceptions
from datetime import datetime, timedelta
import dateutil.relativedelta
from twitwi.constants import FORMATTED_TWEET_DATETIME_FORMAT
import itertools
from gazouilloire.config_format import log

try:
    with open(os.path.join(os.path.dirname(__file__), "db_mappings.json"), "r") as db_mappings:
        DB_MAPPINGS = json.loads(db_mappings.read())
        # ensure intended mappings are there
        for key in ["tweet", "link"]:
            DB_MAPPINGS[key + "s_mapping"]["mappings"]["properties"]
except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
    print("ERROR - Could not open db_mappings.json: %s %s" % (type(e), e))
    sys.exit(1)


def reformat_elastic_document(doc):
    res = dict(doc["_source"])
    res["_id"] = doc["_id"]
    return res


def chunks(iterator, n):
    """
    generates chunks/batches of size n from an iterator
    """
    for first in iterator:
        yield itertools.chain([first], itertools.islice(iterator, n - 1))


def add_and_report(sett, val):
    """
    Add val to sett and check if val was already part of sett
    :param sett: set of tweet ids
    :param val: new tweet id
    :return: bool
    """
    leng = len(sett)
    sett.add(val)
    return len(sett) != leng


def format_response(response, single_result=False):
    """Formats the ES find() response into a list of dictionaries"""
    if response["hits"]["total"] == 0:
        if single_result:
            return None
        return []
    if single_result:
        return reformat_elastic_document(response["hits"]["hits"][0])
    return [reformat_elastic_document(element) for element in response["hits"]["hits"]]


def format_tweet_fields(tweet):
    """Adapts the fields of the given tweet to fit the index mapping"""
    elastic_tweet = {}
    for key in DB_MAPPINGS["tweets_mapping"]["mappings"]["tweet"]["properties"]:
        elastic_tweet[key] = tweet.get(key, None)
    if not elastic_tweet["deleted"]:
        elastic_tweet["deleted"] = False
    if elastic_tweet["coordinates"]:
        elastic_tweet["coordinates"] = elastic_tweet["coordinates"].get(
            'coordinates', None)
    return elastic_tweet


def prepare_db(host, port, db_name, multi_index=False):
    try:
        db = ElasticManager(host, port, db_name, multi_index=multi_index)
        if multi_index:
            db_exists = db.exists(db.tweets + "*")
        else:
            db_exists = db.exists(db.tweets)
    except Exception as e:
        sys.stderr.write(
            "ERROR: Could not initiate connection to database: %s %s" % (type(e), e))
        sys.exit(1)
    if db_exists:
        return db
    else:
        sys.stderr.write(
            "ERROR: elasticsearch index %s does not exist" % db_name
        )


def get_month(day):
    return datetime.strftime(day, "_%Y_%m")


class ElasticManager:

    def __init__(self, host, port, db_name, multi_index=False, nb_past_months=None, links_index=None):
        self.host = host
        self.port = port
        self.multi_index = multi_index
        self.nb_past_months = nb_past_months
        self.current_month = get_month(datetime.now())
        self.db_name = db_name.replace(" ", "_")
        self.client = Elasticsearch(
            host + ":" + str(port),
            retry_on_timeout=True,
            timeout=30
        )
        self.tweets = self.db_name + "_tweets"
        if links_index:
            self.links = links_index
        else:
            self.links = self.db_name + "_links"

    def exists(self, doc_type):
        """
        Check if index already exists in elasticsearch
        """
        return self.client.indices.exists(index=doc_type)

    def get_index_name(self, day):
        return self.tweets + get_month(day)

    def get_sorted_indices(self):
        return sorted([
            index["index"] for index in self.client.cat.indices(
                index=self.tweets + "_*", format="json"
            ) if int(index["docs.count"]) > 0 and index["status"] == "open"
        ])

    def get_positional_index(self, position):
        if not self.multi_index:
            log.error("Multi-index is not activated, you should not use the --index option")
            sys.exit(1)

        opened_indices = self.get_sorted_indices()

        if position == "last":
            return opened_indices[-1]

        if position == "first":
            return opened_indices[0]

        if position == "inactive":
            if self.nb_past_months is None:
                log.error("since 'nb_past_months' is not parametered in config.json, all indices are active")
                sys.exit(1)
            else:
                last_inactive = datetime.now() - dateutil.relativedelta.relativedelta(months=self.nb_past_months+1)
                last_inactive = self.get_index_name(last_inactive)
                if last_inactive in opened_indices:
                    return last_inactive
                else:
                    log.error("Index is already closed or deleted")
                    sys.exit(1)

    def create_index(self, index_name, mapping):
        if not self.exists(index_name):
            self.client.indices.create(index=index_name, body=mapping)

    def prepare_indices(self):
        """
        Check if indices exist, if not, create them
        """
        if self.multi_index:
            one_month_in_advance = datetime.now() + dateutil.relativedelta.relativedelta(months=1)
            if self.nb_past_months:
                nb_past_months = self.nb_past_months + 2
            else:
                twitter_creation_date = datetime(2006, 3, 21)
                time_diff_years = one_month_in_advance.year - twitter_creation_date.year
                time_diff_months = one_month_in_advance.month - twitter_creation_date.month
                nb_past_months = time_diff_years * 12 + time_diff_months + 1
            for i in range(nb_past_months):
                index_name = self.get_index_name(one_month_in_advance - dateutil.relativedelta.relativedelta(months=i))
                self.create_index(index_name, DB_MAPPINGS["tweets_mapping"])
        else:
            self.create_index(self.tweets, DB_MAPPINGS["tweets_mapping"])

        self.create_index(self.links, DB_MAPPINGS["links_mapping"])

    def delete_index(self, doc_type):
        """
        Check if index exists, if so, delete it.
        In case of multi_index, delete all indices with the name prefix.
        """
        index_name = getattr(self, doc_type)
        opened_indices = self.client.indices.get(index_name + "*")
        success = []
        if len(opened_indices) > 0:
            for index in opened_indices:
                success.append(self.client.indices.delete(index=index))
            if all(success):
                log.info("{} successfully deleted".format(index_name))
                return True
            else:
                for status, index_name in zip(success, opened_indices):
                    if not status:
                        log.error("failed to delete {}".format(index_name))
                return False
        log.warning("{} does not exist and could not be deleted".format(index_name))
        return False

    def close_index(self, index_name, delete, log_message):
        """
        Close or delete one specific index (with the month suffix).
        """
        if self.exists(index_name):
            if delete:
                success = self.client.indices.delete(index_name).get("acknowledged", False)
            else:
                success = self.client.indices.close(index_name).get("acknowledged", False)
            if success:
                log.info("{} successfully {}d".format(index_name, log_message))
            else:
                log.error("failed to {} {}".format(log_message, index_name))
        else:
            log.warning("{} does not exist and could not be {}d".format(index_name, log_message))

    def close_indices(self, indices, delete=False, force=False):
        """
        "Close all indices older than self.nb_past_months or close specific indices"
        """
        log_message = "delete" if delete else "close"
        now = datetime.now()
        if self.multi_index:
            for index in indices:
                try:
                    year, month = index.replace(self.db_name + "_tweets_", "").split("_")
                    last_day_of_month = datetime(
                        int(year),
                        int(month),
                        calendar.monthrange(int(year), int(month))[1],
                        now.hour,
                        now.minute,
                        now.second
                    )
                except ValueError:
                    log.error("indices should be in format YYYY-MM")
                    sys.exit(1)

                index_name = self.get_index_name(last_day_of_month)
                if self.is_too_old(last_day_of_month) or force == True:
                    self.close_index(index_name, delete, log_message)
                else:
                    log.warning("{} may contain tweets posted less than {} months ago, use --force option if you want "
                                "to {} it anyway.".format(index_name, self.nb_past_months, log_message))
        else:
            self.close_index(indices, delete, log_message)

    def prepare_indexing_links(self, links):
        """Yields an indexing action for every link of a list"""
        for l in links:
            yield {
                '_index': self.links,
                "_op_type": "index",
                '_source': l
            }

    def prepare_indexing_tweets(self, tweets):
        """Yields an indexing action for every tweet of a list. For existing tweets, only some fields are updated."""
        if self.multi_index and get_month(datetime.now()) != self.current_month:
            self.prepare_indices()
            self.current_month = get_month(datetime.now())
        index = self.tweets
        for tweet in tweets:
            t = tweet.copy()
            reply_count = t.get("reply_count", None)
            if self.multi_index:
                tweet_date = tweet_date = datetime.strptime(t["local_time"], FORMATTED_TWEET_DATETIME_FORMAT)
                if self.nb_past_months and self.is_too_old(tweet_date):
                    continue
                index = self.get_index_name(tweet_date)
            if reply_count is not None:
                source = "ctx._source.match_query |= params.match_query; \
                    ctx._source.retweet_count = params.retweet_count; \
                    ctx._source.reply_count = params.reply_count; \
                    ctx._source.favorite_count = params.favorite_count; \
                    if (!ctx._source.collected_via.contains(params.collected_via)){ctx._source.collected_via.add(params.collected_via)}"
            else:
                source = "ctx._source.match_query |= params.match_query; \
                    ctx._source.retweet_count = params.retweet_count; \
                    ctx._source.favorite_count = params.favorite_count; \
                    if (!ctx._source.collected_via.contains(params.collected_via)){ctx._source.collected_via.add(params.collected_via)}"
            yield {
                '_index': index,
                "_op_type": "update",
                "_id": t.pop("id"),
                "script": {
                    "source": source,
                    "lang": "painless",
                    "params": {
                        "collected_via": t["collected_via"][0],
                        "match_query": t["match_query"],
                        "retweet_count": t["retweet_count"],
                        "reply_count": reply_count,
                        "like_count": t["like_count"],
                    }

                },
                "upsert": t
            }

    def prepare_updating_links_in_tweets(self, links):
        """Yields an update action for the links of every tweet in the list"""
        for l in links:
            l.update({
                "_op_type": "update"
            })
            yield l

    def set_deleted(self, tweet_id):
        """Sets the field 'deleted' of the given tweet to True"""

        opened_indices = self.client.indices.get(self.tweets + "*")
        success = []
        for index in opened_indices:
            try:
                self.client.update(index=index, id=tweet_id,
                                                   body={"doc": {"deleted": True}, "doc_as_upsert": False})
                success.append(True)
                break
            except exceptions.NotFoundError:
                success.append(False)
                continue
        if not any(success):
            log.debug("tweet {} was not found while trying to mark it as deleted".format(tweet_id))

    def find_tweet(self, tweet_id):
        """Returns the tweet corresponding to the given id"""
        opened_indices = self.client.indices.get(self.tweets + "*")
        for index in opened_indices:
            try:
                response = self.client.get(
                    index=index,
                    id=tweet_id
                )
                return response
            except exceptions.NotFoundError:
                continue
        return None

    def is_too_old(self, date):
        min_date = datetime.now() - dateutil.relativedelta.relativedelta(months=self.nb_past_months)
        return date < min_date

    def get_urls(self, url_list):
        """Returns the urls corresponding to the given url_list.
            this method is designed to replace find_links_in when the url will become the _id in elasticsearch db
        """
        response = self.client.mget(
            index=self.links,
            doc_type="link",
            body={'ids': url_list}
        )
        return response

    def find_tweets_with_unresolved_links(self, batch_size=600, retry_days=30):
        """Returns a list of tweets where 'links_to_resolve' field is True"""
        query = {"bool": {"filter": [{"term": {"links_to_resolve": True}}]}}
        if retry_days:
            range_clause = {"range": {"timestamp_utc": {"gte":
                                                            str((datetime.now() - timedelta(
                                                                days=retry_days)).timestamp())
                                                        }
                                      }
                            }
            query["bool"]["filter"].append(range_clause)
        response = self.client.search(
            index=self.tweets + "*",
            body={
                "_source": ["links", "proper_links", "retweet_id", "local_time"],
                "size": batch_size,
                "query": query
            }
        )
        return format_response(response)

    def find_links_in(self, urls_list, batch_size):
        """Returns a list of links which ids are in the 'urls_list' argument"""
        response = self.client.search(
            index=self.links,
            size=batch_size,
            body={
                "query": {
                    "bool": {
                        "filter": {
                            "terms": {
                                "link_id": urls_list

                            }
                        }
                    }
                }
            }
        )

        return format_response(response)

    def insert_link(self, link, resolved_link):
        """Inserts the given link in the database"""
        self.client.index(index=self.links,
                          body={"link_id": link, "real": resolved_link})

    def prepare_indexing_tweets_with_new_links(self, tweets, links, domains):
        index = self.tweets
        for t in tweets:
            if self.multi_index:
                index = self.get_index_name(
                    datetime.strptime(t["_source"]["local_time"], FORMATTED_TWEET_DATETIME_FORMAT)
                )
            t["_source"]["proper_links"] = links
            t["_source"]["domains"] = domains
            t["_source"]["links_to_resolve"] = False
            yield {
                '_index': index,
                "_op_type": "index",
                '_source': t["_source"],
                "_id": t["_id"]
            }

    def update_retweets_with_links(self, tweet_id, links, domains):
        """Adds the resolved links to the corresponding tweets"""
        query = {
            "term": {
                "retweet_id": tweet_id
            }
        }
        response = helpers.scan(
            client=self.client,
            index=self.tweets + "*",
            query={"query": query}
        )

        helpers.bulk(self.client, actions=self.prepare_indexing_tweets_with_new_links(response, links, domains))

    def count_tweets(self, key, value):
        """Counts the number of documents where the given key is equal to the given value"""
        return self.client.count(index=self.tweets + "*", body={"query": {"term": {key: value}}})['count']

    def search_thread_elements(self, ids_list):
        """
        Elasticsearch query on which get_thread_ids_from_ids is based
        """
        body = {
            "_source": "to_tweetid",
            "query": {
                "bool": {
                    "filter": [{
                        "bool": {
                            "should": [
                                {"terms": {"_id": ids_list}},
                                {"terms": {"to_tweetid": ids_list}}
                            ]
                        }
                    }]
                }
            }
        }
        response = helpers.scan(
            client=self.client,
            index=self.tweets + "*",
            query=body
        )
        return response

    def get_thread_ids_from_ids(self, ids):
        """
        Find ids of all tweets that are part of the same conversations as the tweets in ids
        :param ids: list of tweet ids
        :return:
        """
        ids_list = list(set(ids))
        all_ids = set(ids)
        while ids_list:
            todo_ids = set()
            for t in self.search_thread_elements(ids_list):
                if add_and_report(all_ids, t["_id"]):
                    todo_ids.add(t["_id"])
                origin = t.get("to_tweetid")
                if origin and add_and_report(all_ids, origin):
                    todo_ids.add(origin)
            ids_list = list(todo_ids)
        return list(all_ids)

    def multi_get(self, ids, batch_size=1000):
        # todo: currently in error with multiindex
        for i in range(0, len(ids), batch_size):
            batch = self.client.mget(body={'ids': ids[i:i + batch_size]}, index=self.tweets)
            for tweet in batch["docs"]:
                yield tweet


def bulk_update(client, actions):
    # Adapted code from elasticsearch's helpers.bulk method to return the
    # details of new elements from bulk updates
    success, created = 0, 0
    errors = []

    for ok, item in helpers.streaming_bulk(client, actions, yield_ok=True):
        if not ok:
            errors.append(item)
        else:
            if item["update"]["result"] == "created":
                created += 1
            success += 1

    return success, created, errors


if __name__ == "__main__":
    es = ElasticManager("localhost", 9200, "gazouilloire")
    es.prepare_indices()
    print(es.tweets)

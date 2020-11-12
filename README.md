# Gazouilloire

Twitter stream + search API grabber handling various config options such as collecting only during specific time periods, or limiting the collection to some locations.

Python 3.x compatible.

## HowTo

- Install gazouilloire
    ```bash
    git clone https://github.com/medialab/gazouilloire.git
    cd gazouilloire
    git checkout elasticPy3-merge
    python setup.py install
    ```

- Install [Elasticsearch](https://www.elastic.co/downloads/elasticsearch#ga-release) (version 6.X)

- Init gazouilloire collection in a specific directory
    ```bash
    gazouilloire init path/to/collection/directory'
    ```
or in the current directory

    ```bash
    gazouilloire init
    ```
a `config.json` file is created. Open it to configure the collection parameters.

- Set your [Twitter API key](https://apps.twitter.com/app/) and generate the related Access Token

    ```json
    "twitter": {
       "key": "<Consumer Key (API Key)>xxxxxxxxxxxxxxxxxxxxx",
       "secret": "<Consumer Secret (API Secret)>xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
       "oauth_token": "<Access Token>xxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
       "oauth_secret": "<Access Token Secret>xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    }
    
    ```

- Write down the list of desired **keywords** and **@users** and/or the list of desired **url_pieces** as json arrays:

    ```json
    "keywords": [
        "amour",
        "@medialab_scpo"
    ],
    "url_pieces": [
        "medialab.sciencespo.fr/fr"
    ],
    ```

  Avoid using accented characters (Twitter will automatically return both tweets with and without accents, for instance searching "heros" will find both tweets with "heros" and "héros").

  Note that there are three possibilities to filter further:

  - **language**: in order to collect only tweets written in a specific language : just add `"language": "fr"` to the config (the language should be written in [ISO 639-1 code](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes))
  - **geolocalisation**: just add `"geolocalisation": "Paris, France"` field to the config with the desired geographical boundaries or give in coordinates of the desired box as shown in the config example file
  - **time_limited_keywords**: in order to filter on specific keywords during planned time period:

    ```json
    "time_limited_keywords": {
        "#m6": [
            ["2014-05-01 16:00", "2014-05-08 16:05"],
            ["2014-05-08 16:00", "2014-05-08 16:05"],
            ["2014-05-15 16:00", "2014-05-08 16:05"],
            ["2014-05-22 16:00", "2014-05-08 16:05"]
        ],
        "bieber": [
            ["2014-05-08 16:00", "2014-05-08 16:05"]
        ]
    },
    ```
  One can also choose the analyzer used by Elasticsearch to tokenize text:
    ```json
    "text_analyzer": "french",
    ```
  The complete list of analyzers is [here](https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-analyzers.html).


- Run with:

    ```bash
    gazouilloire start path/to/collection/directory
    ```
    or, to run the script in the current directory:
    ```
    gazouilloire start
    ```

- Data is stored in your ElasticSearch, which you can direcly query. But you can also export it easily in csv format:

    ```bash
    # Export all fields from all tweets:
    gazouilloire export
    # or
    gazou export
    ```

- By default, the `export` command writes in stdout. You can also use the -o option to write into a file:
    ```bash
    gazou export > my_tweets_file.csv
    # is equivalent to
    gazou export -o my_tweets_file.csv
    ```

- Other available options:
    ```bash      
    # Export a csv of all tweets having a specific word in their text:
    gazou export medialab
    
    # Export a csv of all tweets having one of many specific words in their text:
    gazou export medialab digitalhumanities datajournalism '#python'
  
    # Export only a selection of columns:
    gazouilloire export --columns/-c id,user_screen_name,local_time,links
    # or
    gazou export --select/-s id,user_screen_name,local_time,links
    
    # Exclude tweets from conversations or from quotes (i.e. that do not match the keywords defined in config.json)
    gazou export --exclude_threads
    
    # Export all tweets matching a specific Elasticsearch term query, for instance by user name:
    gazou export "{'user_screen_name': 'medialab_ScPo'}"
    ```

## Troubleshooting

- Elasticsearch

  - Remember to [set the heap size](https://www.elastic.co/guide/en/elasticsearch/reference/current/heap-size.html) (at 1GB by default) when moving to production. 1GB is fine for indices under 15-20 million tweets, but be sure to set a higher value for heavier corpora.
  
    Set these values here `/etc/elasticsearch/jvm.options` (if you use Elasticsearch as a service) or here `your_installation_folder/config/jvm.options` (if you have a custom installation folder):
    ```
    -Xms2g
    -Xmx2g
    ```
    Here the heap size is set at 2GB (set the values at `-Xms5g -Xmx5g` if you need 5GB, etc).

  - If you encounter this Elasticsearch error message:
    `max virtual memory areas vm.max_map_count [65530] is too low, increase to at least [262144]`:

    :arrow_right:  Increase the `max_map_count` value:

    ```bash
    sudo sysctl -w vm.max_map_count=262144
    ```

    ([source](https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html))

  - If you get a _ClusterBlockException_ `[SERVICE_UNAVAILABLE/1/state not recovered / initialized]` when starting Elasticsearch:

    :arrow_right:  Check the value of `gateway.recover_after_nodes` in _/etc/elasticsearch/elasticsearch.yml_:

    ```bash
    sudo [YOUR TEXT EDITOR] /etc/elasticsearch/elasticsearch.yml
    ```

    Edit the value of **`gateway.recover_after_nodes`** to match your number of nodes (usually `1` - easily checked here : *http://host:port/_nodes*).

## Publications using Gazouilloire

- RICCI, Donato, COLOMBO, Gabriele, MEUNIER, Axel, et al. [Designing Digital Methods to monitor and inform Urban Policy. The case of Paris and its Urban Nature initiative](https://re.public.polimi.it/bitstream/11311/1038509/1/IPPA_Ricci-Colombo-Meunier-Brilli.pdf). In : 3rd International Conference on Public Policy (ICPP3)-Panel T10P6 Session 1 Digital Methods for Public Policy. SGP, 2017. p. 1-37.

- DOUAY, Nicolas, REYS, Aurélien, ROBIN, Sabrina. [L’usage de Twitter par les maires d’Île-de-France](https://journals.openedition.org/netcom/2089). NETCOM, 29-3/4 | 2015 : Visualisation des réseaux, de l’information et de l’espace, p. 275-296.

- ANTOLINOS-BASSO Diégo, PADDEU Flaminia, DOUAY Nicolas, BLANC Nathalie. [Pourquoi le débat #EuropaCity n’a pas pris sur Twitter ?](https://journals.openedition.org/reset/1070). RESET, 7 | 2018. DOI : 10.4000/reset.1070


## Publications talking about Gazouilloire

- JULLIARD, Virginie. [#Theoriedugenre: comment débat-on du genre sur Twitter ?](https://www.cairn.info/revue-questions-de-communication-2016-2-page-135.html). Questions de communication, 2016, no 2, p. 135-157.

- BOTTINI, Thomas et JULLIARD, Virginie. [Entre informatique et sémiotique](https://www.cairn.info/revue-reseaux-2017-4-page-35.htm). Réseaux, 2017, no 4, p. 35-69.


## Credits & License

[Benjamin Ooghe-Tabanou](https://github.com/boogheta), [Jules Farjas](https://github.com/farjasju) & al @ [Sciences Po médialab](https://github.com/medialab)

Read more about Gazouilloire's migration from Python2 & Mongo to Python3 & ElasticSearch in [Jules' report](https://github.com/farjasju/medialabInternshipReport).

Discover more of our projects at [médialab tools](http://tools.medialab.sciences-po.fr/).

This work is supported by [DIME-Web](http://dimeweb.dime-shs.sciences-po.fr/), part of [DIME-SHS](http://www.sciencespo.fr/dime-shs/) research equipment financed by the EQUIPEX program (ANR-10-EQPX-19-01).

Gazouilloire is a free open source software released under [GPL 3.0 license](LICENSE).

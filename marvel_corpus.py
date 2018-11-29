import re
import json
import requests
from scrapy.selector import Selector
from click import progressbar

from nltk.tokenize import word_tokenize
from nltk.tokenize import MWETokenizer
from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters
punkt_param = PunktParameters()
# FIX: define this set in some tidier way
punkt_param.abbrev_types = {'s.h.i.e.l.d', 'h.a.m.m.e.r', 'a.i.m', 'a.g.m', 'n.y.p.d', 'n.a.t.o', 'u.s.s.r', 's.t.r.i.k.e', 'u.l.t.i.m.a.t.u.m', 's.w.o.r.d', 'dr', 'mr', 'ms', 'mrs', 'u.s', 'u.s.a', 'u.n', 'u.k ', 'etc', 'st', 'col'}
sent_tokenizer = PunktSentenceTokenizer(punkt_param)
mwe_tokenizer = MWETokenizer()

basepath = 'http://marvel.wikia.com/'


def get_characters_list():

    params = {'limit': 25000,
              'category': 'Earth-616_Characters'}

    return requests.get(basepath + 'api/v1/Articles/List/',
                        params=params).json()['items']


# TODO: avoid nearly repeating get_characters_list()
def get_others_list():

    params = {'limit': 10000,
              'category': 'Earth-616'}

    return requests.get(basepath + 'api/v1/Articles/List/',
                        params=params).json()['items']


def load_page_list(page_list_path):
    """To load from stored local page lists (and be nice to Wikia servers)"""
    return json.load(open(page_list_path))['items']


class Details():

    def __init__(self, url, article_id):

        self.url = url
        self.html = None
        self.sel = None
        self.name = ''
        self.content = ''

        self.fetch_html()
        self.create_selector()

        self.set_article_id(article_id)
        self.set_name()
        self.set_content()

    def fetch_html(self):
        self.html = requests.get(basepath + self.url).text

    def create_selector(self):
        self.sel = Selector(text=self.html)

    def set_article_id(self, article_id):
        self.article_id = article_id

    def set_name(self):
        title_xpath = '//div[contains(@class, "header-title")]/h1/text()'
        self.name = self.sel.xpath(title_xpath).extract_first()
        self.name = self.name.replace(' (Earth-616)', '')

    def set_content(self):

        for scope in self.sel.xpath('//div[@id="WikiaArticle"]/*/p'):
            text_parts = scope.xpath('.//text()').extract()
            text_parts = [part.strip() for part in text_parts]

            self.content += '%s\n' % ' '.join(text_parts)

            text_links = scope.xpath('./a/text()').extract()
            list(map(mwe_tokenizer.add_mwe, [l.split() for l in text_links]))

        # remove reference indicators
        self.content = re.sub(r'\[\d+\]', '',
                              self.content,
                              flags=re.MULTILINE)
        # remove URLs
        self.content = re.sub(r'^https?:\/\/.*[\r\n]*', '',
                              self.content,
                              flags=re.MULTILINE)

        # tokenize content
        content_tokenized = []
        for sent in sent_tokenizer.tokenize(self.content):
            # only include lines with more than two words
            sent_tokens = word_tokenize(sent)
            if len(sent_tokens) > 2:
                # join known mwes
                sent_mwes = mwe_tokenizer.tokenize(sent_tokens)
                sent_normalized = ' '.join(sent_mwes)
                content_tokenized.append(sent_normalized)
        content_normalized = '\n'.join(content_tokenized)
        self.content = content_normalized

        # some rules to fix munged tokenization
        self.content = re.sub(r'_ ', ' ',
                              self.content,
                              flags=re.MULTILINE)

        self.content = re.sub(r' \. ', ' ',
                              self.content,
                              flags=re.MULTILINE)

        self.content = re.sub(r'\s-(\w)', r'-\1',
                              self.content,
                              flags=re.MULTILINE)

    def dump(self, path='marvel.txt'):

        if len(self.content) == 0:
            return False

        with open(path, 'a') as f:
            f.write('%d\n' % self.article_id)
            f.write('%s\n' % self.name)
            f.write('%s\n' % self.content)
            f.write('\n')


def main():

    dump_path = 'marvel.txt'

    # reset dump
    open(dump_path, 'w').close()

    refs = []
    refs.extend(get_others_list())
    refs.extend(get_characters_list())

    # clean titles (mostly names) to recognize as mwes
    r = re.compile(r'\(.*\)')
    names = [r.sub('', ref['title']).strip() for ref in refs]
    list(map(mwe_tokenizer.add_mwe, [name.split() for name in names]))

    with progressbar(refs) as bar:
        for ref in bar:
            details = Details(ref['url'], ref['id'])
            details.dump(dump_path)

if __name__ == '__main__':
    main()
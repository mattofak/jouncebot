from lxml import etree
import dateutil.parser
from threading import Timer
from datetime import datetime
import math
import pytz

class DeployPage:
    #: mwclient.Site mwcon: Connection to MediaWiki server that hosts the deployment calendar
    mwcon = None
    page = ""
    logger = None
    update_interval = 1

    notify_callback = None
    notify_timer = None
    update_timer = None

    deploy_items = {}

    page_url = ''

    def __init__(self, mwcon, page, logger, update_interval = 15):
        """ Create a DeployPage object
        :param mwclient.Site mwcon: Connection to MediaWiki server that hosts :param page
        :param string page: Title of page that hosts the deployment calendar
        :param int update_interval: Number of minutes between requests for the deployment page
        """
        self.mwcon = mwcon
        self.page = page
        self.logger = logger
        self.update_interval = update_interval

        # Things I hate about the MW API right here...
        # This is getting the full URL of the deployments page so we can create
        # nice links in IRC messages
        page_url_result = mwcon.api('query', **{'titles':'Deployments', 'prop':'info','inprop':'url'})
        self.page_url = page_url_result['query']['pages'][page_url_result['query']['pages'].keys()[0]]['fullurl']

    def start(self, notify_callback):
        """Start all the various timers"""
        self.notify_callback = notify_callback
        self._reparse_on_timer()

    def stop(self):
        if self.notify_timer:
            self.notify_timer.cancel()
        if self.update_timer:
            self.update_timer.cancel()

    def reparse(self, set_timer = False):
        deploy_items = {}

        def stringify_children(node):
            from lxml.etree import tostring
            from itertools import chain
            parts = ([node.text] +
                    list(chain(*(stringify_children(c) for c in node.getchildren()))) +
                    [node.tail])
            # filter removes possible Nones in texts and tails
            return ''.join(filter(None, parts))

        self.logger.debug("Collecting new deployment information from the server")
        tree = etree.fromstring(self._get_page_html(), etree.HTMLParser())
        for item in tree.xpath('//tr[@class="deploycal-item"]'):
            id = item.get('id')
            times = item.xpath('td/span[@class="deploycal-time-utc"]/time')
            start_time = dateutil.parser.parse(times[0].get('datetime'))
            end_time = dateutil.parser.parse(times[1].get('datetime'))
            window = stringify_children(item.xpath('td/span[@class="deploycal-window"]')[0]) \
                .replace("\n", " ") \
                .strip()
            owners = map(lambda x: x.text, item.xpath('td/span[@class="ircnick"]/tt'))

            item_obj = DeployItem(id, '%s#%s' % (self.page_url, id), start_time, end_time, window, owners)

            if start_time in deploy_items:
                deploy_items[start_time].append(item_obj)
            else:
                deploy_items[start_time] = [item_obj]

        self.logger.debug("Got %s items" % len(deploy_items))
        self.deploy_items = deploy_items

        if set_timer:
            self._set_deploy_timer()

        return deploy_items


    def get_events(self):
        return self.deploy_items

    def get_current_events(self):
        pass

    def get_next_events(self):
        """What are the first set of DeployEvents in the future"""
        ctime = datetime.now(pytz.utc)
        nexttime = None
        for time in sorted(self.deploy_items.keys()):
            if ctime < time:
                nexttime = time
                break

        if nexttime:
            return self.deploy_items[nexttime]
        else:
            return []

    def _get_page_html(self):
        try:
            return self.mwcon.parse(self.mwcon.pages[self.page].edit())['text']['*']
        except Exception as ex:
            self.logger.error("Could not fetch page due to exception: " + repr(ex))
            return ""

    def _reparse_on_timer(self):
        self.reparse(set_timer = True)
        if self.update_timer:
            self.update_timer.cancel()

        self.update_timer = Timer(self.update_interval * 60, self._reparse_on_timer)
        self.update_timer.start()

    def _set_deploy_timer(self):
        next_events = self.get_next_events()
        if len(next_events) > 0:
            td = math.floor((next_events[0].start - datetime.now(pytz.utc)).total_seconds())
            if self.notify_timer:
                self.notify_timer.cancel()

            self.logger.debug( "Setting deploy timer to %s for %s" % (td, next_events[0]))
            self.notify_timer = Timer(td, self._on_deploy_timer, next_events)

    def _on_deploy_timer(self, events):
        self.notify_callback(events)
        self._set_deploy_timer()


class DeployItem:
    def __init__(self, id, url, start, end, window, owners):
        self.id = id
        self.url = url
        self.start = start
        self.end = end
        self.window = window
        self.owners = owners

    def __repr__(self):
        return "%s: (%s -> %s) %s; %s" % (
            self.id,
            self.start,
            self.end,
            self.window,
            ", ".join(self.owners)
        )
from lxml import etree
import dateutil.parser

class DeployPage:
    #: mwclient.Site mwcon: Connection to MediaWiki server that hosts the deployment calendar
    mwcon = None
    page = ""
    logger = None
    update_interval = 0

    page_url = ''

    callback = None

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
        page_url_result = mwcon.api('query', **{'titles':'Deployments', 'prop':'info','inprop':'url'})
        self.page_url = page_url_result['query']['pages'][page_url_result['query']['pages'].keys()[0]]['fullurl']

    def reparse(self):
        deploy_items = {}

        tree = etree.fromstring(self._get_page_html(), etree.HTMLParser())
        for item in tree.xpath('//tr[@class="deploycal-item"]'):
            id = item.get('id')
            times = item.xpath('td/span[@class="deploycal-time-utc"]/time')
            start_time = dateutil.parser.parse(times[0].attr('datetime'))
            end_time = dateutil.parser.parse(times[1].attr('datetime'))
            window = item.xpath('td/span[@class="deploycal-window"]')[0].text
            owners = map(lambda x: x.text, item.xpath('td/span[@class="ircnick"]/tt'))

            item_obj = DeployItem(id, '%s#%s' % (self.page_url, id), start_time, end_time, window, owners)

            if id in deploy_items:
                deploy_items[id].append(item_obj)
            else:
                deploy_items[id] = [item_obj]

        return deploy_items


    def get_events(self):
        pass

    def set_notify_callback(self, callback):
        self.callback = callback

    def _get_page_html(self):
        try:
            return self.mwcon.parse(self.mwcon.pages[self.page].edit())['text']['*']
        except Exception as ex:
            self.logger.error("Could not fetch page due to exception: " + repr(ex))
            return ""


class DeployItem:
    def __init__(self, id, url, start, end, window, owners):
        self.id = id
        self.url = url
        self.start = start
        self.end = end
        self.window = window
        self.owners = owners

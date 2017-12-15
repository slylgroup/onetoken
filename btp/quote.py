import asyncio
import aiohttp
import json

from .logger import log
from .model import Ticker


class Quote:
    def __init__(self, host=None):
        self.sess = None
        self.ws = None
        self.last_tick_dict = {}
        self.tick_queue = {}
        self.host = 'http://alihk-debug.qbtrade.org:3014/ws' if not host else host

    def error(self, e, msg):
        if self.sess:
            self.sess.close()

    async def init(self):
        log.debug(f'Connecting to {self.host}')

        try:
            self.sess = aiohttp.ClientSession()
            self.ws = await self.sess.ws_connect(self.host, autoping=False)
        except Exception as e:
            self.error(e, 'try connect to WebSocket failed...')
        else:
            log.debug('Connected to WS')

            asyncio.ensure_future(self.on_msg())

    async def on_msg(self):
        while not self.ws.closed:
            msg = await self.ws.receive()
            try:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # print(msg.data)
                    self.parse_tick(msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    log.debug('closed')
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.warning('error', msg)
                    break
            except Exception as e:
                log.warning('ws was disconnected...', e)

    # await ws.send_json({'uri': 'subscribe-single-tick-verbose', 'contract': 'btc.usd:xtc.bitfinex'})

    def parse_tick(self, plant_data):
        try:
            data = json.loads(plant_data)
            # print(data)
            if 'uri' in data and data['uri'] == 'single-tick-verbose':
                tick = Ticker.from_dict(data['data'])
                self.last_tick_dict[tick.contract] = tick
                if tick.contract in self.tick_queue:
                    self.tick_queue[tick.contract].put_nowait(tick)
        except:
            log.warning('parse error')

    async def subscribe_tick(self, contract, on_update=None):
        if self.ws:
            try:
                await self.ws.send_json({'uri': 'subscribe-single-tick-verbose', 'contract': contract})
            except Exception as e:
                log.warning(f'subscribe {contract} failed...', e)
            else:
                self.tick_queue[contract] = asyncio.Queue()
                if on_update:
                    asyncio.ensure_future(self.handle_q(contract, on_update))
        else:
            log.warning('ws is not ready yet...')

    async def handle_q(self, contract, on_update):
        while contract in self.tick_queue:
            q = self.tick_queue[contract]
            tk = await q.get()
            if on_update:
                if asyncio.iscoroutinefunction(on_update):
                    await on_update(tk)
                else:
                    on_update(tk)

    def get_last_tick(self, contract):
        return self.last_tick_dict.get(contract, None)
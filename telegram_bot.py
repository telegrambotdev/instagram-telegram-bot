import time

import peewee
import telepot
from InstagramAPI import InstagramAPI
from decouple import config
from telepot.delegate import (
    per_chat_id, create_open, pave_event_space, include_callback_query_chat_id)
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton

from models import Image
from upload_photos import download_photo, change_image_status

propose_records = telepot.helper.SafeDict()

try:
    Image.create_table()
except peewee.OperationalError:
    print('Tabela já existe')

image = None
login = InstagramAPI(config('USERNAME'), config('PASSWORD'))
login.login()


def post_on_instagram():
    global image

    # Upload Photo
    login.uploadPhoto(image.path, caption=image.caption, upload_id=None)
    print("Posted with caption {}".format(image.caption))


class GeneratePost(telepot.helper.ChatHandler):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Yes', callback_data='yes'),
        InlineKeyboardButton(text='No', callback_data='no'),
    ]])

    def __init__(self, *args, **kwargs):
        super(GeneratePost, self).__init__(*args, **kwargs)
        global propose_records
        if self.id in propose_records:
            self._count, self._edit_msg_ident = propose_records[self.id]
            self._editor = telepot.helper.Editor(self.bot,
                                                 self._edit_msg_ident) \
                if self._edit_msg_ident else None
        else:
            self._count = 0
            self._edit_msg_ident = None
            self._editor = None

    def _cancel_last(self):
        if self._editor:
            self._editor.editMessageReplyMarkup(reply_markup=None)
            self._editor = None
            self._edit_msg_ident = None

    def on__idle(self, event):
        self.sender.sendMessage('I know you may need a little time to decide.')
        self.close()

    def on_close(self, ex):
        # Save to database
        global propose_records
        propose_records[self.id] = (self._count, self._edit_msg_ident)

    def _propose(self):
        global image
        image = download_photo()

        post = "{} \n \n Caption: {} \n \n Do you want to post it?".format(
            image.url, image.caption)

        sent = self.sender.sendMessage(post, reply_markup=self.keyboard)
        self._editor = telepot.helper.Editor(self.bot, sent)
        self._edit_msg_ident = telepot.message_identifier(sent)

    def on_chat_message(self, msg):
        self._propose()

    def on_callback_query(self, msg):
        query_id, from_id, query_data = telepot.glance(msg,
                                                       flavor='callback_query')

        if query_data == 'yes':
            post_on_instagram()
            self.sender.sendMessage(
                'Image posted! Check it out at: https://www.instagram.com/{}/'
                .format(config('USERNAME')))
            change_image_status(image)
            self.close()
        else:
            self.bot.answerCallbackQuery(
                query_id, text='Alright! Lets try another picture.'
            )
            self._cancel_last()
            time.sleep(5)
            self._propose()


bot = telepot.DelegatorBot(config('TOKEN'), [
    include_callback_query_chat_id(
        pave_event_space())(
        per_chat_id(types=['private']), create_open, GeneratePost,
        timeout=10),
])

loop = asyncio.get_event_loop()
loop.create_task(MessageLoop(bot).run_forever())
print('Listening ...')

loop.run_forever()

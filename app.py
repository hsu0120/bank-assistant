import os
import openai
from flask import Flask, request

import requests
from bs4 import BeautifulSoup


from facebookbot import (
    FacebookBotApi, WebhookHandler
)

from facebookbot.models import (
    TextMessage, ImageMessage, VideoMessage, AudioMessage, 
    FileMessage, AttachmentMessage, LocationMessage, FallbackMessage,
    
    TextMessageEvent, AttachmentMessageEvent, GetStartedEvent, QuickReplyMessageEvent,
    PostbackEvent, LinkingEvent, UnLinkingEvent, TextEchoMessageEvent, AttachmentEchoMessageEvent,
    
    PostbackAction, URLAction, 
    TemplateSendMessage, ButtonsTemplate, GenericTemplate, MediaTemplate, 
    GenericElement, ImageElement, VideoElement,
    
    TextSendMessage, ImageSendMessage, VideoSendMessage, AudioSendMessage, FileSendMessage,
    LocationQuickReply, TextQuickReply,
    PostbackAction, URLAction, 
    ButtonsTemplate, TemplateSendMessage, GenericTemplate, GenericElement, ImageElement, VideoElement
)



app = Flask(__name__)

ACCESS_TOKEN = os.environ.get('PAGE_TOKEN')
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
CHATGPT_TOKEN = os.environ.get('CHATGPT_TOKEN')

fb_bot_api = FacebookBotApi(ACCESS_TOKEN)

handler = WebhookHandler()

openai.api_key = CHATGPT_TOKEN

# file = openai.File.create(file=open('example.jsonl'), purpose='fine-tune')
# print(file)

# print(openai.File.list())
# files = openai.File.list()['data']
# print(files)
# file_id = files[0].id

# model_classification = openai.FineTune.create(training_file=file_id, model='davinci')
# print(model_classification)

# print(openai.FineTune.list())
# models = openai.FineTune.list()['data']
# fine_tuned_model = models[0].fine_tuned_model
# print(fine_tuned_model)


category = '6'

data = dict()

@app.route('/')
def index():
    return '<p>Success</p>'

@app.route('/callback', methods=['GET'])
def verify():
    
    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.challenge'):
        
        if not request.args.get('hub.verify_token') == VERIFY_TOKEN:
            return 'Verification token mismatch', 403
        return request.args['hub.challenge'], 200

    return 'Hello world', 200


@app.route('/callback', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    body = request.get_json()
    handler.handle(body)
    
    return 'ok', 200


@handler.add(GetStartedEvent)
def handle_get_started(event):
    
    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(text='Welcome to this page/app...')
    )    
    
    # set welcome message   

@handler.add(TextMessageEvent)
def handle_text_message(event):
    
    time = event.timestamp / 1000
    
    text = event.message.text
    print(text)
    
    user_id = event.sender.id
    
    if user_id not in data.keys():
        data[user_id] = dict()
        data[user_id]['conversation_log'] = list()
    
    data[user_id]['conversation_log'].append(text)
    data[user_id]['last_time'] = time
        
    print(data)

#     category = openai.Completion.create(
#         model=fine_tuned_model,
#         prompt='Which category is this statement in: 玩',
#         max_tokens=4,
#         temperature=0
#     )['choices'][0]['text']

    # 外幣
    if category == '8':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '你要換算哪個外幣呢？',
                quick_replies = [
                    TextQuickReply(title='美元 US', payload='foreign_US'),
                    TextQuickReply(title='人民幣 CN', payload='foreign_CN'),
                    TextQuickReply(title='港幣 HK', payload='foreign_HK'),
                    TextQuickReply(title='日圓 JP', payload='foreign_JP'),
                    TextQuickReply(title='歐元 EU', payload='foreign_EU')
                ]          
            )
        )

    # 匯率
    if category == '6':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '請問你要查個別外幣匯率，還是要一次瀏覽多種外幣別呢？',
                buttons=[
                    URLAction(
                        title='查看所有幣別匯率',
                        url='https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates',
                        webview_height_ratio='full',
                        messenger_extensions=None,
                        fallback_url=None
                    ),
                    PostbackAction(
                        title='個別外幣匯率',
                        payload='currency'
                    )
                ]       
            )
        )          
    
#     response = openai.Completion.create(
#         model='text-davinci-003',
#         prompt=text,
#         max_tokens=64,
#         temperature=0.5,
#     )

#     while prediction >= 0.5:
#         response = openai.Completion.create(
#             model='text-davinci-003',
#             prompt='「' + response + '」換句話說',
#             max_tokens=64,
#             temperature=0.5,
#         )
    
#     fb_bot_api.push_message(
#         user_id, 
#         message=TextSendMessage(text=response['choices'][0]['text'])
#     )

@handler.add(QuickReplyMessageEvent) # quick reply action
def handle_quick_reply_message(event):

    time = event.timestamp / 1000

    text = event.message.text

    quick_reply_payload = event.message.quick_reply.payload
    
    user_id = event.sender.id

    data[user_id]['text'].append(text)
    data[user_id]['time'].append(time)

    # 外幣
    if quick_reply_payload.startswith('foreign_'):
        data[user_id]['status'] += 0.1
        
        if data[user_id]['status'] == 8.2:
            payload_buy = quick_reply_payload + 'buy'
            payload_sell = quick_reply_payload + 'sell'

            fb_bot_api.push_message(
                user_id, 
                message=TextSendMessage(
                    text = '請問你是要?',
                    quick_replies = [
                        TextQuickReply(title='買現鈔', payload=payload_buy),
                        TextQuickReply(title='賣現鈔', payload=payload_sell)
                    ]          
                )
            )
            
        elif data[user_id]['status'] == 8.3:
            fb_bot_api.push_message(
                user_id, 
                message=TextSendMessage(text = '你要換多少呢?')
            )

    # 匯率
    if quick_reply_payload.startswith('currency_'):
        if quick_reply_payload[9:] == 'US':
            send_message = currency('美元 US', 'USD')
        elif quick_reply_payload[9:] == 'CN':
            send_message = currency('人民幣 CN', 'CNY')
        elif quick_reply_payload[9:] == 'HK':
            send_message = currency('港幣 HK', 'HKD')
        elif quick_reply_payload[9:] == 'JP':
            send_message = currency('日圓 JP', 'JPY')
        elif quick_reply_payload[9:] == 'EU':
            send_message = currency('歐元 EU', 'EUR')

        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = send_message,
                buttons=[
                    URLAction(
                        title='外匯走勢',
                        url='https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates',
                        webview_height_ratio='full',
                        messenger_extensions=None,
                        fallback_url=None
                    ),
                    PostbackAction(
                        title='查其他外幣匯率',
                        payload='currency'
                    )
                ]       
            )
        )


    fb_bot_api.push_message(
        user_id, 
        message=TextSendMessage(text='success qr')
    )

def currency(dollar, en_dollar):
    r = requests.get('https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates')
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, "html.parser")
        
        dollar_info = soup.find_all("tr", {"class": en_dollar})[0]
        buy_instant = dollar_info.find_all("div", {'class': 'BBoardRate'})[0].string
        sell_instant = dollar_info.find_all("div", {'class': 'SBoardRate'})[0].string

    return '{dollar} \n\n我要賣{dollar} - 買匯價: {buy_instant} \n我要買{dollar} - 賣匯價: {sell_instant}'


@handler.add(PostbackEvent) # button action
def handle_postback_message(event):


    button_payload = event.postback.payload
    
    user_id = event.sender.id
    
    if button_payload == 'currency':
        fb_bot_api.push_message(
            user_id, 
            message=TextSendMessage(
                text = '你要查詢哪個外幣呢？',
                quick_replies = [
                    TextQuickReply(title='美元 US', payload='currency_US'),
                    TextQuickReply(title='人民幣 CN', payload='currency_CN'),
                    TextQuickReply(title='港幣 HK', payload='currency_HK'),
                    TextQuickReply(title='日圓 JP', payload='currency_JP'),
                    TextQuickReply(title='歐元 EU', payload='currency_EU')
                ]         
            )
        )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
